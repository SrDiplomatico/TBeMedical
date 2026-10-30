"""Browser session management using Playwright."""

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from typing import Optional

from src.config.settings import EMEDICAL_BASE_URL
from src.config.paths import is_frozen, CHROME_NOT_FOUND_MESSAGE


# Global browser manager instance for session persistence between automation runs
_global_browser_manager: Optional['BrowserManager'] = None

# Keep references to old Playwright instances so they aren't garbage-collected
# (GC would call stop() which kills the browser we want to keep alive)
_orphaned_playwrights = []


def get_browser_manager() -> 'BrowserManager':
    """
    Get the global browser manager instance.
    Creates one if it doesn't exist.
    This allows the browser session to persist between automation runs.
    """
    global _global_browser_manager
    if _global_browser_manager is None:
        _global_browser_manager = BrowserManager()
    return _global_browser_manager


def reset_browser_manager(close_browser: bool = True) -> None:
    """
    Reset the global browser manager.
    
    Args:
        close_browser: If True, close the browser entirely (for clean shutdown).
                      If False, disconnect only - leave the browser process alive
                      so it can be reconnected via CDP on port 9222.
    """
    global _global_browser_manager
    if _global_browser_manager is not None:
        try:
            if close_browser:
                _global_browser_manager.close_all()
            else:
                _global_browser_manager.disconnect()
        except Exception:
            pass
        _global_browser_manager = None


class BrowserManager:
    """
    Manages Playwright browser instance with shared context.
    Uses a single browser context so all tabs share the same session/cookies.
    """
    
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.pages: list[Page] = []
    
    def is_connected(self) -> bool:
        """
        Check if we have an active browser connection.
        
        Returns:
            True if browser is connected and has at least one page
        """
        if not self.browser or not self.context:
            return False
        
        try:
            # Try to check if the browser is still responsive
            # by checking if we have any pages
            pages = self.context.pages
            return len(pages) > 0
        except Exception:
            return False
    
    def get_existing_emedical_page(self) -> Optional[Page]:
        """
        Find an existing eMedical page in the current browser session.
        
        Returns:
            Page object if found, None otherwise
        """
        if not self.is_connected():
            return None
        
        try:
            # Refresh our pages list from the context
            self.pages = list(self.context.pages)
            
            # Find eMedical page
            for page in self.pages:
                try:
                    url = page.url.lower()
                    if "emedical" in url or "immi.gov.au" in url:
                        print(f"Found existing eMedical page: {page.url}")
                        return page
                except Exception:
                    continue
            
            # Return first non-blank page
            for page in self.pages:
                try:
                    url = page.url.lower()
                    if url and url != "about:blank":
                        print(f"Using existing page: {page.url}")
                        return page
                except Exception:
                    continue
            
            return None
        except Exception:
            return None
    
    @staticmethod
    def _port_open(port: int = 9222) -> bool:
        """Check if a TCP port is open on localhost."""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            s.close()
            return result == 0
        except Exception:
            return False
    
    def disconnect(self) -> None:
        """
        Disconnect from the browser WITHOUT closing the browser process.
        The browser stays alive on port 9222 for later CDP reconnection.
        
        Use this when switching between automation runs in different threads
        while keeping the same browser window open.
        """
        self.pages.clear()
        self.context = None
        self.browser = None
        if self.playwright:
            # Save reference so GC doesn't call stop() and kill the browser
            _orphaned_playwrights.append(self.playwright)
            print("DEBUG: Disconnected from browser (kept alive for CDP reconnection)")
        self.playwright = None
    
    def start(self, headless: bool = False) -> None:
        """
        Start the browser.
        
        If a browser from a previous run is still alive on port 9222,
        reconnects to it via CDP instead of launching a new instance.
        
        Args:
            headless: If False (default), browser window is visible
        """
        # If already connected, don't start a new browser
        if self.is_connected():
            print("Browser already connected, reusing existing session")
            return
        
        # Check if there's already a browser on port 9222 from a previous run
        if self._port_open(9222):
            print("DEBUG: Port 9222 already open, reusing existing browser via CDP...")
            try:
                self.connect_to_existing()
                return
            except Exception as e:
                print(f"DEBUG: Could not reuse existing browser: {e}")
                # Fall through to launch a new browser
        
        self.playwright = sync_playwright().start()
        launch_kwargs = dict(
            headless=headless,
            slow_mo=50,  # Slight delay for stability
            args=["--remote-debugging-port=9222"],
        )
        # Use the Google Chrome installed on this machine rather than a bundled
        # Chromium, so the packaged app has no browser download step.
        try:
            self.browser = self.playwright.chromium.launch(channel="chrome", **launch_kwargs)
        except Exception as chrome_err:
            if is_frozen():
                self.playwright.stop()
                self.playwright = None
                raise RuntimeError(CHROME_NOT_FOUND_MESSAGE) from chrome_err
            # Development fallback: Playwright's own Chromium (playwright install chromium)
            print(f"DEBUG: Google Chrome launch failed ({chrome_err}); falling back to bundled Chromium")
            self.browser = self.playwright.chromium.launch(**launch_kwargs)
        # Create a single context that all tabs will share
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 900}
        )
    
    def connect_to_existing(self, cdp_url: str = "http://localhost:9222") -> Page:
        """
        Connect to an existing Chrome browser with remote debugging enabled.
        
        To use this, start Chrome with:
        chrome.exe --remote-debugging-port=9222
        
        Args:
            cdp_url: CDP endpoint URL
            
        Returns:
            The first page in the connected browser
            
        Raises:
            ConnectionError: If Chrome is not reachable on the debug port
        """
        import socket
        import time as _time
        
        # First, check if the port is actually open
        port = int(cdp_url.rsplit(":", 1)[-1]) if ":" in cdp_url else 9222
        
        def _port_open():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                result = s.connect_ex(('localhost', port))
                s.close()
                return result == 0
            except Exception:
                return False
        
        # Retry port check a few times (Chrome may still be starting)
        port_available = False
        for attempt in range(6):
            if _port_open():
                port_available = True
                break
            print(f"DEBUG: Port {port} not open yet, attempt {attempt+1}/6...")
            _time.sleep(1)
        
        if not port_available:
            raise ConnectionError(
                f"Chrome remote debugging port {port} is not open. "
                f"Make sure Chrome was started with --remote-debugging-port={port}"
            )
        
        # Clean up any existing stale connections first
        # This prevents thread affinity issues with old Page objects
        if self.playwright is not None:
            try:
                self.pages.clear()
                self.context = None
                self.browser = None
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
        
        # Now connect fresh
        self.playwright = sync_playwright().start()
        
        # Try to connect with retries
        last_error = None
        for attempt in range(3):
            try:
                self.browser = self.playwright.chromium.connect_over_cdp(cdp_url)
                break
            except Exception as e:
                last_error = e
                print(f"DEBUG: CDP connect attempt {attempt+1}/3 failed: {e}")
                _time.sleep(2)
        else:
            raise ConnectionError(
                f"Could not connect to Chrome via CDP at {cdp_url} "
                f"after 3 attempts. Last error: {last_error}"
            )
        # Get the default context (the one with the existing pages)
        self.context = self.browser.contexts[0]
        # Get the existing pages
        existing_pages = self.context.pages
        if existing_pages:
            self.pages = list(existing_pages)
            # Find the eMedical page, not DevTools or other pages
            for page in self.pages:
                url = page.url.lower()
                if "emedical" in url or "immi.gov.au" in url:
                    print(f"Found eMedical page: {page.url}")
                    return page
            # If no eMedical page found, skip devtools/chrome pages
            for page in self.pages:
                url = page.url.lower()
                if not url.startswith("devtools://") and not url.startswith("chrome://"):
                    print(f"Using page: {page.url}")
                    return page
            # Last resort, return the first page
            return self.pages[0]
        else:
            # No pages, create one
            return self.new_tab()
    
    def new_tab(self) -> Page:
        """
        Open a new tab in the shared context.
        
        Returns:
            New Page object
        """
        if not self.context:
            raise RuntimeError("Browser not started. Call start() first.")
        
        page = self.context.new_page()
        self.pages.append(page)
        return page
    
    def navigate_to_emedical(self, page: Page) -> None:
        """
        Navigate a page to the eMedical portal.
        
        Args:
            page: Page to navigate
        """
        page.goto(EMEDICAL_BASE_URL)
        page.wait_for_load_state("networkidle")
    
    def close_tab(self, page: Page) -> None:
        """
        Close a specific tab.
        
        Args:
            page: Page to close
        """
        if page in self.pages:
            self.pages.remove(page)
        page.close()
    
    def close_all(self) -> None:
        """Close all tabs and the browser."""
        for page in self.pages:
            try:
                page.close()
            except Exception:
                pass
        self.pages.clear()
        
        if self.context:
            self.context.close()
            self.context = None
        
        if self.browser:
            self.browser.close()
            self.browser = None
        
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all()
        return False
