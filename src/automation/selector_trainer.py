"""
Selector Training Tool for eMedical Portal

This tool helps you discover and map web form selectors to I-693 data fields.
It opens a browser, lets you navigate to the eMedical portal, and helps you
capture selectors for each field.

Usage:
    python -m src.automation.selector_trainer

Instructions:
1. Browser opens to eMedical login page
2. Right-click on any field and select "Inspect" in DevTools
3. In the console, type the selector (e.g., #username, input[name='password'])
4. Use the terminal prompts to save selectors to the mapping file
"""

import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Page, Browser

# Output file for discovered selectors
SELECTORS_FILE = Path(__file__).parent / "discovered_selectors.json"
EMEDICAL_URL = "https://www.emedical.immi.gov.au/eMedUI/eMedical"


class SelectorTrainer:
    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.page: Page = None
        self.selectors = self._load_selectors()
    
    def _load_selectors(self) -> dict:
        """Load existing selectors if file exists."""
        if SELECTORS_FILE.exists():
            with open(SELECTORS_FILE, 'r') as f:
                return json.load(f)
        return {
            "login": {},
            "page1": {},
            "page2": {},
            "page3": {},
            "page4": {},
            "navigation": {},
            "file_uploads": {}
        }
    
    def _save_selectors(self):
        """Save selectors to file."""
        with open(SELECTORS_FILE, 'w') as f:
            json.dump(self.selectors, f, indent=2)
        print(f"\n✅ Selectors saved to: {SELECTORS_FILE}")
    
    async def start(self):
        """Start the browser for selector discovery."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            slow_mo=100  # Slow down actions for visibility
        )
        self.page = await self.browser.new_page()
        
        # Navigate to eMedical
        print(f"\n🌐 Opening eMedical portal: {EMEDICAL_URL}")
        await self.page.goto(EMEDICAL_URL)
        
        print("\n" + "="*60)
        print("SELECTOR TRAINING MODE")
        print("="*60)
        print("""
Instructions:
1. The browser is now open to the eMedical portal
2. Use Chrome DevTools (F12) to inspect elements
3. Find selectors for each field you need

To find a selector:
- Right-click on a field → Inspect
- In DevTools, right-click the element → Copy → Copy selector
- Or note the id, name, or class attributes

Common selector patterns:
- By ID:    #fieldId
- By name:  input[name='fieldName']
- By class: .className
- Combined: input.form-control[name='username']
""")
    
    async def test_selector(self, selector: str) -> bool:
        """Test if a selector finds an element on the current page."""
        try:
            element = await self.page.query_selector(selector)
            if element:
                # Highlight the element briefly
                await self.page.evaluate("""
                    (selector) => {
                        const el = document.querySelector(selector);
                        if (el) {
                            const orig = el.style.outline;
                            el.style.outline = '3px solid red';
                            setTimeout(() => el.style.outline = orig, 2000);
                        }
                    }
                """, selector)
                return True
            return False
        except Exception as e:
            print(f"  ❌ Error testing selector: {e}")
            return False
    
    async def interactive_mode(self):
        """Run interactive selector discovery."""
        print("\n" + "-"*60)
        print("INTERACTIVE MODE - Type commands below")
        print("-"*60)
        print("""
Commands:
  test <selector>     - Test if selector finds an element (highlights it)
  add <page> <field> <selector> - Add a selector mapping
  show                - Show all current selectors
  save                - Save selectors to file
  fill <selector> <value> - Test filling a field
  click <selector>    - Test clicking an element
  screenshot          - Take a screenshot
  url                 - Show current URL
  quit                - Exit training mode

Pages: login, page1, page2, page3, page4, navigation, file_uploads
""")
        
        while True:
            try:
                cmd = input("\n> ").strip()
                if not cmd:
                    continue
                
                parts = cmd.split(maxsplit=3)
                action = parts[0].lower()
                
                if action == "quit" or action == "exit":
                    print("Exiting...")
                    break
                
                elif action == "test" and len(parts) >= 2:
                    selector = parts[1]
                    found = await self.test_selector(selector)
                    if found:
                        print(f"  ✅ Found element: {selector}")
                    else:
                        print(f"  ❌ Not found: {selector}")
                
                elif action == "add" and len(parts) >= 4:
                    page, field, selector = parts[1], parts[2], parts[3]
                    if page in self.selectors:
                        self.selectors[page][field] = selector
                        print(f"  ✅ Added: {page}.{field} = {selector}")
                    else:
                        print(f"  ❌ Unknown page: {page}")
                        print(f"     Valid pages: {list(self.selectors.keys())}")
                
                elif action == "show":
                    print("\nCurrent selectors:")
                    print(json.dumps(self.selectors, indent=2))
                
                elif action == "save":
                    self._save_selectors()
                
                elif action == "fill" and len(parts) >= 3:
                    selector, value = parts[1], parts[2]
                    try:
                        await self.page.fill(selector, value)
                        print(f"  ✅ Filled {selector} with '{value}'")
                    except Exception as e:
                        print(f"  ❌ Error: {e}")
                
                elif action == "click" and len(parts) >= 2:
                    selector = parts[1]
                    try:
                        await self.page.click(selector)
                        print(f"  ✅ Clicked {selector}")
                    except Exception as e:
                        print(f"  ❌ Error: {e}")
                
                elif action == "screenshot":
                    path = "emedical_screenshot.png"
                    await self.page.screenshot(path=path)
                    print(f"  ✅ Screenshot saved: {path}")
                
                elif action == "url":
                    print(f"  Current URL: {self.page.url}")
                
                elif action == "help":
                    print(__doc__)
                
                else:
                    print("  Unknown command. Type 'help' for commands.")
            
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"  Error: {e}")
        
        # Cleanup
        await self.browser.close()
        await self.playwright.stop()
    
    async def auto_discover_login(self):
        """Attempt to auto-discover login page selectors."""
        print("\n🔍 Attempting to auto-discover login selectors...")
        
        # Common login field patterns
        username_selectors = [
            "#username", "#user", "#email", "#userId",
            "input[name='username']", "input[name='user']",
            "input[name='email']", "input[name='userId']",
            "input[type='text']", "input[type='email']",
            "#txtUserName", "#txtUsername", "#userName",
        ]
        
        password_selectors = [
            "#password", "#pass", "#pwd",
            "input[name='password']", "input[name='pass']",
            "input[type='password']",
            "#txtPassword", "#txtPass",
        ]
        
        submit_selectors = [
            "button[type='submit']", "input[type='submit']",
            "#login", "#loginBtn", "#btnLogin", "#submit",
            ".login-button", ".btn-login", ".submit-btn",
            "button:has-text('Login')", "button:has-text('Sign in')",
        ]
        
        # Test username fields
        for sel in username_selectors:
            if await self.test_selector(sel):
                print(f"  ✅ Username field found: {sel}")
                self.selectors["login"]["username"] = sel
                break
        else:
            print("  ⚠️ Username field not auto-detected")
        
        # Test password fields
        for sel in password_selectors:
            if await self.test_selector(sel):
                print(f"  ✅ Password field found: {sel}")
                self.selectors["login"]["password"] = sel
                break
        else:
            print("  ⚠️ Password field not auto-detected")
        
        # Test submit buttons
        for sel in submit_selectors:
            if await self.test_selector(sel):
                print(f"  ✅ Login button found: {sel}")
                self.selectors["login"]["submit"] = sel
                break
        else:
            print("  ⚠️ Login button not auto-detected")


async def main():
    trainer = SelectorTrainer()
    await trainer.start()
    
    # Try auto-discovery first
    await trainer.auto_discover_login()
    
    # Then enter interactive mode
    await trainer.interactive_mode()


if __name__ == "__main__":
    asyncio.run(main())
