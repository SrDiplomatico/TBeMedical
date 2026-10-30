"""eMedical automation - main automation controller."""

import re
import time
import tkinter as tk
from tkinter import messagebox
from datetime import date
from pathlib import Path
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from playwright.sync_api import Page

from src.ui.missing_data_dialog import MissingDataDialog
from src.config.settings import (
    FIELD_DELAY_MS,
    PAGE_LOAD_TIMEOUT_MS,
    EMEDICAL_BASE_URL,
    MAX_CONCURRENT_PATIENTS,
    DEBUG_START_PAGE,
    CHECKPOINT_PAGES,
)
from src.models.i693_form import PatientFiles, I693Form
from src.ui.login_dialog import Credentials
from src.ui.batch_monitor import PatientStatus
from src.automation.browser import BrowserManager, get_browser_manager, reset_browser_manager
from src.automation.field_map_emedical import (
    EMEDICAL_PAGES,
    PAGE_NAVIGATION,
    FILE_UPLOADS,
    get_page_fields,
    get_country_code,
    get_issuing_country_code,
    get_state_code,
    sanitize_name,
    PAGE3_ADDRESS_POPUP,
    PAGE3_PHONE_POPUP,
    PAGE5_IDENTITY,
    PAGE6_START_EXAMS,
    PAGE7_SELECTIVE_TB,
    PAGE8_VIEW_EXAM,
    PAGE9_EXAM_DATE,
)
from src.automation.selector_discovery import (
    discover_page1_selectors,
    discover_page2_selectors,
    discover_page3_selectors,
    discover_page3_popup_selectors,
    discover_page3_phone_popup_selectors,
    discover_page6_selectors,
    discover_page7_selectors,
    discover_page8_selectors,
    discover_page9_selectors,
    discover_page9_deferred_selectors,
    discover_page9_file_upload_selectors,
    discover_page9_upload_popup_selectors,
    discover_navigation_buttons,
)


class EMedicalAutomation:
    """
    Automates data entry into the eMedical portal.
    
    Works in a SINGLE browser tab (eMedical does not allow multiple tabs/sessions):
    for each patient it fills pages 1-9, uploads files, STOPS before final submit,
    then returns to Case search (top-left menu) and starts the next patient.
    """
    
    _stop_requested: bool = False
    skip_checkpoints: bool = False
    
    @classmethod
    def request_stop(cls):
        """Request the automation to stop after the current operation."""
        cls._stop_requested = True
    
    @classmethod
    def is_stop_requested(cls) -> bool:
        """Check if a stop has been requested."""
        return cls._stop_requested
    
    @classmethod
    def clear_stop(cls):
        """Clear the stop request flag."""
        cls._stop_requested = False
    
    def __init__(self):
        # Use the global browser manager to persist sessions between runs
        self.browser_manager = get_browser_manager()
        self.on_status_update: Optional[Callable[[str, PatientStatus], None]] = None
    
    def _show_checkpoint_dialog(self, page_num: int, patient_name: str) -> bool:
        """
        Show a confirmation dialog at checkpoint pages to let user verify data.
        
        Args:
            page_num: Current page number
            patient_name: Name of the patient being processed
            
        Returns:
            True to continue, False to abort
        """
        # Create a temporary root window (hidden)
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Ensure dialog is on top
        
        # Determine page description
        page_descriptions = {
            2: "Applicant Details (Create Case)",
            5: "Identity Confirmation",
        }
        page_desc = page_descriptions.get(page_num, f"Page {page_num}")
        
        # Show dialog
        result = messagebox.askokcancel(
            f"Checkpoint - Page {page_num}",
            f"Patient: {patient_name}\n\n"
            f"Page: {page_desc}\n\n"
            f"Please verify the data on the page is correct.\n\n"
            f"Click OK to continue to the next page,\n"
            f"or Cancel to stop the automation.",
            parent=root
        )
        
        root.destroy()
        return result
    
    def _show_resume_dialog(self, page_desc: str, start_page: int) -> None:
        """
        Show a dialog asking user to navigate to the correct page.
        (Login is already done automatically)
        
        Args:
            page_desc: Description of the page to navigate to
            start_page: Page number to start from
        """
        # Create a temporary root window (hidden)
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Ensure dialog is on top
        
        # Show dialog with instructions
        messagebox.showinfo(
            f"Resume from Page {start_page}",
            f"You are now logged in to eMedical.\n\n"
            f"Please complete these steps:\n\n"
            f"1. Search for and open the FIRST patient's case\n"
            f"2. Navigate to: {page_desc}\n\n"
            f"The first patient resumes from that page. Any further\n"
            f"patients start automatically from Case search.\n\n"
            f"Click OK when you're on the correct page\n"
            f"and ready to continue automation.",
            parent=root
        )
        
        root.destroy()
    
    def _show_already_logged_in_dialog(self) -> None:
        """
        Show a dialog confirming user is already logged in to eMedical.
        Used when starting from Page 1 without login.
        """
        # Create a temporary root window (hidden)
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Ensure dialog is on top
        
        # Show dialog with instructions
        messagebox.showinfo(
            "Already Logged In Mode",
            "Connected to existing browser.\n\n"
            "Please confirm you are logged into eMedical\n"
            "and on the main dashboard.\n\n"
            "Click OK when ready to begin automation.",
            parent=root
        )
        
        root.destroy()
    
    def _show_connect_error_dialog(self, error_detail: str = "") -> None:
        """
        Show an error dialog when unable to connect to existing browser.
        """
        import socket
        
        # Check if port 9222 is open for diagnostic info
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            port_open = s.connect_ex(('localhost', 9222)) == 0
            s.close()
        except Exception:
            port_open = False
        
        if port_open:
            diagnostic = "Port 9222 IS open but CDP connection failed."
        else:
            diagnostic = "Port 9222 is NOT open - Chrome debug mode is not running."
        
        detail = f"\n\nError: {error_detail}" if error_detail else ""
        
        # Create a temporary root window (hidden)
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Ensure dialog is on top
        
        # Show error dialog with instructions
        messagebox.showerror(
            "Cannot Connect to Browser",
            f"Could not connect to an existing Chrome browser.\n"
            f"({diagnostic}){detail}\n\n"
            "To use 'Already Logged In' mode:\n\n"
            "1. Close ALL Chrome windows first\n"
            "2. Click 'Launch Chrome' button in this app\n"
            "   (or run: chrome.exe --remote-debugging-port=9222)\n\n"
            "3. Log into eMedical manually\n"
            "4. Try again\n\n"
            "Or select 'Login (New Case)' to start fresh.",
            parent=root
        )
        
        root.destroy()
    
    def run_batch(
        self,
        patients: list[PatientFiles],
        credentials: Optional[Credentials],
        start_page: int = 0,
        skip_uploads: bool = False,
        on_status_update: Optional[Callable[[str, PatientStatus], None]] = None,
        skip_checkpoints: bool = False,
    ) -> None:
        """
        Process a batch of patients one after another in a single browser tab.
        
        After each patient reaches the final page (uploads done, submit NOT clicked)
        the automation clicks "Case search" and begins the next patient. In resume
        modes (start_page > 1) only the FIRST patient resumes from that page; every
        following patient starts fresh from Case search / page 1.
        
        Args:
            patients: List of PatientFiles to process (max MAX_CONCURRENT_PATIENTS)
            credentials: eMedical login credentials (only required for a new login)
            start_page: Page number to start from:
                0 = Login (New Case) - do login + start from page 1
                1 = Page 1 (Already Logged In) - skip login, start from page 1
                2 = Page 2 (Applicant Details) - skip login, resume from page 2
                3 = Page 3 (Address) - skip login, resume from page 3
                9 = Page 9 (Exam Data) - skip login, resume from page 9
            on_status_update: Callback for status updates
            skip_checkpoints: Don't pause for user verification at CHECKPOINT_PAGES
        """
        # Clear any previous stop request
        EMedicalAutomation.clear_stop()
        
        self.on_status_update = on_status_update
        self.skip_checkpoints = skip_checkpoints
        patients = patients[:MAX_CONCURRENT_PATIENTS]
        
        # Reset the browser manager for the new thread.
        # Each run executes in a new thread, and Playwright objects are bound to their
        # creation thread. Reusing a BrowserManager from a dead thread causes:
        # "cannot switch to a different thread (which happens to have exited)"
        #
        # For "Already Logged In" / resume modes: disconnect only (browser stays alive
        # on port 9222 for CDP reconnection). For "New Case": close browser entirely
        # unless there's an existing browser we can reuse.
        print(f"DEBUG: Resetting browser manager for new automation thread (start_page={start_page})")
        if start_page >= 1:
            # Keep browser alive so we can reconnect via CDP
            reset_browser_manager(close_browser=False)
        else:
            # New Case mode: close old browser (start() will reuse if port 9222 is still open)
            reset_browser_manager(close_browser=True)
        
        # Get a fresh browser manager for this thread
        self.browser_manager = get_browser_manager()
        
        try:
            # For "Already Logged In" mode, try to reuse existing browser session first
            # For all other modes, start a fresh browser
            if start_page == 1:
                # ALREADY LOGGED IN MODE
                # First, try to connect via CDP to existing Chrome with debug port
                print("ALREADY LOGGED IN MODE: Trying to connect via CDP...")
                try:
                    login_page = self.browser_manager.connect_to_existing()
                    print(f"Connected to existing browser via CDP, found page: {login_page.url}")
                except Exception as e:
                    print(f"Failed to connect to existing browser: {e}")
                    # Show error dialog with actual error detail
                    self._show_connect_error_dialog(str(e))
                    return
            elif start_page > 1:
                # RESUME MODE: Connect to existing Chrome browser via CDP
                # User already has eMedical open on the page they want to resume from
                print(f"RESUME MODE (page {start_page}): Trying to connect via CDP...")
                try:
                    login_page = self.browser_manager.connect_to_existing()
                    print(f"Connected to existing browser via CDP, found page: {login_page.url}")
                except Exception as e:
                    print(f"Failed to connect to existing browser for resume: {e}")
                    self._show_connect_error_dialog(str(e))
                    return
            else:
                # Start fresh browser for login or resume modes
                self.browser_manager.start(headless=False)
                login_page = self.browser_manager.new_tab()
            
            # Single tab for the whole batch. eMedical rejects multiple tabs/sessions,
            # so every patient is processed in this one page, one after another.
            page = login_page
            
            if start_page == 0:
                # Normal mode: log in automatically
                if credentials is None:
                    raise ValueError("Credentials are required when starting a new case")
                self._login(page, credentials)
            elif start_page == 1:
                print("ALREADY LOGGED IN MODE: Using existing browser session")
            else:
                print(f"RESUME MODE: First patient resumes from page {start_page}; "
                      f"remaining patients start from Case search")
            
            print(f"DEBUG: Processing {len(patients)} patient(s) sequentially in one tab:")
            for idx, p in enumerate(patients):
                print(f"  Patient {idx+1}: {p.patient_name} - I693: {p.i693_path}")
            
            total = len(patients)
            for i, patient in enumerate(patients):
                patient_num = i + 1
                
                if EMedicalAutomation.is_stop_requested():
                    print(f"DEBUG: Stop requested - not starting patient {patient_num}")
                    for remaining in patients[i:]:
                        self._update_status(remaining.patient_name, "error",
                                            error_message="Stopped by user before starting")
                    break
                
                # First patient honours the selected start page. Every later patient
                # begins at Case search (page 1) in the same, already-logged-in tab.
                if i == 0:
                    effective_start = start_page
                else:
                    effective_start = 1
                    print(f"DEBUG: Returning to Case search for patient {patient_num}/{total}...")
                    try:
                        self._return_to_case_search(page)
                    except Exception as nav_err:
                        print(f"DEBUG: Could not return to Case search: {nav_err}")
                        self._update_status(
                            patient.patient_name, "error",
                            error_message=f"Could not return to Case search: {nav_err}"
                        )
                        continue
                
                print(f"DEBUG: Processing patient {patient_num}/{total} ({patient.patient_name}) "
                      f"from page {effective_start}")
                try:
                    self._update_status(patient.patient_name, "processing", current_page=0)
                    self._process_patient(page, patient, start_page=effective_start, skip_uploads=skip_uploads)
                    self._update_status(patient.patient_name, "ready_for_review", current_page=10)
                    print(f"DEBUG: Completed patient {patient_num} ({patient.patient_name}) - "
                          f"stopped before final submit")
                except Exception as e:
                    print(f"DEBUG: Error processing patient {patient_num}: {e}")
                    import traceback
                    traceback.print_exc()
                    self._update_status(
                        patient.patient_name, 
                        "error", 
                        error_message=str(e)
                    )
                    # Continue with next patient even if this one fails
            
            print(f"DEBUG: All {len(patients)} patients processed")
            
            # Don't close browser - leave it open for user review and manual submit
            # User will close browser when done
            
        except Exception as e:
            # On critical error, still try to leave browser open
            raise e
    
    def _return_to_case_search(self, page: Page) -> None:
        """
        Navigate the single working tab back to the Case search page (page 1).
        
        Tries the top-left "Case search" menu item first, then a text-based
        fallback, and finally reloads the eMedical home URL and tries again.
        Raises RuntimeError if the Case search page cannot be reached.
        """
        case_search_selector = "#appMenu-caseSearch_0-body"
        alt_selector = "span:has-text('Case search')"
        search_button = PAGE_NAVIGATION.get("page1_search_button", "#caseSearch-search")
        
        def _on_case_search() -> bool:
            try:
                return page.locator(search_button).first.is_visible(timeout=1500)
            except Exception:
                return False
        
        for attempt in range(1, 4):
            if _on_case_search():
                print("DEBUG: Case search page is showing")
                return
            
            for selector in (case_search_selector, alt_selector):
                try:
                    page.wait_for_selector(selector, state="visible", timeout=5000)
                    page.click(selector)
                    print(f"DEBUG: Clicked 'Case search' ({selector})")
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                    break
                except Exception as e:
                    print(f"DEBUG: Case search click failed via {selector}: {e}")
            
            if _on_case_search():
                print("DEBUG: Case search page loaded")
                return
            
            # Menu may be hidden behind a dialog or the page may be in a bad state:
            # reload the eMedical home page and try the menu again.
            print(f"DEBUG: Not on Case search after attempt {attempt}; reloading eMedical home")
            try:
                page.goto(EMEDICAL_BASE_URL)
                page.wait_for_load_state("networkidle")
                time.sleep(1.5)
            except Exception as e:
                print(f"DEBUG: Reload failed: {e}")
        
        raise RuntimeError(
            "Could not navigate back to the Case search page. "
            "Check the browser window, return to Case search manually, and resume."
        )
    
    def _login(self, page: Page, credentials: Credentials) -> None:
        """
        Login to eMedical portal.
        
        Args:
            page: Browser page
            credentials: Login credentials
        """
        page.goto(EMEDICAL_BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Fill login form using discovered selectors
        username_selector = PAGE_NAVIGATION["username_field"]  # input[type='text']
        password_selector = PAGE_NAVIGATION["password_field"]  # #logon-password_input
        login_button = PAGE_NAVIGATION["login_button"]  # #logon-btnLogon
        
        # Wait for login form to be visible
        page.wait_for_selector(username_selector, state="visible", timeout=10000)
        
        page.fill(username_selector, credentials.username)
        page.fill(password_selector, credentials.password)
        page.click(login_button)
        
        # Wait for login to complete
        page.wait_for_load_state("networkidle")
        time.sleep(1)  # Extra delay for any redirects
    
    def _process_patient(self, page: Page, patient: PatientFiles, start_page: int = 1, skip_uploads: bool = False) -> None:
        """
        Process a single patient in a browser tab.
        
        Args:
            page: Browser page/tab
            patient: Patient data and files
            start_page: Page to start from (1-9). Use for debugging/resuming.
        """
        if not patient.i693_data:
            raise ValueError(f"No I-693 data for patient {patient.patient_name}")
        
        # Register a dialog handler to accept all JavaScript dialogs (alerts/confirms)
        # This MUST be done before any page navigation to prevent Playwright's default
        # auto-dismiss from crashing on race conditions with fast-closing dialogs.
        def handle_dialog(dialog):
            try:
                print(f"DEBUG: JavaScript dialog detected: {dialog.type} - {dialog.message}")
                dialog.accept()
            except Exception as e:
                print(f"DEBUG: Dialog already dismissed (harmless): {e}")
        
        page.on("dialog", handle_dialog)
        
        # Skip to start_page if not starting from beginning
        if start_page <= 1:
            if start_page == 0:
                # Fresh login mode: navigate to eMedical base URL
                page.goto(EMEDICAL_BASE_URL)
                page.wait_for_load_state("networkidle")
                time.sleep(1)
            else:
                # Already logged in mode (start_page == 1):
                # Page is already on eMedical, no need to navigate
                print(f"DEBUG: Already on eMedical page, skipping navigation (URL: {page.url})")
            
            # Click "Case search" menu item to get to Page 1
            self._return_to_case_search(page)
            
            # Page 1: Search for existing case or create new
            print(f"DEBUG: Starting Page 1 - filling search fields...")
            self._update_status(patient.patient_name, "processing", current_page=1)
            
            # Discover Page 1 selectors dynamically (IDs change between machines)
            discover_page1_selectors(page)
            
            self._fill_page(page, 1, patient.i693_data)
            print(f"DEBUG: Page 1 fields filled, clicking Search button...")
            
            # First click "Search" button to search for existing case
            search_button = PAGE_NAVIGATION.get("page1_search_button", "#caseSearch-search")
            page.wait_for_selector(search_button, state="visible", timeout=5000)
            page.click(search_button)
            print(f"DEBUG: Search button clicked, waiting for results...")
            page.wait_for_load_state("networkidle")
            time.sleep(1)  # Reduced from 2 seconds - Wait for search results
            print(f"DEBUG: Search complete, looking for Create Case button...")
            
            # Then click "Create Case" button that appears after search
            create_case_button = PAGE_NAVIGATION.get("page1_create_case", "#caseSearch-createCase")
            
            # First wait for the button to be attached to the DOM (search may push it off-screen)
            try:
                page.wait_for_selector(create_case_button, state="attached", timeout=10000)
                print(f"DEBUG: Create Case button found in DOM, scrolling into view...")
                page.locator(create_case_button).scroll_into_view_if_needed()
                time.sleep(0.3)
                # Now wait for it to be visible (not obscured)
                page.wait_for_selector(create_case_button, state="visible", timeout=5000)
            except Exception as btn_err:
                # Button not found or not visible - take a screenshot to diagnose
                from src.config.paths import screenshots_dir
                screenshot_dir = screenshots_dir()
                screenshot_path = screenshot_dir / f"page1_after_search_{patient.patient_name.replace(' ', '_')}.png"
                try:
                    page.screenshot(path=str(screenshot_path))
                    print(f"DEBUG: Screenshot saved to {screenshot_path}")
                except Exception:
                    pass
                # Log page state for diagnosis
                print(f"DEBUG: Page URL after search: {page.url}")
                print(f"DEBUG: Could not find Create Case button ({create_case_button}): {btn_err}")
                # Try JavaScript as last resort (handles disabled/obscured buttons)
                clicked = page.evaluate(f"""
                    (() => {{
                        const btn = document.querySelector('{create_case_button}');
                        if (btn) {{ btn.scrollIntoView(); btn.click(); return true; }}
                        return false;
                    }})()
                """)
                if not clicked:
                    raise RuntimeError(
                        f"Create Case button '{create_case_button}' not found after search. "
                        f"Screenshot saved to {screenshot_path}. "
                        f"The search may have returned results that changed the page layout, "
                        f"or the button selector needs updating."
                    ) from btn_err
                print(f"DEBUG: Clicked Create Case button via JavaScript fallback")
                page.wait_for_load_state("networkidle")
                time.sleep(0.5)
            else:
                page.click(create_case_button)
                print(f"DEBUG: Clicked Create Case button, loading Page 2...")
            page.wait_for_load_state("networkidle")
            time.sleep(0.5)  # Reduced from 1 second
            print(f"DEBUG: Page 2 loaded")
        
        if start_page <= 2:
            # Page 2: Fill form fields
            self._update_status(patient.patient_name, "processing", current_page=2)
            
            # Discover Page 2 selectors dynamically (IDs change between machines)
            discover_page2_selectors(page)
            
            self._fill_page(page, 2, patient.i693_data)
            
            # Checkpoint: Pause for user verification before clicking Create
            if 2 in CHECKPOINT_PAGES and not self.skip_checkpoints:
                print("DEBUG: Checkpoint - pausing for user verification on Page 2")
                if not self._show_checkpoint_dialog(2, patient.patient_name):
                    print("DEBUG: User cancelled at Page 2 checkpoint")
                    self._update_status(patient.patient_name, "error", error_message="Cancelled by user at Page 2")
                    return
            
            # Click "Create" button to proceed to Page 3
            self._click_next(page, 2)
            print("DEBUG: Clicked 'Create' button on Page 2, proceeding to Page 3")
        
        if start_page <= 3:
            # Page 3: Special handling - address popup
            self._update_status(patient.patient_name, "processing", current_page=3)
            
            # Discover Page 3 selectors (Add button, Next button)
            discover_page3_selectors(page)
            
            self._fill_page3_address(page, patient.i693_data)
            self._click_next(page, 3)
        
        if start_page <= 4:
            # Page 4: Handle "Can you attach a photo?" and click Next
            self._update_status(patient.patient_name, "processing", current_page=4)
            discover_navigation_buttons(page, 4)
            self._fill_page4_photo(page)
            self._click_next(page, 4)
        
        if start_page <= 5:
            # Page 5: Identity confirmation (selectors are stable - name-based)
            self._update_status(patient.patient_name, "processing", current_page=5)
            discover_navigation_buttons(page, 5)
            self._fill_page5_identity(page, patient.i693_data)
            
            # Checkpoint: Pause for user verification before clicking Next
            if 5 in CHECKPOINT_PAGES and not self.skip_checkpoints:
                print("DEBUG: Checkpoint - pausing for user verification on Page 5")
                if not self._show_checkpoint_dialog(5, patient.patient_name):
                    print("DEBUG: User cancelled at Page 5 checkpoint")
                    self._update_status(patient.patient_name, "error", error_message="Cancelled by user at Page 5")
                    return
            
            self._click_next(page, 5)
            print("DEBUG: Clicked 'Next' button on Page 5, proceeding to Page 6")
        
        if start_page <= 6:
            # Page 6: Click Start Exam(s) and handle confirmation dialog
            self._update_status(patient.patient_name, "processing", current_page=6)
            discover_page6_selectors(page)
            self._fill_page6_start_exams(page)
        
        if start_page <= 7:
            # Page 7: Click "Selective History and TB" section to expand
            self._update_status(patient.patient_name, "processing", current_page=7)
            discover_page7_selectors(page)
            self._fill_page7_selective_tb(page)
        
        if start_page <= 8:
            # Page 8: Click "View exam" button
            self._update_status(patient.patient_name, "processing", current_page=8)
            discover_page8_selectors(page)
            self._fill_page8_view_exam(page)
        
        if start_page <= 9:
            # Page 9: Enter exam date, IGRA, X-ray, sputum, TB classification
            self._update_status(patient.patient_name, "processing", current_page=9)
            discover_page9_selectors(page)
            self._fill_page9_exam_date(page, patient.i693_data)
        
        # Upload files after Page 9 (works in both normal and debug mode)
        # Page 10: Upload files and STOP
        if skip_uploads:
            print("DEBUG: skip_uploads=True - skipping file uploads. Stopping after Page 9.")
            return
        self._update_status(patient.patient_name, "processing", current_page=10)
        discover_page9_file_upload_selectors(page)
        self._upload_files(page, patient)
        print("DEBUG: Completed Page 9 + file uploads. Stopping before final submit.")
        # DO NOT click final submit - leave for user review
    
    def _fill_page(self, page: Page, page_num: int, form_data: I693Form) -> None:
        """
        Fill all fields on a specific page.
        
        Args:
            page: Browser page
            page_num: Page number (1-4)
            form_data: Extracted I-693 data
        """
        from src.automation.field_map_emedical import get_page5_issuing_country, get_page5_id_type_code
        
        # Pre-fill scan: prompt user for any missing required fields before touching the browser
        self._prefill_check_page(page_num, form_data)
        
        fields = get_page_fields(page_num)
        print(f"DEBUG: Page {page_num} has {len(fields)} fields to fill")
        
        for field_key, field_config in fields.items():
            try:
                print(f"DEBUG: Filling field '{field_key}'...")
                
                # Check for special handlers first
                special_handler = field_config.get("special_handler")
                
                if special_handler == "issuing_country":
                    # Special handling for issuing country based on ID type
                    id_type = form_data.applicant.id_type or ""
                    country_of_birth = form_data.applicant.country_of_birth or ""
                    id_issuing_country = form_data.applicant.id_issuing_country or ""
                    value = get_page5_issuing_country(id_type, country_of_birth, id_issuing_country)
                    print(f"DEBUG: Issuing country - ID type: '{id_type}', Country of birth: '{country_of_birth}', Parsed issuing: '{id_issuing_country}' -> '{value}'")
                    if value:
                        self._fill_field(page, field_config, value)
                    continue
                
                # Check if this field has a static value (always use this value)
                static_value = field_config.get("static_value")
                
                if static_value:
                    # Use static value for dropdowns/special fields
                    self._fill_field(page, field_config, static_value)
                    continue
                
                # Check if this field has a default value (like dropdowns)
                default_value = field_config.get("default_value")
                
                if default_value:
                    # Use default value for dropdowns/special fields
                    self._fill_field(page, field_config, default_value)
                else:
                    # Get value from form data using data_path if available, else field_key
                    data_path = field_config.get("data_path", field_key)
                    value = self._get_form_value(form_data, data_path)
                    
                    # Convert country name to code if needed
                    if value and field_config.get("use_country_code"):
                        country_code = get_country_code(value)
                        if country_code:
                            value = country_code
                        else:
                            print(f"Warning: No country code found for '{value}'")
                    
                    # Convert country name to issuing country code if needed
                    if value and field_config.get("use_issuing_country_code"):
                        country_code = get_issuing_country_code(value)
                        if country_code:
                            value = country_code
                        else:
                            print(f"Warning: No issuing country code found for '{value}'")
                    
                    # Apply value_map if present (e.g., Passport -> 01)
                    value_map = field_config.get("value_map", {})
                    
                    # For ID type fields, use keyword-based matching instead of exact map
                    if value and field_config.get("use_id_type_code"):
                        mapped_code = get_page5_id_type_code(value)
                        print(f"DEBUG: ID type keyword match: '{value}' -> '{mapped_code}'")
                        value = mapped_code
                    elif value and value_map:
                        # Try exact match first, then case-insensitive match
                        if value in value_map:
                            value = value_map[value]
                        else:
                            # Try case-insensitive lookup
                            value_lower = value.lower().strip()
                            matched = False
                            for map_key, map_value in value_map.items():
                                if map_key.lower().strip() == value_lower:
                                    value = map_value
                                    matched = True
                                    break
                            if not matched and field_config.get("fallback_value"):
                                # Use fallback (e.g., "Other" for unknown ID types)
                                print(f"Warning: '{value}' not found in value_map, using fallback")
                                value = field_config.get("fallback_value")
                    
                    # Strip special characters if configured (e.g., for ID numbers)
                    if value and field_config.get("strip_special_chars"):
                        import re
                        original_value = value
                        # Keep only alphanumeric characters
                        value = re.sub(r'[^a-zA-Z0-9]', '', value)
                        if value != original_value:
                            print(f"DEBUG: Stripped special chars: '{original_value}' -> '{value}'")
                    
                    # Remove characters eMedical rejects in name fields
                    # (e.g. a trailing period on an abbreviated given name)
                    if value and field_config.get("sanitize_name"):
                        original_value = value
                        value = sanitize_name(value)
                        if value != original_value:
                            print(f"DEBUG: Sanitized name for {field_key}: "
                                  f"'{original_value}' -> '{value}'")
                    
                    if value:
                        self._fill_field(page, field_config, value)
            except Exception as e:
                # Log error but continue with other fields
                print(f"Error filling {field_key}: {e}")
        
        time.sleep(FIELD_DELAY_MS / 1000)
    
    def _get_form_value(self, form_data: I693Form, field_path: str) -> Optional[str]:
        """
        Get a value from the form data using dot notation path.
        
        Args:
            form_data: I693Form object
            field_path: Path like "applicant.family_name"
            
        Returns:
            String value or None
        """
        parts = field_path.split(".")
        obj = form_data
        
        try:
            for part in parts:
                obj = getattr(obj, part)
            
            # Convert to string
            if obj is None:
                return None
            elif isinstance(obj, date):
                # Format date for Australian format
                return obj.strftime("%d/%m/%Y")
            elif isinstance(obj, bool):
                return "Yes" if obj else "No"
            else:
                return str(obj)
        except AttributeError:
            return None
    
    def _fill_field(self, page: Page, field_config: dict, value: str) -> None:
        """
        Fill a single form field.
        
        Args:
            page: Browser page
            field_config: Field configuration with selector and type
            value: Value to fill
        """
        selector = field_config["selector"]
        field_type = field_config.get("type", "text")
        
        # For html_select, the actual <select> may be hidden (styled with CSS)
        # We can use select_option directly without waiting for visibility
        if field_type == "html_select":
            # Standard HTML <select> element - select by value
            # Works even if element is hidden since it uses JavaScript
            try:
                print(f"DEBUG: Selecting '{value}' in dropdown '{selector}'")
                page.select_option(selector, value=value, timeout=2000)
                print(f"DEBUG: Successfully selected '{value}'")
            except Exception as e:
                # Try with force option or wait for attached state
                print(f"DEBUG: First attempt failed, waiting for selector...")
                page.wait_for_selector(selector, state="attached", timeout=2000)
                page.select_option(selector, value=value)
                print(f"DEBUG: Second attempt succeeded")
            return
        
        # Wait for element to be visible for other field types
        page.wait_for_selector(selector, state="visible", timeout=5000)
        
        if field_type == "text":
            page.fill(selector, value)
        
        elif field_type == "date":
            # Date fields may need special handling depending on date picker
            page.fill(selector, value)
        
        elif field_type == "select":
            # Custom dropdown: click to open, then click the option
            page.click(selector)
            time.sleep(0.5)  # Wait for dropdown to open
            # Try to find and click the option with matching text
            try:
                # Look for option in dropdown list
                option_selector = f"li:has-text('{value}'), div[role='option']:has-text('{value}'), span:has-text('{value}')"
                page.click(option_selector, timeout=3000)
            except Exception:
                # Fallback: try pressing keys to select
                page.keyboard.type(value[0])  # Type first letter to jump to option
                time.sleep(0.3)
                page.keyboard.press("Enter")
        
        elif field_type == "autocomplete":
            # Autocomplete fields: type text, wait for dropdown, select first match
            page.fill(selector, value)
            time.sleep(0.5)  # Wait for autocomplete dropdown to appear
            # Press down arrow and Enter to select first suggestion
            page.press(selector, "ArrowDown")
            time.sleep(0.2)
            page.press(selector, "Enter")
            time.sleep(0.3)
        
        elif field_type == "radio":
            # Map value if needed
            value_map = field_config.get("value_map", {})
            radio_value = value_map.get(value, value)
            page.click(f"{selector}[value='{radio_value}']")
        
        elif field_type == "checkbox":
            if value.lower() in ("yes", "true", "1", "on"):
                page.check(selector)
            else:
                page.uncheck(selector)
        
        time.sleep(FIELD_DELAY_MS / 1000)
    
    # Friendly labels for data_path keys used in the pre-fill check dialog
    _FIELD_LABELS = {
        "applicant.family_name": "Family Name",
        "applicant.given_name": "Given Name",
        "applicant.date_of_birth": "Date of Birth",
        "applicant.id_number": "ID Document Number",
        "applicant.sex": "Sex",
        "applicant.country_of_birth": "Country of Birth",
        "applicant.city_of_birth": "City of Birth",
        "applicant.id_type": "ID Document Type",
    }

    def _prefill_check_page(self, page_num: int, form_data: I693Form) -> None:
        """Check for missing required fields on a page and prompt user to fill them."""
        fields = get_page_fields(page_num)
        missing: list[dict] = []

        for field_key, field_config in fields.items():
            # Skip fields that have static or default values — they don't need PDF data
            if field_config.get("static_value") or field_config.get("default_value"):
                continue
            if field_config.get("special_handler"):
                continue

            data_path = field_config.get("data_path", field_key)
            value = self._get_form_value(form_data, data_path)
            if not (value or "").strip():
                label = self._FIELD_LABELS.get(data_path, data_path.split(".")[-1].replace("_", " ").title())
                missing.append({"label": label, "key": data_path, "type": "text"})

        if not missing:
            return

        labels = ", ".join(f["label"] for f in missing)
        print(f"DEBUG: Page {page_num} missing fields: {labels}")

        patient_name = f"{form_data.applicant.given_name} {form_data.applicant.family_name}".strip() or "Unknown"
        dialog = MissingDataDialog(patient_name=patient_name, missing_fields=missing)
        result = dialog.show()

        if result is None:
            raise RuntimeError(f"User cancelled automation due to missing data on page {page_num}")

        for data_path, value in result.items():
            if value:
                parts = data_path.split(".")
                obj = form_data
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
                print(f"DEBUG: User supplied {data_path} = '{value}'")

    def _prefill_check_address(self, form_data: I693Form) -> None:
        """Check for missing required address fields and prompt user to fill them."""
        required_address_fields = [
            {"label": "Street Address", "key": "street_address", "type": "text",
             "value": form_data.applicant.street_address},
            {"label": "City", "key": "city", "type": "text",
             "value": form_data.applicant.city},
            {"label": "State", "key": "state", "type": "state_dropdown",
             "value": form_data.applicant.state},
            {"label": "Zip Code", "key": "zip_code", "type": "text",
             "value": form_data.applicant.zip_code},
        ]

        missing = [f for f in required_address_fields if not (f["value"] or "").strip()]
        if not missing:
            return

        labels = ", ".join(f["label"] for f in missing)
        print(f"DEBUG: Missing address fields for {form_data.applicant.family_name}: {labels}")

        dialog = MissingDataDialog(
            patient_name=f"{form_data.applicant.given_name} {form_data.applicant.family_name}",
            missing_fields=[{"label": f["label"], "key": f["key"], "type": f["type"]} for f in missing],
        )
        result = dialog.show()

        if result is None:
            raise RuntimeError("User cancelled automation due to missing address data")

        # Apply user-supplied values back to the form data object
        for key, value in result.items():
            if value:
                setattr(form_data.applicant, key, value)
                print(f"DEBUG: User supplied {key} = '{value}'")

    def _fill_page3_address(self, page: Page, form_data: I693Form) -> None:
        """
        Fill Page 3 address popup and phone popup.
        
        Page 3 requires clicking an add button to open a popup,
        then filling address fields, then adding phone number.
        
        Args:
            page: Browser page
            form_data: Extracted I-693 data
        """
        # Pre-fill scan: check for missing required address fields
        self._prefill_check_address(form_data)

        # === FIRST: Add Address ===
        # Click the add button (+ icon) to open the address popup
        add_button = PAGE3_ADDRESS_POPUP["add_button"]
        page.wait_for_selector(add_button, state="visible", timeout=10000)
        page.click(add_button)
        time.sleep(3)  # Wait for popup to fully load
        
        # Discover popup selectors dynamically
        discover_page3_popup_selectors(page)
        
        # Select "Address (Home)" from channel type dropdown
        # Click the dropdown, select different option, then select Address (Home)
        channel_dropdown = PAGE3_ADDRESS_POPUP["channel_type_dropdown"]
        page.wait_for_selector(channel_dropdown, state="visible", timeout=10000)
        time.sleep(1)  # Extra wait for dropdown to be ready
        
        # Click to open dropdown
        page.click(channel_dropdown)
        time.sleep(0.5)
        
        # Click on "Address (Mailing)" option first
        page.select_option(channel_dropdown, value="4")
        time.sleep(1)
        
        # Click to open dropdown again
        page.click(channel_dropdown)
        time.sleep(0.5)
        
        # Now click on "Address (Home)" option
        page.select_option(channel_dropdown, value=PAGE3_ADDRESS_POPUP["channel_type_value"])
        time.sleep(3)  # Wait for address fields to appear
        
        # Fill country dropdown (uses same codes as country_of_birth)
        # Need to use the same double-select trick to trigger the change
        country_dropdown = PAGE3_ADDRESS_POPUP["country_dropdown"]
        # For US addresses, use "USA"
        country = form_data.applicant.country or "United States"
        country_code = get_country_code(country)
        if country_code:
            page.wait_for_selector(country_dropdown, state="visible", timeout=5000)
            # Click to open, select different value first
            page.click(country_dropdown)
            time.sleep(0.5)
            page.select_option(country_dropdown, value="MEXI")  # Select Mexico first
            time.sleep(1)
            # Click to open again, then select the actual country
            page.click(country_dropdown)
            time.sleep(0.5)
            page.select_option(country_dropdown, value=country_code)
            time.sleep(1)
        
        # Fill street address
        street_input = PAGE3_ADDRESS_POPUP["street_input"]
        street = form_data.applicant.street_address or ""
        if street:
            page.wait_for_selector(street_input, state="visible", timeout=5000)
            page.fill(street_input, street)
            time.sleep(0.3)
        
        # Fill unit (APT/STE/FLR + number) - combine unit_type prefix with apt_number
        unit_input = PAGE3_ADDRESS_POPUP["unit_input"]
        apt_number = (form_data.applicant.apt_number or "").strip()
        unit_type = (form_data.applicant.unit_type or "").strip()
        
        # Filter out checkbox values like "Yes", "On", "True" from apt_number
        # Note: "1" is NOT filtered - it's a valid apt/suite number
        if apt_number and apt_number.lower() not in ("yes", "on", "true", "off"):
            # unit_type is normalized to APT/STE/FLR by the parser, but stay
            # tolerant of raw PDF values (1=APT, 2=STE, 3=FLR, or the word).
            unit_prefix = ""
            unit_type_lower = unit_type.lower().rstrip(".")
            if unit_type_lower in ("1", "apt", "apartment"):
                unit_prefix = "APT "
            elif unit_type_lower in ("2", "ste", "suite"):
                unit_prefix = "STE "
            elif unit_type_lower in ("3", "flr", "fl", "floor"):
                unit_prefix = "FLR "
            
            full_unit = f"{unit_prefix}{apt_number}"
            print(f"DEBUG: Unit field - type='{unit_type}', number='{apt_number}' -> '{full_unit}'")
            page.fill(unit_input, full_unit)
            time.sleep(0.3)
        
        # Fill city
        city_input = PAGE3_ADDRESS_POPUP["city_input"]
        city = form_data.applicant.city or ""
        if city:
            page.fill(city_input, city)
            time.sleep(0.3)
        
        # Select state from dropdown
        state_dropdown = PAGE3_ADDRESS_POPUP["state_dropdown"]
        state = form_data.applicant.state or ""
        if state:
            state_code = get_state_code(state)
            if state_code:
                page.select_option(state_dropdown, value=state_code)
                time.sleep(0.3)
        
        # Fill zip code
        zip_input = PAGE3_ADDRESS_POPUP["zip_input"]
        zip_code = form_data.applicant.zip_code or ""
        if zip_code:
            page.fill(zip_input, zip_code)
            time.sleep(0.3)
        
        # Click Save button to close popup and save address
        save_button = PAGE3_ADDRESS_POPUP["save_button"]
        page.wait_for_selector(save_button, state="visible", timeout=5000)
        page.click(save_button)
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        
        # === SECOND: Add Mobile Phone ===
        # Skip entirely if no phone number is available — saving an empty popup
        # triggers a validation error that leaves the dialog open and blocks
        # subsequent pages.
        phone = form_data.applicant.phone or form_data.applicant.mobile_phone or ""
        if not phone:
            print("DEBUG: No phone number in I-693 data — skipping phone popup")
        else:
            # Click the Add New button again to open popup
            phone_add_button = PAGE3_PHONE_POPUP["add_button"]
            page.wait_for_selector(phone_add_button, state="visible", timeout=10000)
            page.click(phone_add_button)
            time.sleep(1)  # Wait for popup to open
        
            # Select "Mobile (Personal)" from channel type dropdown
            # Need double-select trick: select different option first, then target
            phone_channel_dropdown = PAGE3_PHONE_POPUP["channel_type_dropdown"]
            page.wait_for_selector(phone_channel_dropdown, state="visible", timeout=5000)
            # Select a different option first (e.g., "Email (Personal)" = "1")
            page.select_option(phone_channel_dropdown, value="1")
            time.sleep(1)
            # Click to open dropdown again
            page.click(phone_channel_dropdown)
            time.sleep(0.5)
            # Now select "Mobile (Personal)"
            page.select_option(phone_channel_dropdown, value=PAGE3_PHONE_POPUP["channel_type_value"])
            time.sleep(3)  # Wait for phone fields to appear

            # Discover phone popup selectors dynamically
            discover_page3_phone_popup_selectors(page)

            # Fill country code (1 for US)
            country_code_input = PAGE3_PHONE_POPUP["country_code_input"]
            page.wait_for_selector(country_code_input, state="visible", timeout=5000)
            page.fill(country_code_input, "1")  # US country code
            time.sleep(0.3)

            # Fill phone number (digits only, no dashes or formatting)
            phone_input = PAGE3_PHONE_POPUP["phone_input"]
            phone_digits = ''.join(c for c in phone if c.isdigit())
            page.fill(phone_input, phone_digits)
            time.sleep(0.3)

            # Click Save button to close popup and save phone
            phone_save_button = PAGE3_PHONE_POPUP["save_button"]
            page.wait_for_selector(phone_save_button, state="visible", timeout=5000)
            try:
                page.wait_for_selector("#wc-shim", state="hidden", timeout=10000)
            except Exception:
                pass  # proceed anyway
            page.click(phone_save_button)
            page.wait_for_load_state("networkidle")
            time.sleep(1)
    
    def _fill_page4_photo(self, page: Page) -> None:
        """
        Handle the 'Can you attach a photo?' section on Page 4.

        Selects 'No', then selects 'Camera Problem' from the reason dropdown,
        and fills in 'A digital image of the applicant is not available.' as the description.
        """
        # Select "No" for "Can you attach a photo?"
        try:
            photo_radio = "input[name='pre_exam-manage_photo-_0b0c0b0a'][value='3']"
            page.wait_for_selector(photo_radio, state="attached", timeout=10000)
            page.click(photo_radio, force=True)
            print("DEBUG: Selected 'No' for 'Can you attach a photo?'")
            time.sleep(0.5)
        except Exception as e:
            print(f"DEBUG: Could not select photo radio 'No': {e}")
            return

        # Select "Camera Problem" from the reason dropdown
        try:
            photo_reason_dropdown = "#pre_exam-manage_photo-_0b0e0b_input"
            page.wait_for_selector(photo_reason_dropdown, state="visible", timeout=5000)
            page.select_option(photo_reason_dropdown, value="ERR_ATTCH_CAMERA")
            print("DEBUG: Selected 'Camera Problem' from photo reason dropdown")
            time.sleep(0.3)
        except Exception as e:
            print(f"DEBUG: Could not select photo reason dropdown: {e}")

        # Fill in the description textarea.
        # The wc-buggyie framework (AU gov web components) reads its mirror
        # state from REAL keyboard/mouse events. Programmatic .focus() and
        # .blur() bypass the framework's listeners, so aria-invalid never
        # flips and the page stays invalid even though the visible text is
        # correct. We must drive it with mouse + keyboard primitives.
        photo_desc_textarea = "#pre_exam-manage_photo-_0b0e1b_input"
        photo_text = "A digital image of the applicant is not available."
        try:
            page.wait_for_selector(photo_desc_textarea, state="visible", timeout=5000)

            # Wait for the shim to clear before interacting with the textarea.
            try:
                page.wait_for_selector("#wc-shim", state="hidden", timeout=10000)
            except Exception:
                pass  # proceed anyway

            committed = False
            for attempt in range(3):
                # Real mouse click to focus (Playwright dispatches actual
                # mousedown/mouseup/focus events the framework hooks).
                page.click(photo_desc_textarea)
                time.sleep(0.2)

                # Clear with real keyboard.
                page.keyboard.press("Control+a")
                time.sleep(0.05)
                page.keyboard.press("Delete")
                time.sleep(0.1)

                # Type with real keystrokes (each fires keydown/keypress/input/
                # keyup, which wc-buggyie listens for to update its mirror).
                page.keyboard.type(photo_text, delay=15)
                time.sleep(0.3)

                # Tab away to fire a genuine blur + change event sequence.
                page.keyboard.press("Tab")
                time.sleep(0.6)

                state = page.evaluate(
                    """(sel) => {
                        const el = document.querySelector(sel);
                        if (!el) return null;
                        return {
                            value: el.value || '',
                            ariaInvalid: el.getAttribute('aria-invalid'),
                        };
                    }""",
                    photo_desc_textarea
                )
                value_ok = bool(state) and state.get("value") == photo_text
                aria = state.get("ariaInvalid") if state else None
                # Accept "false" (validated OK) OR null/missing (framework
                # never re-validated but value is set). Only "true" means
                # the framework actively rejected.
                aria_ok = aria != "true"

                if value_ok and aria_ok:
                    print(f"DEBUG: Photo description committed (attempt {attempt + 1}, "
                          f"aria-invalid={aria})")
                    committed = True
                    break
                print(f"DEBUG: Photo description not yet committed (attempt {attempt + 1}): "
                      f"value_len={len(state.get('value', '')) if state else 0}, "
                      f"aria-invalid={aria}")

            if not committed:
                print("DEBUG: WARNING - Photo description may not be properly "
                      "registered with framework after 3 attempts")
        except Exception as e:
            print(f"DEBUG: Could not fill photo description textarea: {e}")

        # Click Save button to save the photo section.
        save_button = "#pre_exam-_2b0c0d"
        try:
            page.wait_for_selector(save_button, state="visible", timeout=5000)
            try:
                page.wait_for_selector("#wc-shim", state="hidden", timeout=10000)
            except Exception:
                pass  # proceed anyway
            page.click(save_button)
            print("DEBUG: Clicked Save button on page 4")
            page.wait_for_load_state("networkidle")
            time.sleep(0.8)
        except Exception as e:
            print(f"DEBUG: Could not click Save button on page 4: {e}")

        # If Save left aria-invalid="true" on the description, the framework
        # rejected the value. Re-type it once more with the textarea now
        # in its post-save state and re-Save.
        try:
            state = page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return null;
                    return {
                        value: el.value || '',
                        ariaInvalid: el.getAttribute('aria-invalid'),
                    };
                }""",
                photo_desc_textarea
            )
            needs_retry = bool(state) and (
                state.get("value") != photo_text
                or state.get("ariaInvalid") == "true"
            )
            if needs_retry:
                print("DEBUG: Photo description still invalid after Save; retrying")
                page.click(photo_desc_textarea)
                time.sleep(0.2)
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                page.keyboard.type(photo_text, delay=15)
                page.keyboard.press("Tab")
                time.sleep(0.5)
                page.click(save_button)
                page.wait_for_load_state("networkidle")
                time.sleep(0.8)
        except Exception as e:
            print(f"DEBUG: Photo description retry check failed: {e}")

        # Wait for the Next button to become enabled after save.
        next_button = "#pre_exam-_2b0c1a"
        try:
            page.wait_for_selector(f"{next_button}:not([disabled])", timeout=10000)
            print("DEBUG: Next button is now enabled")
        except Exception as e:
            print(f"DEBUG: Next button did not become enabled: {e}")

    def _fill_page5_identity(self, page: Page, form_data: I693Form) -> None:
        """
        Fill Page 5 identity confirmation fields.
        
        Args:
            page: Browser page
            form_data: Extracted I-693 data
        """
        from src.automation.field_map_emedical import (
            PAGE5_IDENTITY, get_page5_id_type_code, get_page5_issuing_country
        )
        
        # Always select "Yes" for identity document provided.
        # wc-buggyie hides the actual <input> behind a zero-size overlay, so
        # Playwright's visibility check (even with force=True) throws
        # "Element is not visible".  Drive it through JavaScript instead:
        # set checked, then fire click + change so the framework registers it.
        identity_yes = PAGE5_IDENTITY["identity_doc_provided_yes"]
        page.wait_for_selector(identity_yes, state="attached", timeout=10000)
        page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return;
                el.checked = true;
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            identity_yes
        )
        print(f"DEBUG: Clicked 'Yes' for identity document provided")
        time.sleep(1)  # Wait for extra fields to appear
        
        # Get ID type from I-693 Part 5.1
        id_type = form_data.applicant.id_type or ""
        country_of_birth = form_data.applicant.country_of_birth or ""
        id_issuing_country = form_data.applicant.id_issuing_country or ""
        print(f"DEBUG: ID type from I-693: '{id_type}', Country of birth: '{country_of_birth}', Issuing country: '{id_issuing_country}'")
        
        # Fill ID Document Type dropdown
        # wc-buggyie hides the <select> behind an overlay - use JS to set value.
        id_type_dropdown = PAGE5_IDENTITY.get("id_doc_type_dropdown")
        if id_type_dropdown:
            id_type_code = get_page5_id_type_code(id_type)
            print(f"DEBUG: Mapped ID type '{id_type}' to code '{id_type_code}'")
            try:
                page.wait_for_selector(id_type_dropdown, state="attached", timeout=10000)
                page.evaluate(
                    """(args) => {
                        const el = document.querySelector(args.sel);
                        if (!el) return;
                        el.value = args.val;
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }""",
                    {"sel": id_type_dropdown, "val": id_type_code}
                )
                print(f"DEBUG: Selected ID type in dropdown: {id_type_code}")
                time.sleep(0.5)

                # If "Other" (code 06) is selected, fill the text description field
                if id_type_code == "06":
                    other_id_input = PAGE5_IDENTITY.get("other_id_doc_input", "#pre_exam-confirm_identity-other_id_doc_input")
                    try:
                        page.wait_for_selector(other_id_input, state="attached", timeout=3000)
                        other_id_text = id_type.upper().strip()
                        page.evaluate(
                            """(args) => {
                                const el = document.querySelector(args.sel);
                                if (!el) return;
                                const nativeSetter = Object.getOwnPropertyDescriptor(
                                    window.HTMLInputElement.prototype, 'value'
                                ).set;
                                nativeSetter.call(el, args.text);
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                            }""",
                            {"sel": other_id_input, "text": other_id_text}
                        )
                        print(f"DEBUG: Filled 'Other' ID description with: '{other_id_text}'")
                        time.sleep(0.3)
                    except Exception as e:
                        print(f"DEBUG: Could not fill Other ID text field: {e}")
            except Exception as e:
                print(f"DEBUG: Could not select ID type dropdown: {e}")
        
        # Fill Issuing Country dropdown (same wc-buggyie hidden select)
        issuing_country_dropdown = PAGE5_IDENTITY.get("issuing_country_dropdown")
        if issuing_country_dropdown:
            issuing_country_code = get_page5_issuing_country(id_type, country_of_birth, id_issuing_country)
            print(f"DEBUG: Issuing country code: '{issuing_country_code}' (based on ID type, country of birth, and parsed issuing country)")
            try:
                page.wait_for_selector(issuing_country_dropdown, state="attached", timeout=10000)
                page.evaluate(
                    """(args) => {
                        const el = document.querySelector(args.sel);
                        if (!el) return;
                        el.value = args.val;
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }""",
                    {"sel": issuing_country_dropdown, "val": issuing_country_code}
                )
                print(f"DEBUG: Selected issuing country in dropdown: {issuing_country_code}")
                time.sleep(0.5)
            except Exception as e:
                print(f"DEBUG: Could not select issuing country dropdown: {e}")
        
        # Identity concerns: ALWAYS "No". Never "Yes".
        self._select_no_identity_concerns(page)
    
    def _select_no_identity_concerns(self, page: Page) -> None:
        """
        Force the Page 5 "Do you have any identity concerns?" answer to "No".
        
        The answer is always No. This selects the No radio, clears every other
        option in the group, then re-reads the DOM to verify. If "No" cannot be
        confirmed after several attempts the patient is aborted BEFORE clicking
        Next, so a wrong answer is never carried forward.
        """
        from src.automation.field_map_emedical import PAGE5_IDENTITY
        
        concerns_no = PAGE5_IDENTITY["identity_concerns_no"]
        # Derive the radio group name from the selector: input[name='...'][value='3']
        m = re.search(r"name=['\"]([^'\"]+)['\"]", concerns_no)
        group_name = m.group(1) if m else "pre_exam-confirm_identity-any_id_concerns"
        
        # Shared lookup: prefer the field-map selector, but reject it if its label reads
        # "Yes"; otherwise fall back to the radio in the group whose label reads "No".
        js_find = """
            const labelText = (el) => {
                const lbl = el.id ? document.querySelector(`label[for="${el.id}"]`) : null;
                const t = (lbl && lbl.textContent) || (el.closest('label') && el.closest('label').textContent) || (el.parentElement && el.parentElement.textContent) || '';
                return t.trim().toLowerCase();
            };
            const isNo = (t) => t === 'no' || t.startsWith('no ') || t.startsWith('no\\n');
            const isYes = (t) => t === 'yes' || t.startsWith('yes ') || t.startsWith('yes\\n');
            const group = Array.from(document.querySelectorAll(`input[name="${args.group}"]`));
            let noEl = document.querySelector(args.sel);
            if (noEl && isYes(labelText(noEl))) noEl = null;
            if (!noEl) noEl = group.find(el => isNo(labelText(el))) || null;
        """
        
        js_select_no = "(args) => {" + js_find + """
            if (!noEl) return { found: false, groupSize: group.length };
            for (const el of group) { if (el !== noEl && el.checked) { el.checked = false; } }
            noEl.checked = true;
            noEl.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            noEl.dispatchEvent(new Event('input', { bubbles: true }));
            noEl.dispatchEvent(new Event('change', { bubbles: true }));
            // Re-assert in case a click handler toggled it
            for (const el of group) { if (el !== noEl) { el.checked = false; } }
            noEl.checked = true;
            return { found: true, groupSize: group.length, value: noEl.value, label: labelText(noEl) };
        }"""
        
        js_verify = "(args) => {" + js_find + """
            const checked = group.filter(el => el.checked);
            return {
                groupSize: group.length,
                noFound: !!noEl,
                noChecked: !!(noEl && noEl.checked),
                othersChecked: checked.filter(el => el !== noEl).map(el => el.value),
            };
        }"""
        
        args = {"sel": concerns_no, "group": group_name}
        try:
            page.wait_for_selector(f"input[name='{group_name}']", state="attached", timeout=10000)
        except Exception as e:
            raise RuntimeError(
                f"Page 5: identity concerns radio group '{group_name}' not found - "
                f"cannot guarantee 'No' was selected. {e}"
            ) from e
        
        last_state = None
        for attempt in range(1, 5):
            result = page.evaluate(js_select_no, args)
            print(f"DEBUG: Identity concerns -> No (attempt {attempt}): {result}")
            time.sleep(0.5)
            last_state = page.evaluate(js_verify, args)
            print(f"DEBUG: Identity concerns verify: {last_state}")
            if last_state.get("noChecked") and not last_state.get("othersChecked"):
                print("DEBUG: VERIFIED 'No' selected for identity concerns")
                return
            time.sleep(0.7)
        
        raise RuntimeError(
            "Page 5: could not verify that 'No' is selected for identity concerns "
            f"(state: {last_state}). Automation stopped for this patient before clicking Next."
        )
    
    def _fill_page6_start_exams(self, page: Page) -> None:
        """
        Click Start Exam(s) button and handle the browser confirmation dialog.
        
        Args:
            page: Browser page
        """
        # Dialog handler is already registered in _process_patient
        # Click the Start Exam(s) button
        start_button = PAGE6_START_EXAMS["start_exams_button"]
        page.wait_for_selector(start_button, state="visible", timeout=10000)
        page.click(start_button)
        
        # Wait for dialog to be handled and page to load
        time.sleep(2)
        page.wait_for_load_state("networkidle")
        time.sleep(1)
    
    def _fill_page7_selective_tb(self, page: Page) -> None:
        """
        Click the 'Selective History and TB' section to expand it.
        
        Args:
            page: Browser page
        """
        # Click the summary element to expand the section
        section_selector = PAGE7_SELECTIVE_TB["selective_tb_section"]
        page.wait_for_selector(section_selector, state="visible", timeout=10000)
        page.click(section_selector)
        time.sleep(2)  # Wait for section to expand
        page.wait_for_load_state("networkidle")
        time.sleep(1)
    
    def _fill_page8_view_exam(self, page: Page) -> None:
        """
        Click the 'View exam' button.
        
        Args:
            page: Browser page
        """
        view_exam_button = PAGE8_VIEW_EXAM["view_exam_button"]
        page.wait_for_selector(view_exam_button, state="visible", timeout=10000)
        page.click(view_exam_button)
        time.sleep(2)
        page.wait_for_load_state("networkidle")
        time.sleep(1)
    
    def _fill_page9_exam_date(self, page: Page, form_data: I693Form) -> None:
        """
        Enter the exam date from I-693 Part 6.1.
        Format expected: DD/MMM/YYYY (e.g., 05/Dec/2025)
        
        Args:
            page: Browser page
            form_data: Extracted I-693 data
        """
        exam_date_input = PAGE9_EXAM_DATE["exam_date_input"]
        # exam_date is in the examination section - may be a date object or string
        exam_date_raw = form_data.examination.exam_date
        
        # Convert to string if it's a date object
        if hasattr(exam_date_raw, 'strftime'):
            # It's a date object, format it as DD MMM YYYY (e.g., "01 Nov 2025")
            exam_date = exam_date_raw.strftime("%d %b %Y")
        else:
            exam_date = str(exam_date_raw) if exam_date_raw else ""
        
        print(f"DEBUG: exam_date from form = '{exam_date}'")
        print(f"DEBUG: exam_date_input selector = '{exam_date_input}'")
        
        if exam_date:
            # Convert date to DD/MMM/YYYY format if needed
            try:
                formatted_date = self._format_exam_date(exam_date)
                print(f"DEBUG: formatted exam_date = '{formatted_date}'")
            except Exception as e:
                print(f"DEBUG: Error formatting date: {e}")
                import traceback
                traceback.print_exc()
                formatted_date = exam_date  # Use as-is if formatting fails
            
            try:
                print(f"DEBUG: Waiting for selector...")
                page.wait_for_selector(exam_date_input, state="visible", timeout=10000)
                print(f"DEBUG: Found exam date input, clicking...")
                
                # Click the field first
                page.click(exam_date_input)
                time.sleep(0.2)
                
                # Clear and type the date character by character
                page.fill(exam_date_input, "")
                # Ensure formatted_date is a string
                date_to_type = str(formatted_date)
                print(f"DEBUG: Typing date: '{date_to_type}'")
                page.type(exam_date_input, date_to_type, delay=50)
                print(f"DEBUG: Typed date successfully")
                
                time.sleep(0.3)
                
                # A dropdown appears with date options - click the first/matching option
                # The dropdown items appear in a listbox
                try:
                    # Wait for dropdown to appear
                    dropdown_option = f"span[role='listbox'] >> text='{date_to_type}'"
                    page.wait_for_selector(dropdown_option, state="visible", timeout=2000)
                    page.click(dropdown_option)
                    print(f"DEBUG: Clicked dropdown option: '{date_to_type}'")
                except Exception:
                    # Try clicking the first option if exact match not found
                    try:
                        first_option = "span[role='listbox'] >> nth=0"
                        page.click(first_option)
                        print(f"DEBUG: Clicked first dropdown option")
                    except Exception:
                        # If no dropdown, just press Enter to confirm
                        page.keyboard.press("Enter")
                        print(f"DEBUG: Pressed Enter to confirm date")
                
                time.sleep(0.3)
                # Press Tab to trigger field change and wait for new fields to populate
                page.keyboard.press("Tab")
                print(f"DEBUG: Pressed Tab, waiting for fields to populate...")
                time.sleep(0.5)  # Wait for new fields to populate
                print(f"DEBUG: Exam date entry complete")
            except Exception as e:
                print(f"DEBUG: Error filling exam date: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("DEBUG: No exam_date found in form data")
        
        # === First, select IGRA radio button ===
        igra_radio = PAGE9_EXAM_DATE["igra_radio"]
        try:
            page.wait_for_selector(igra_radio, state="visible", timeout=5000)
            page.click(igra_radio, force=True)
            print(f"DEBUG: Clicked IGRA radio button")
            time.sleep(0.5)  # Wait for IGRA fields to appear
            
            # Re-discover selectors for fields revealed after IGRA radio click
            discover_page9_deferred_selectors(page)
        except Exception as e:
            print(f"DEBUG: Error clicking IGRA radio: {e}")
        
        # === IGRA Test Type Selection ===
        igra_dropdown = PAGE9_EXAM_DATE["igra_test_dropdown"]
        tb_test_type = form_data.examination.tb_test_type or ""
        print(f"DEBUG: tb_test_type from form = '{tb_test_type}'")
        
        # Always select IGRA type (default to Quantiferon if not specified)
        try:
            page.wait_for_selector(igra_dropdown, state="visible", timeout=5000)
            print(f"DEBUG: Found IGRA dropdown, attempting selection...")
            
            # Map the test type to dropdown value
            igra_values = PAGE9_EXAM_DATE["igra_test_values"]
            igra_value = igra_values.get(tb_test_type, igra_values.get(tb_test_type.upper(), "QNTFN")) if tb_test_type else "QNTFN"
            print(f"DEBUG: Mapped to igra_value = '{igra_value}'")
            
            # Use double-select trick: select different option first, then target
            other_value = "TSPOT" if igra_value == "QNTFN" else "QNTFN"
            page.select_option(igra_dropdown, value=other_value)
            print(f"DEBUG: Selected other option first: '{other_value}'")
            time.sleep(0.2)
            page.select_option(igra_dropdown, value=igra_value)
            print(f"DEBUG: Selected IGRA test type: '{igra_value}'")
            time.sleep(0.3)
        except Exception as e:
            print(f"DEBUG: Error selecting IGRA test type: {e}")
            import traceback
            traceback.print_exc()
        
        # === IGRA Blood Sample Date ===
        igra_date_input = PAGE9_EXAM_DATE["igra_date_input"]
        igra_date_raw = form_data.examination.igra_test_date
        
        # Convert to string if it's a date object
        if hasattr(igra_date_raw, 'strftime'):
            igra_date = igra_date_raw.strftime("%d %b %Y")
        else:
            igra_date = str(igra_date_raw) if igra_date_raw else ""
        
        print(f"DEBUG: igra_test_date from form = '{igra_date}'")
        
        if igra_date:
            try:
                page.wait_for_selector(igra_date_input, state="visible", timeout=5000)
                print(f"DEBUG: Found IGRA date input, clicking...")
                
                # Click the field first
                page.click(igra_date_input)
                time.sleep(0.2)
                
                # Clear and type the date character by character
                page.fill(igra_date_input, "")
                print(f"DEBUG: Typing IGRA date: '{igra_date}'")
                page.type(igra_date_input, igra_date, delay=50)
                print(f"DEBUG: Typed IGRA date successfully")
                
                time.sleep(0.3)
                
                # A dropdown appears with date options - click the matching option or just close it
                try:
                    dropdown_option = f"span[role='listbox'] >> text='{igra_date}'"
                    page.wait_for_selector(dropdown_option, state="visible", timeout=1000)
                    page.click(dropdown_option, timeout=1000)
                    print(f"DEBUG: Clicked IGRA date dropdown option: '{igra_date}'")
                except Exception:
                    # Just press Escape to close any dropdown
                    page.keyboard.press("Escape")
                    print(f"DEBUG: Pressed Escape to close dropdown")
                
                time.sleep(0.3)
                print(f"DEBUG: IGRA date entry complete")
            except Exception as e:
                print(f"DEBUG: Error filling IGRA date: {e}")
                import traceback
                traceback.print_exc()
        
        # === IGRA Result Radio Button ===
        igra_result_raw = form_data.examination.igra_test_result or ""
        print(f"DEBUG: igra_test_result from form = '{igra_result_raw}'")
        
        if igra_result_raw:
            try:
                import datetime
                # Map I-693 result to eMedical value
                igra_result_values = PAGE9_EXAM_DATE["igra_result_values"]
                result_value = igra_result_values.get(igra_result_raw, igra_result_values.get(igra_result_raw.upper(), ""))
                print(f"DEBUG: Mapped to result_value = '{result_value}'")
                
                if result_value:
                    radio_name = PAGE9_EXAM_DATE["igra_result_radio_name"]
                    result_radio = f"input[name='{radio_name}'][value='{result_value}']"
                    print(f"DEBUG: [{datetime.datetime.now().strftime('%H:%M:%S')}] Waiting for IGRA result selector...")
                    page.wait_for_selector(result_radio, state="visible", timeout=5000)
                    print(f"DEBUG: [{datetime.datetime.now().strftime('%H:%M:%S')}] Found selector, clicking...")
                    page.click(result_radio, force=True)
                    print(f"DEBUG: [{datetime.datetime.now().strftime('%H:%M:%S')}] Clicked IGRA result radio: '{result_value}'")
                    time.sleep(0.3)
                else:
                    print(f"DEBUG: Unknown IGRA result value: '{igra_result_raw}'")
            except Exception as e:
                print(f"DEBUG: Error selecting IGRA result: {e}")
                import traceback
                traceback.print_exc()
        
        # === Chest X-ray Requirement Radio (Part 8.1.A(2)) ===
        # I-693 Part 8.1.A(2) options:
        #   A = Chest X-ray NOT required (medically cleared for TB)
        #   B = Required due to initial screening test results
        #   C = Required due to TB signs/symptoms or immunosuppression (HIV)
        #   D = Required due to IGRA exception
        # X-ray is required if B/C/D is selected, OR if IGRA is Positive/Indeterminate
        try:
            radio_name = PAGE9_EXAM_DATE["chest_xray_req_radio_name"]
            
            # Check if the I-693 has an X-ray reason that means "required" (B, C, or D)
            xray_reason = getattr(form_data.examination, 'initial_tb_screening', '') or ''
            has_xray_required_reason = xray_reason in ("B", "C", "D")
            
            # X-ray is required if reason B/C/D is given OR IGRA is not Negative
            if has_xray_required_reason or igra_result_raw != "N":
                xray_req_value = "REQ"  # Required
                reason_parts = []
                if has_xray_required_reason:
                    reason_parts.append(f"I-693 reason={xray_reason}")
                if igra_result_raw != "N":
                    reason_parts.append(f"IGRA={igra_result_raw}")
                print(f"DEBUG: Chest X-ray REQUIRED ({', '.join(reason_parts)})")
            else:
                xray_req_value = "N_REQ"  # Not required
                print(f"DEBUG: Chest X-ray NOT required (I-693 reason='{xray_reason}', IGRA={igra_result_raw})")
            
            xray_req_radio = f"input[name='{radio_name}'][value='{xray_req_value}']"
            page.wait_for_selector(xray_req_radio, state="visible", timeout=5000)
            page.click(xray_req_radio, force=True)
            print(f"DEBUG: Clicked chest X-ray requirement radio: '{xray_req_value}'")
            time.sleep(0.5)  # wait for reason checkboxes to appear after clicking Required
            
            # If chest X-ray is required, select the reason checkbox
            if xray_req_value == "REQ":
                # Map I-693 reason letter to eMedical label text (partial match, robust to wording changes)
                # I-693 options:
                #   A = Not required — no checkbox needed
                #   B = Due to initial screening test results → "Initial screening results"
                #   C = Due to TB signs/symptoms or immunosuppression (HIV) → "TB signs or symptoms"
                #   D = Due to IGRA exception → "IGRA exception"
                REASON_LABEL_MAP = {
                    "B": "Initial screening results",
                    "C": "TB signs or symptoms",
                    "D": "IGRA exception",
                }

                # Uncheck all reason checkboxes first — use label text to avoid
                # dynamic ID mismatches (IDs like hr513-... change each page load)
                for label_text in REASON_LABEL_MAP.values():
                    try:
                        cb = page.get_by_label(label_text, exact=False)
                        if cb.count() > 0 and cb.first.is_checked():
                            cb.first.click()
                            print(f"DEBUG: Unchecked existing X-ray reason: '{label_text}'")
                            time.sleep(0.1)
                    except Exception:
                        pass

                # Select correct reason based on I-693 Part 8.1.A(2)
                xray_reason = getattr(form_data.examination, 'initial_tb_screening', 'B') or 'B'
                reason_text = REASON_LABEL_MAP.get(xray_reason, "Initial screening results")
                print(f"DEBUG: Selecting X-ray reason '{reason_text}' (I-693 reason={xray_reason})")

                try:
                    cb = page.get_by_label(reason_text, exact=False)
                    cb.first.wait_for(state="visible", timeout=5000)
                    if not cb.first.is_checked():
                        cb.first.click()
                        print(f"DEBUG: Checked X-ray reason: '{reason_text}'")
                    else:
                        print(f"DEBUG: X-ray reason '{reason_text}' already checked")
                    time.sleep(0.3)
                except Exception as e:
                    print(f"DEBUG: Error selecting X-ray reason checkbox (label='{reason_text}'): {e}")
                
                # === Chest X-ray Read Date (Part 8.1.A(3)) ===
                xray_read_date_raw = form_data.examination.chest_xray_read_date
                
                # Convert to string if it's a date object
                if hasattr(xray_read_date_raw, 'strftime'):
                    xray_read_date = xray_read_date_raw.strftime("%d %b %Y")
                else:
                    xray_read_date = str(xray_read_date_raw) if xray_read_date_raw else ""
                
                print(f"DEBUG: chest_xray_read_date from form = '{xray_read_date}'")
                
                if xray_read_date:
                    try:
                        xray_read_date_input = PAGE9_EXAM_DATE["xray_read_date_input"]
                        page.wait_for_selector(xray_read_date_input, state="visible", timeout=5000)
                        print(f"DEBUG: Found X-ray read date input, clicking...")
                        
                        # Click the field first
                        page.click(xray_read_date_input)
                        time.sleep(0.2)
                        
                        # Clear and type the date
                        page.fill(xray_read_date_input, "")
                        print(f"DEBUG: Typing X-ray read date: '{xray_read_date}'")
                        page.type(xray_read_date_input, xray_read_date, delay=50)
                        print(f"DEBUG: Typed X-ray read date successfully")
                        
                        time.sleep(0.3)
                        
                        # Click the matching date in dropdown or just close it
                        try:
                            dropdown_option = f"span[role='listbox'] >> text='{xray_read_date}'"
                            page.wait_for_selector(dropdown_option, state="visible", timeout=1000)
                            page.click(dropdown_option, timeout=1000)
                            print(f"DEBUG: Clicked X-ray read date dropdown option: '{xray_read_date}'")
                        except Exception:
                            page.keyboard.press("Escape")
                            print(f"DEBUG: Pressed Escape to close dropdown")
                        
                        time.sleep(0.3)
                        print(f"DEBUG: X-ray read date entry complete")
                    except Exception as e:
                        print(f"DEBUG: Error filling X-ray read date: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Select chest X-ray result (Normal/Abnormal)
                xray_result_raw = getattr(form_data.examination, 'chest_xray_result', None)
                if xray_result_raw:
                    xray_result = str(xray_result_raw).strip().upper() if xray_result_raw else ""
                else:
                    xray_result = ""
                
                print(f"DEBUG: chest_xray_result from form = '{xray_result}'")
                
                if xray_result:
                    try:
                        import datetime
                        xray_result_radio_name = PAGE9_EXAM_DATE["xray_result_radio_name"]
                        xray_result_values = PAGE9_EXAM_DATE["xray_result_values"]
                        
                        # Map I-693 value to eMedical value
                        if xray_result in xray_result_values:
                            result_value = xray_result_values[xray_result]
                            result_radio = f"input[name='{xray_result_radio_name}'][value='{result_value}']"
                            print(f"DEBUG: Mapped to xray_result_value = '{result_value}'")
                            
                            print(f"DEBUG: [{datetime.datetime.now().strftime('%H:%M:%S')}] Waiting for X-ray result selector...")
                            page.wait_for_selector(result_radio, state="visible", timeout=5000)
                            print(f"DEBUG: [{datetime.datetime.now().strftime('%H:%M:%S')}] Found selector, clicking...")
                            page.click(result_radio, force=True)
                            print(f"DEBUG: [{datetime.datetime.now().strftime('%H:%M:%S')}] Clicked X-ray result radio: {result_value}")
                            time.sleep(0.5)
                            
                            # If Abnormal was selected, check the specific abnormal findings checkboxes
                            if result_value == "ABN":
                                self._fill_xray_abnormal_findings(page, form_data)
                        else:
                            print(f"DEBUG: Unknown xray_result value: '{xray_result}'")
                    except Exception as e:
                        print(f"DEBUG: Error selecting X-ray result: {e}")
                        import traceback
                        traceback.print_exc()
        except Exception as e:
            print(f"DEBUG: Error selecting chest X-ray requirement: {e}")
            import traceback
            traceback.print_exc()
        
        # === Sputum Smears Radio Button (Part 8.1.A(4)) ===
        try:
            sputum_indicated = getattr(form_data.examination, 'sputum_indicated', None)
            if sputum_indicated:
                sputum_indicated = str(sputum_indicated).strip().upper()
            else:
                sputum_indicated = ""
            
            print(f"DEBUG: sputum_indicated from form = '{sputum_indicated}'")
            
            if sputum_indicated:
                sputum_radio_name = PAGE9_EXAM_DATE["sputum_radio_name"]
                sputum_values = PAGE9_EXAM_DATE["sputum_values"]
                
                if sputum_indicated in sputum_values:
                    sputum_value = sputum_values[sputum_indicated]
                    sputum_radio = f"input[name='{sputum_radio_name}'][value='{sputum_value}']"
                    print(f"DEBUG: Mapped to sputum_value = '{sputum_value}'")
                    
                    page.wait_for_selector(sputum_radio, state="visible", timeout=5000)
                    page.click(sputum_radio, force=True)
                    print(f"DEBUG: Clicked sputum smears radio: {sputum_value}")
                    time.sleep(0.5)
                    
                    # === Sputum Reason Checkboxes (shown after selecting "Indicated") ===
                    if sputum_value == "IND":
                        time.sleep(1.0)  # Wait for reason checkboxes and result fields to appear
                        
                        # Sputum reason label text as shown on the eMedical page (partial match)
                        SPUTUM_REASON_LABELS = {
                            'signs_symptoms': "sign or symptoms of tb",
                            'chest_xray':     "chest x-ray suggestive of tb",
                            'hiv_extrapulm':  "known hiv infection or extrapulmonary",
                            'end_treatment':  "end of treatment cultures",
                        }
                        
                        # First, uncheck all sputum reason checkboxes by label text
                        # Using get_by_label avoids touching X-ray reason checkboxes
                        # that share similar wording in a different section.
                        for label_text in SPUTUM_REASON_LABELS.values():
                            try:
                                cb = page.get_by_label(label_text, exact=False)
                                if cb.count() > 0 and cb.first.is_checked():
                                    cb.first.click()
                                    print(f"DEBUG: Unchecked sputum reason checkbox: '{label_text}'")
                                    time.sleep(0.1)
                            except Exception:
                                pass
                        
                        # Determine correct sputum reason from I-693 data
                        if getattr(form_data.examination, 'sputum_chest_xray', '') == 'Yes':
                            reason_key = 'chest_xray'
                            sputum_reason_label = "Chest X-ray suggestive of TB"
                        elif getattr(form_data.examination, 'sputum_hiv_extrapulm', '') == 'Yes':
                            reason_key = 'hiv_extrapulm'
                            sputum_reason_label = "HIV infection or extrapulmonary TB"
                        elif getattr(form_data.examination, 'sputum_end_treatment', '') == 'Yes':
                            reason_key = 'end_treatment'
                            sputum_reason_label = "End of treatment cultures"
                        elif getattr(form_data.examination, 'sputum_signs_symptoms', '') == 'Yes':
                            reason_key = 'signs_symptoms'
                            sputum_reason_label = "Signs or symptoms of TB"
                        else:
                            reason_key = 'signs_symptoms'
                            sputum_reason_label = "Signs or symptoms of TB (default)"
                        
                        label_text = SPUTUM_REASON_LABELS[reason_key]
                        try:
                            cb = page.get_by_label(label_text, exact=False)
                            cb.first.wait_for(state="visible", timeout=5000)
                            if not cb.first.is_checked():
                                cb.first.click()
                                print(f"DEBUG: Checked sputum reason: '{sputum_reason_label}'")
                            else:
                                print(f"DEBUG: Sputum reason already checked: '{sputum_reason_label}'")
                            time.sleep(0.3)
                        except Exception as e:
                            print(f"DEBUG: Error selecting sputum reason checkbox (label='{label_text}'): {e}")
                        
                        # === Sputum Smear Results (Part 8.1.A(5)(a)) ===
                        self._fill_sputum_smear_rows(page, form_data)
                        self._fill_sputum_culture_rows(page, form_data)
                else:
                    print(f"DEBUG: Unknown sputum_indicated value: '{sputum_indicated}'")
        except Exception as e:
            print(f"DEBUG: Error selecting sputum smears: {e}")
            import traceback
            traceback.print_exc()
        
        # === TB Classification Checkbox (Part 8.1.A(6)) ===
        # Only ONE checkbox should be selected - uncheck others first
        try:
            tb_classification = getattr(form_data.examination, 'tb_classification', None)
            if tb_classification:
                tb_classification = str(tb_classification).strip().upper()
            else:
                tb_classification = ""
            
            print(f"DEBUG: tb_classification from form = '{tb_classification}'")
            
            if tb_classification:
                tb_checkboxes = PAGE9_EXAM_DATE["tb_classification_checkboxes"]
                
                if tb_classification in tb_checkboxes:
                    target_selector = tb_checkboxes[tb_classification]
                    print(f"DEBUG: TB classification target checkbox = '{target_selector}'")
                    
                    # First, uncheck any other checkboxes that are already checked
                    for class_code, checkbox_selector in tb_checkboxes.items():
                        if class_code != tb_classification:
                            try:
                                if page.is_checked(checkbox_selector):
                                    page.click(checkbox_selector, force=True)
                                    print(f"DEBUG: Unchecked TB classification: {class_code}")
                                    time.sleep(0.2)
                            except Exception:
                                pass  # Checkbox might not be visible yet
                    
                    # Now check the correct one if not already checked
                    page.wait_for_selector(target_selector, state="visible", timeout=5000)
                    if not page.is_checked(target_selector):
                        page.click(target_selector, force=True)
                        print(f"DEBUG: Clicked TB classification checkbox: {tb_classification}")
                    else:
                        print(f"DEBUG: TB classification checkbox already checked: {tb_classification}")
                    time.sleep(0.5)
                else:
                    print(f"DEBUG: Unknown tb_classification value: '{tb_classification}'")
        except Exception as e:
            print(f"DEBUG: Error selecting TB classification: {e}")
            import traceback
            traceback.print_exc()
        
        # Fill TB remarks textarea (I-693 Part 8 A.(7)) if present
        try:
            remarks_textarea = PAGE9_EXAM_DATE.get("remarks_textarea")
            tb_remarks = (form_data.examination.tb_remarks or "").strip()
            if remarks_textarea and tb_remarks:
                page.wait_for_selector(remarks_textarea, state="visible", timeout=5000)
                page.click(remarks_textarea)
                time.sleep(0.1)
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                page.keyboard.type(tb_remarks, delay=15)
                page.keyboard.press("Tab")
                time.sleep(0.3)
                print(f"DEBUG: Filled TB remarks textarea with {len(tb_remarks)} chars")
            elif remarks_textarea and not tb_remarks:
                print("DEBUG: TB remarks textarea found but I-693 Part 8 A.(7) is empty - skipping")
            elif tb_remarks:
                print(f"DEBUG: TB remarks textarea not discovered but field has content: '{tb_remarks[:40]}...'")
        except Exception as e:
            print(f"DEBUG: Could not fill TB remarks textarea: {e}")

        print(f"DEBUG: Page 9 complete")
    
    def _fill_xray_abnormal_findings(self, page: Page, form_data: I693Form) -> None:
        """
        Check the abnormal findings checkboxes on the eMedical page.
        Called after selecting "ABN" for the X-ray result radio button.
        
        Maps I-693 abnormality checkboxes to eMedical checkboxes.
        
        NOTE: The I-693 PDF uses non-standard export values for these checkboxes
        (e.g. 'Infiltrate', 'Discrete#20Nodule', 'B', 'C', etc.) which are NOT
        in CHECKBOX_TRUE_VALUES. Instead, any non-empty, non-'Off' value means
        the checkbox is selected.
        
        Args:
            page: Browser page
            form_data: Extracted I-693 data
        """
        abnormal_findings_map = PAGE9_EXAM_DATE.get("xray_abnormal_findings", {})
        if not abnormal_findings_map:
            print("DEBUG: No xray_abnormal_findings mapping found in PAGE9_EXAM_DATE")
            return
        
        print(f"DEBUG: Checking abnormal findings checkboxes...")
        
        # Wait for abnormal findings checkboxes to appear after ABN radio is clicked
        # Try the first selector to confirm the section is visible
        first_selector = list(abnormal_findings_map.values())[0]
        try:
            page.wait_for_selector(first_selector, state="visible", timeout=5000)
        except Exception as e:
            print(f"DEBUG: Abnormal findings checkboxes not visible yet: {e}")
            time.sleep(1)
        
        checked_count = 0
        for i693_field, emedical_selector in abnormal_findings_map.items():
            try:
                # Get the I-693 field value
                field_value = getattr(form_data.examination, i693_field, "") or ""
                
                # X-ray abnormality checkboxes use non-standard export values like
                # 'Infiltrate', 'Discrete#20Nodule', 'B', 'PE', etc.
                # Any non-empty, non-Off value means the checkbox IS checked.
                is_checked = bool(field_value and field_value.strip().lower() not in ('', 'off', 'no'))
                
                print(f"DEBUG: {i693_field} = {repr(field_value)} -> checked={is_checked}")
                
                if is_checked:
                    # Check this checkbox in eMedical
                    checkbox = page.query_selector(emedical_selector)
                    if checkbox:
                        if not checkbox.is_checked():
                            checkbox.click()
                            print(f"DEBUG: Checked abnormal finding: {i693_field} -> {emedical_selector}")
                        else:
                            print(f"DEBUG: Abnormal finding already checked: {i693_field}")
                        checked_count += 1
                        time.sleep(0.2)
                    else:
                        print(f"DEBUG: Could not find checkbox for {i693_field}: {emedical_selector}")
            except Exception as e:
                print(f"DEBUG: Error checking abnormal finding {i693_field}: {e}")
        
        print(f"DEBUG: Checked {checked_count} abnormal finding checkbox(es)")
    
    def _fill_sputum_date_field(self, page: Page, selector: str, date_value: str, label: str) -> None:
        """
        Fill a sputum date field (specimen or result date) using the same pattern
        as other date fields on page 9: type date, click dropdown, press Tab.
        
        Args:
            page: Browser page
            selector: CSS selector for the date input
            date_value: Raw date string from I-693
            label: Description for debug logging
        """
        if not date_value:
            return
        
        try:
            # Format the date to DD/MMM/YYYY if possible
            formatted = self._format_exam_date(str(date_value))
            
            page.wait_for_selector(selector, state="visible", timeout=5000)
            page.click(selector)
            time.sleep(0.2)
            
            page.fill(selector, "")
            page.type(selector, formatted, delay=50)
            print(f"DEBUG: Typed {label}: '{formatted}'")
            
            time.sleep(0.3)
            
            # Click dropdown option or close it
            try:
                dropdown_option = f"span[role='listbox'] >> text='{formatted}'"
                page.wait_for_selector(dropdown_option, state="visible", timeout=1000)
                page.click(dropdown_option, timeout=1000)
                print(f"DEBUG: Clicked {label} dropdown option: '{formatted}'")
            except Exception:
                page.keyboard.press("Escape")
                print(f"DEBUG: Pressed Escape to close {label} dropdown")
            
            time.sleep(0.3)
        except Exception as e:
            print(f"DEBUG: Error filling {label}: {e}")
    
    def _fill_sputum_dropdown(self, page: Page, selector: str, value: str, value_map: dict, label: str) -> None:
        """
        Select a sputum result from a dropdown (POS/NEG for smears, POS/NEG/NTM/CNTAMNTD for cultures).
        
        Args:
            page: Browser page
            selector: CSS selector for the dropdown
            value: Raw result value from I-693
            value_map: Mapping of I-693 values to eMedical dropdown values
            label: Description for debug logging
        """
        if not value:
            return
        
        mapped = value_map.get(value.strip().upper(), "")
        if not mapped:
            print(f"DEBUG: Unknown {label} value: '{value}'")
            return
        
        try:
            page.wait_for_selector(selector, state="visible", timeout=5000)
            page.select_option(selector, value=mapped)
            print(f"DEBUG: Selected {label}: '{mapped}'")
            time.sleep(0.3)
        except Exception as e:
            print(f"DEBUG: Error selecting {label}: {e}")
            import traceback
            traceback.print_exc()
    
    def _fill_sputum_smear_rows(self, page: Page, form_data: I693Form) -> None:
        """
        Fill sputum smear result rows (Part 8.1.A(5)(a)) on eMedical page 9.
        
        Each row has: specimen date, result date, result dropdown (POS/NEG).
        Only fills rows that have data in the form model.
        
        Args:
            page: Browser page
            form_data: Extracted I-693 data
        """
        print("DEBUG: === Filling Sputum Smear Results ===")
        
        smear_rows = PAGE9_EXAM_DATE.get("sputum_smear_rows", [])
        result_values = PAGE9_EXAM_DATE.get("sputum_smear_result_values", {})
        
        if not smear_rows:
            print("DEBUG: No sputum smear row selectors configured")
            return
        
        # Model fields for each row
        row_data = [
            {
                "specimen_date": getattr(form_data.examination, 'smear_specimen_date_1', ''),
                "result_date": getattr(form_data.examination, 'smear_result_date_1', ''),
                "result": getattr(form_data.examination, 'smear_result_1', ''),
            },
            {
                "specimen_date": getattr(form_data.examination, 'smear_specimen_date_2', ''),
                "result_date": getattr(form_data.examination, 'smear_result_date_2', ''),
                "result": getattr(form_data.examination, 'smear_result_2', ''),
            },
            {
                "specimen_date": getattr(form_data.examination, 'smear_specimen_date_3', ''),
                "result_date": getattr(form_data.examination, 'smear_result_date_3', ''),
                "result": getattr(form_data.examination, 'smear_result_3', ''),
            },
        ]
        
        for i, (selectors, data) in enumerate(zip(smear_rows, row_data)):
            row_num = i + 1
            has_data = any(data.values())
            if not has_data:
                print(f"DEBUG: Smear row {row_num}: no data, skipping")
                continue
            
            print(f"DEBUG: Filling smear row {row_num}...")
            self._fill_sputum_date_field(
                page, selectors["specimen_date"],
                data["specimen_date"], f"smear row {row_num} specimen date"
            )
            self._fill_sputum_date_field(
                page, selectors["result_date"],
                data["result_date"], f"smear row {row_num} result date"
            )
            self._fill_sputum_dropdown(
                page, selectors["result_dropdown"],
                data["result"], result_values, f"smear row {row_num} result"
            )
        
        print("DEBUG: Sputum smear results filling complete")
    
    def _fill_sputum_culture_rows(self, page: Page, form_data: I693Form) -> None:
        """
        Fill sputum culture result rows (Part 8.1.A(5)(b)) on eMedical page 9.
        
        Each row has: specimen date, result date, result dropdown (NEG/POS/NTM/CNTAMNTD).
        Only fills rows that have data in the form model.
        
        Args:
            page: Browser page
            form_data: Extracted I-693 data
        """
        print("DEBUG: === Filling Sputum Culture Results ===")
        
        culture_rows = PAGE9_EXAM_DATE.get("sputum_culture_rows", [])
        result_values = PAGE9_EXAM_DATE.get("sputum_culture_result_values", {})
        
        if not culture_rows:
            print("DEBUG: No sputum culture row selectors configured")
            return
        
        # Model fields for each row
        row_data = [
            {
                "specimen_date": getattr(form_data.examination, 'culture_specimen_date_1', ''),
                "result_date": getattr(form_data.examination, 'culture_result_date_1', ''),
                "result": getattr(form_data.examination, 'culture_result_1', ''),
            },
            {
                "specimen_date": getattr(form_data.examination, 'culture_specimen_date_2', ''),
                "result_date": getattr(form_data.examination, 'culture_result_date_2', ''),
                "result": getattr(form_data.examination, 'culture_result_2', ''),
            },
            {
                "specimen_date": getattr(form_data.examination, 'culture_specimen_date_3', ''),
                "result_date": getattr(form_data.examination, 'culture_result_date_3', ''),
                "result": getattr(form_data.examination, 'culture_result_3', ''),
            },
        ]
        
        for i, (selectors, data) in enumerate(zip(culture_rows, row_data)):
            row_num = i + 1
            has_data = any(data.values())
            if not has_data:
                print(f"DEBUG: Culture row {row_num}: no data, skipping")
                continue
            
            print(f"DEBUG: Filling culture row {row_num}...")
            self._fill_sputum_date_field(
                page, selectors["specimen_date"],
                data["specimen_date"], f"culture row {row_num} specimen date"
            )
            self._fill_sputum_date_field(
                page, selectors["result_date"],
                data["result_date"], f"culture row {row_num} result date"
            )
            self._fill_sputum_dropdown(
                page, selectors["result_dropdown"],
                data["result"], result_values, f"culture row {row_num} result"
            )
        
        print("DEBUG: Sputum culture results filling complete")
    
    def _upload_documents(self, page: Page, patient_files: PatientFiles) -> None:
        """
        Upload the 3 required documents (I-693, Lab Results, Chest X-ray).
        
        Each upload requires:
        1. Click "Add New" button to open popup
        2. Select document type from dropdown
        3. Upload file via file input (using file chooser interception)
        4. Wait for upload to complete
        
        Args:
            page: Browser page
            patient_files: PatientFiles containing paths to the 3 documents
        """
        from src.automation.field_map_emedical import PAGE9_FILE_UPLOADS
        
        # Define the 3 uploads: (document_type_key, file_path, display_name)
        # I-693 is uploaded last because it is the largest file and slowest to process.
        uploads = [
            ("lab_results", patient_files.lab_results_path, "Lab Results (TST/IGRA)"),
            ("chest_xray", patient_files.chest_xray_path, "Chest X-ray"),
            ("i693", patient_files.i693_path, "I-693 Form"),
        ]
        
        add_new_button = PAGE9_FILE_UPLOADS["add_new_button"]
        doc_type_dropdown = PAGE9_FILE_UPLOADS["document_type_dropdown"]
        file_input = PAGE9_FILE_UPLOADS["file_input"]
        doc_types = PAGE9_FILE_UPLOADS["document_types"]
        
        for doc_type_key, file_path, display_name in uploads:
            try:
                print(f"DEBUG: Uploading {display_name}: {file_path}")
                
                # Validate file exists
                if not file_path or not file_path.exists():
                    print(f"DEBUG: ERROR - File not found: {file_path}")
                    continue
                
                # Step 1: Click "Add New" button to open popup
                page.wait_for_selector(add_new_button, state="visible", timeout=10000)
                page.click(add_new_button)
                time.sleep(1.5)  # Wait for popup to fully open
                print(f"DEBUG: Clicked Add New button")
                
                # Discover upload popup selectors dynamically
                discover_page9_upload_popup_selectors(page)
                
                # Step 2: Select document type from dropdown
                page.wait_for_selector(doc_type_dropdown, state="visible", timeout=5000)
                doc_type_value = doc_types.get(doc_type_key, "OTHR")
                page.select_option(doc_type_dropdown, value=doc_type_value)
                time.sleep(0.5)
                print(f"DEBUG: Selected document type: {doc_type_value}")
                
                # Step 3: Upload file using file chooser interception (works in background!)
                print(f"DEBUG: Uploading file: {file_path}")
                file_uploaded = False
                
                # METHOD 1: File Chooser Interception (BEST - works in background with CDP)
                # This intercepts the native file dialog before it opens
                print(f"DEBUG: Method 1 - Using file chooser interception...")
                try:
                    # Set up a listener for file chooser BEFORE clicking the input
                    with page.expect_file_chooser(timeout=10000) as fc_info:
                        # Click the file input to trigger file chooser
                        page.click(file_input, force=True)
                    
                    # Get the file chooser and set the file
                    file_chooser = fc_info.value
                    file_chooser.set_files(str(file_path))
                    print(f"DEBUG: Method 1 SUCCESS - file set via file chooser interception")
                    file_uploaded = True
                    time.sleep(1.5)
                except Exception as e1:
                    print(f"DEBUG: Method 1 failed: {e1}")
                
                # METHOD 2: Try Playwright's set_input_files directly
                if not file_uploaded:
                    print(f"DEBUG: Method 2 - Trying Playwright set_input_files...")
                    try:
                        # Wait for file input to be in DOM
                        page.wait_for_selector(file_input, state="attached", timeout=5000)
                        
                        # Try to set the file directly
                        page.set_input_files(file_input, str(file_path))
                        time.sleep(1.5)
                        
                        # Verify upload by checking if filename appears on page
                        filename = file_path.name
                        # Check for the filename in various possible locations
                        if (page.locator(f"text='{filename}'").first.is_visible(timeout=2000) or
                            page.locator(f"[title*='{filename}']").first.is_visible(timeout=500) or
                            page.locator(f"input[value*='{filename}']").first.is_visible(timeout=500)):
                            file_uploaded = True
                            print(f"DEBUG: Method 2 SUCCESS - file uploaded via set_input_files")
                    except Exception as e2:
                        print(f"DEBUG: Method 2 failed: {e2}")
                
                # METHOD 3: Use CDP Page.setInterceptFileChooserDialog for more control
                if not file_uploaded:
                    print(f"DEBUG: Method 3 - Using CDP setInterceptFileChooserDialog...")
                    try:
                        # Get the CDP session for low-level control
                        client = page.context.new_cdp_session(page)
                        
                        # Enable file chooser interception via CDP
                        client.send("Page.setInterceptFileChooserDialog", {"enabled": True})
                        
                        # Click the file input
                        page.click(file_input, force=True)
                        time.sleep(0.5)
                        
                        # The file chooser should be intercepted, now we need to handle it
                        # Use CDP to handle the file
                        # Get DOM node for the input
                        js_get_node = """
                        (selector) => {
                            const el = document.querySelector(selector);
                            return el ? true : false;
                        }
                        """
                        if page.evaluate(js_get_node, file_input):
                            # Use set_input_files now that dialog is intercepted
                            page.set_input_files(file_input, str(file_path))
                            file_uploaded = True
                            print(f"DEBUG: Method 3 SUCCESS - file uploaded via CDP interception")
                        
                        # Disable interception
                        client.send("Page.setInterceptFileChooserDialog", {"enabled": False})
                        time.sleep(1.5)
                    except Exception as e3:
                        print(f"DEBUG: Method 3 failed: {e3}")
                
                # METHOD 4: Bring window to front briefly for pyautogui (last resort)
                if not file_uploaded:
                    print(f"DEBUG: Method 4 - Using pyautogui with window focus (last resort)...")
                    max_retries = 3
                    
                    for attempt in range(max_retries):
                        if file_uploaded:
                            break
                        
                        if attempt > 0:
                            print(f"DEBUG: Retry attempt {attempt + 1}/{max_retries}")
                            time.sleep(1)
                        
                        try:
                            import pyautogui
                            import pyperclip
                            import pygetwindow as gw
                            
                            # FIRST: Bring browser window to front
                            print(f"DEBUG: Bringing browser window to front...")
                            try:
                                # Find Chrome windows
                                chrome_windows = gw.getWindowsWithTitle('Chrome') + gw.getWindowsWithTitle('eMedical')
                                if chrome_windows:
                                    for win in chrome_windows:
                                        if 'emedical' in win.title.lower() or 'chrome' in win.title.lower():
                                            win.activate()
                                            time.sleep(0.5)
                                            print(f"DEBUG: Focused browser window: {win.title}")
                                            break
                            except Exception as focus_browser_err:
                                print(f"DEBUG: Could not focus browser: {focus_browser_err}")
                            
                            # Wait for file input to be ready
                            file_input_element = page.locator(file_input)
                            file_input_element.wait_for(state="visible", timeout=5000)
                            
                            # Click the file input to open native file dialog
                            page.click(file_input, force=True)
                            print(f"DEBUG: Clicked file input, waiting for dialog to open...")
                            
                            # Wait progressively longer for native dialog to fully open
                            dialog_wait = 3 + attempt  # 3s, 4s, 5s on retries
                            time.sleep(dialog_wait)
                            
                            # Try to find and focus the file dialog window
                            dialog_focused = False
                            try:
                                for title in ['Open', 'Choose File', 'Select file', 'File Upload']:
                                    dialogs = gw.getWindowsWithTitle(title)
                                    if dialogs:
                                        dialog = dialogs[0]
                                        dialog.activate()
                                        dialog.maximize()
                                        print(f"DEBUG: Focused dialog window: {dialog.title}")
                                        time.sleep(0.8)
                                        dialog_focused = True
                                        break
                            except Exception as focus_err:
                                print(f"DEBUG: Could not focus dialog: {focus_err}")
                            
                            if not dialog_focused and attempt < max_retries - 1:
                                print(f"DEBUG: Dialog not found, pressing Escape and retrying...")
                                pyautogui.press('escape')
                                time.sleep(1)
                                continue
                            
                            # Copy file path to clipboard
                            file_path_str = str(file_path)
                            pyperclip.copy(file_path_str)
                            print(f"DEBUG: Copied to clipboard: {file_path_str}")
                            
                            # Paste and confirm
                            time.sleep(0.3)
                            pyautogui.hotkey('ctrl', 'a')
                            time.sleep(0.3)
                            pyautogui.hotkey('ctrl', 'v')
                            print(f"DEBUG: Pasted file path via Ctrl+V")
                            time.sleep(0.8)
                            
                            pyautogui.press('enter')
                            print(f"DEBUG: Pressed Enter to confirm")
                            time.sleep(2.5)
                            
                            # Verify dialog closed
                            remaining_dialogs = gw.getWindowsWithTitle('Open')
                            if remaining_dialogs:
                                print(f"DEBUG: Dialog still open, pressing Enter again...")
                                pyautogui.press('enter')
                                time.sleep(2)
                            
                            file_uploaded = True
                            print(f"DEBUG: Method 4 SUCCESS - file uploaded via pyautogui")
                            
                        except ImportError as ie:
                            print(f"DEBUG: pyautogui/pyperclip not installed: {ie}")
                            break
                        except Exception as e:
                            print(f"DEBUG: Method 4 attempt {attempt + 1} failed: {e}")
                            if attempt == max_retries - 1:
                                import traceback
                                traceback.print_exc()
                
                # Wait for upload to process - use configured wait times
                wait_times = PAGE9_FILE_UPLOADS.get("wait_times", {})
                wait_time = wait_times.get(doc_type_key, 10)  # Default to 10 seconds
                print(f"DEBUG: Waiting {wait_time} seconds for file upload to complete...")
                time.sleep(wait_time)
                
                # Step 4: If this is an "Other" document type, fill in the description
                descriptions = PAGE9_FILE_UPLOADS.get("descriptions", {})
                if doc_type_key in descriptions:
                    description_text = descriptions[doc_type_key]
                    description_textarea = PAGE9_FILE_UPLOADS.get("description_textarea")
                    if description_textarea:
                        try:
                            page.wait_for_selector(description_textarea, state="visible", timeout=3000)
                            page.fill(description_textarea, description_text)
                            print(f"DEBUG: Filled description: {description_text}")
                            time.sleep(0.5)
                        except Exception as desc_err:
                            print(f"DEBUG: Could not fill description (may not be visible): {desc_err}")
                
                # Step 5: Click the Save button to close the popup
                # Use retry logic with JS fallback — CDP reconnections can
                # cause regular clicks to fire without visible effect.
                save_button = PAGE9_FILE_UPLOADS["save_button"]
                popup_closed = False
                
                for save_attempt in range(3):
                    if popup_closed:
                        break
                    
                    if save_attempt > 0:
                        print(f"DEBUG: Save button retry attempt {save_attempt + 1}/3")
                        time.sleep(1.5)
                    
                    # Wait for save button to be visible
                    try:
                        page.wait_for_selector(save_button, state="visible", timeout=5000)
                    except Exception:
                        print(f"DEBUG: Save button not visible, skipping attempt")
                        continue
                    
                    # Wait for the button to be enabled (not disabled).
                    # Use a long timeout so slow uploads (e.g. large I-693) are not cut short.
                    try:
                        page.wait_for_function(
                            f"""() => {{
                                const btn = document.querySelector('{save_button}');
                                return btn && !btn.disabled;
                            }}""",
                            timeout=120000
                        )
                        print(f"DEBUG: Save button is enabled")
                    except Exception:
                        print(f"DEBUG: Save button may be disabled, trying click anyway")
                    
                    time.sleep(0.5)
                    
                    # Attempt 1: Normal Playwright click
                    if save_attempt == 0:
                        try:
                            page.click(save_button)
                            print(f"DEBUG: Clicked Save button (normal click)")
                        except Exception as click_err:
                            print(f"DEBUG: Normal click failed: {click_err}")
                    # Attempt 2+: JavaScript click (more reliable over CDP)
                    else:
                        try:
                            page.evaluate(f"""() => {{
                                const btn = document.querySelector('{save_button}');
                                if (btn) {{ btn.click(); }}
                            }}""")
                            print(f"DEBUG: Clicked Save button (JS click)")
                        except Exception as js_err:
                            print(f"DEBUG: JS click failed: {js_err}")
                    
                    # Verify popup actually closed
                    try:
                        page.wait_for_selector(save_button, state="hidden", timeout=8000)
                        popup_closed = True
                        print(f"DEBUG: Popup closed")
                    except Exception:
                        print(f"DEBUG: Popup still open after click attempt {save_attempt + 1}")
                
                if not popup_closed:
                    # Last resort: force click and continue
                    print(f"DEBUG: All save attempts failed — trying force click")
                    try:
                        page.click(save_button, force=True)
                        time.sleep(3)
                    except Exception:
                        pass
                    print(f"DEBUG: Proceeding despite popup state")
                
                # Wait for modal overlay (wc-shim) to disappear before next upload
                # This overlay intercepts clicks if we proceed too quickly
                try:
                    page.wait_for_selector("#wc-shim", state="hidden", timeout=10000)
                    print(f"DEBUG: Modal overlay cleared")
                except Exception:
                    # Overlay might not exist, continue anyway
                    time.sleep(2)
                    print(f"DEBUG: Waited for overlay to clear (fallback)")
                
                print(f"DEBUG: Completed upload for {display_name}")
                time.sleep(1)  # Brief pause before next upload
                
            except Exception as e:
                print(f"DEBUG: Error uploading {display_name}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"DEBUG: Document uploads complete")
    
    def _format_exam_date(self, date_str: str) -> str:
        """
        Convert exam date to DD/MMM/YYYY format.
        
        Args:
            date_str: Date string from I-693 (various formats)
            
        Returns:
            Date formatted as DD/MMM/YYYY (e.g., 01/Nov/2025)
        """
        from datetime import datetime
        
        # Month abbreviation mapping
        month_abbr = {
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
        }
        
        # Try common date formats from PDF
        formats_to_try = [
            "%Y-%m-%d",      # 2025-11-01 (ISO format - most likely from PDF)
            "%m/%d/%Y",      # 12/05/2025
            "%d/%m/%Y",      # 05/12/2025
            "%m-%d-%Y",      # 12-05-2025
            "%B %d, %Y",     # December 05, 2025
            "%b %d, %Y",     # Dec 05, 2025
            "%d %B %Y",      # 05 December 2025
            "%d %b %Y",      # 05 Dec 2025
        ]
        
        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                # Format as DD/MMM/YYYY
                result = f"{dt.day:02d}/{month_abbr[dt.month]}/{dt.year}"
                print(f"DEBUG: Parsed '{date_str}' with format '{fmt}' -> '{result}'")
                return result
            except ValueError:
                continue
        
        print(f"DEBUG: Could not parse date '{date_str}', returning as-is")
        # If already in correct format or can't parse, return as-is
        return date_str
    
    def _click_next(self, page: Page, page_num: int) -> None:
        """
        Click the next/submit button to advance to the next page.
        
        Args:
            page: Browser page
            page_num: Current page number
        """
        button_key = f"page{page_num}_next"
        selector = PAGE_NAVIGATION.get(button_key, "#nextBtn")

        # Capture a marker that should disappear after navigation so we can
        # detect a no-op click (e.g. validation failure leaving us on the
        # same page). For page 4, the photo-description textarea is a good
        # marker - it only exists on page 4.
        page_markers = {
            4: "#pre_exam-manage_photo-_0b0e1b_input",
        }
        marker = page_markers.get(page_num)

        # Wait for the eMedical loading shim to clear before clicking.
        # The shim (#wc-shim) intercepts pointer events while the page is
        # processing; clicking while it's present causes a 30-second timeout.
        try:
            page.wait_for_selector("#wc-shim", state="hidden", timeout=15000)
        except Exception:
            # Shim didn't disappear in time — try a JavaScript click to bypass it
            print(f"DEBUG: wc-shim still present before page {page_num} Next click; using JS click")
            page.evaluate(f"document.querySelector('{selector}')?.click()")
            page.wait_for_load_state("networkidle")
            return

        page.click(selector)
        page.wait_for_load_state("networkidle")

        # Handle any confirmation modals
        ok_modal_key = f"page{page_num}_ok_modal"
        if ok_modal_key in PAGE_NAVIGATION:
            try:
                modal_selector = PAGE_NAVIGATION[ok_modal_key]
                page.click(modal_selector, timeout=2000)
                page.wait_for_load_state("networkidle")
            except Exception:
                pass  # Modal didn't appear, continue

        # If we have a marker, verify navigation actually happened. If the
        # marker is still in the DOM, the page didn't advance (likely a
        # validation error). Try one re-click after a short delay.
        if marker:
            try:
                page.wait_for_selector(marker, state="detached", timeout=3000)
            except Exception:
                print(f"DEBUG: Page {page_num} did not advance after Next; "
                      f"re-clicking")
                try:
                    page.click(selector)
                    page.wait_for_load_state("networkidle")
                    page.wait_for_selector(marker, state="detached", timeout=5000)
                    print(f"DEBUG: Page {page_num} advanced after retry")
                except Exception as e:
                    print(f"DEBUG: Page {page_num} still has not advanced: {e}")

        time.sleep(0.5)
    
    def _upload_files(self, page: Page, patient: PatientFiles) -> None:
        """
        Upload I-693, lab results, and chest x-ray files.
        Now uses the _upload_documents method with the correct Page 9 selectors.
        
        Args:
            page: Browser page
            patient: Patient files
        """
        self._upload_documents(page, patient)
        
        # STOP HERE - Do NOT click final submit
        # User will review uploads and click submit manually
    
    def _update_status(
        self, 
        patient_name: str, 
        status: str, 
        current_page: int = 0,
        error_message: str = ""
    ) -> None:
        """Send status update via callback."""
        if self.on_status_update:
            self.on_status_update(
                patient_name,
                PatientStatus(
                    patient_name=patient_name,
                    status=status,
                    current_page=current_page,
                    error_message=error_message
                )
            )
    
    def upload_documents_only(self, patient: PatientFiles) -> None:
        """
        Connect to an existing Chrome browser and upload documents for a patient.
        
        Used when the user is already on the last page and the automated upload
        timed out or failed. Reconnects via CDP and re-runs the upload step.
        
        Args:
            patient: PatientFiles with paths to I-693, lab results, and chest x-ray
        """
        # Reset browser manager for the new thread
        reset_browser_manager(close_browser=False)
        self.browser_manager = get_browser_manager()
        
        try:
            page = self.browser_manager.connect_to_existing()
            print(f"DEBUG: Connected to existing browser for upload. Page URL: {page.url}")
        except Exception as e:
            self._show_connect_error_dialog(str(e))
            raise ConnectionError(f"Could not connect to browser: {e}") from e
        
        # Bring the tab to front so CDP interactions target the visible page
        try:
            page.bring_to_front()
            time.sleep(1)
            print(f"DEBUG: Brought page to front")
        except Exception as e:
            print(f"DEBUG: Could not bring page to front (non-critical): {e}")
        
        print(f"DEBUG: Starting document upload for {patient.patient_name}")
        self._upload_documents(page, patient)
        print(f"DEBUG: Document upload complete for {patient.patient_name}")

    def close(self) -> None:
        """Close browser and cleanup."""
        self.browser_manager.close_all()
