"""eMedical automation - main automation controller."""

import time
import tkinter as tk
from tkinter import messagebox
from datetime import date
from pathlib import Path
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from playwright.sync_api import Page

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
from src.automation.browser import BrowserManager
from src.automation.field_map_emedical import (
    EMEDICAL_PAGES,
    PAGE_NAVIGATION,
    FILE_UPLOADS,
    get_page_fields,
    get_country_code,
    get_issuing_country_code,
    get_state_code,
    PAGE3_ADDRESS_POPUP,
    PAGE3_PHONE_POPUP,
    PAGE5_IDENTITY,
    PAGE6_START_EXAMS,
    PAGE7_SELECTIVE_TB,
    PAGE8_VIEW_EXAM,
    PAGE9_EXAM_DATE,
)


class EMedicalAutomation:
    """
    Automates data entry into the eMedical portal.
    
    Opens up to 10 concurrent browser tabs, fills forms, uploads files,
    and STOPS before final submit for user review.
    """
    
    def __init__(self):
        self.browser_manager = BrowserManager()
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
    
    def run_batch(
        self,
        patients: list[PatientFiles],
        credentials: Credentials,
        on_status_update: Optional[Callable[[str, PatientStatus], None]] = None
    ) -> None:
        """
        Process a batch of patients concurrently.
        
        Args:
            patients: List of PatientFiles to process (max 10)
            credentials: eMedical login credentials
            on_status_update: Callback for status updates
        """
        self.on_status_update = on_status_update
        patients = patients[:MAX_CONCURRENT_PATIENTS]
        
        try:
            # DEBUG MODE: Connect to existing browser if starting from page > 1
            # User must already be logged in and on the correct page
            # Start Chrome with: chrome.exe --remote-debugging-port=9222
            if DEBUG_START_PAGE > 1:
                print(f"DEBUG MODE: Starting from page {DEBUG_START_PAGE}")
                print("Connecting to existing Chrome browser on port 9222...")
                print("(Make sure Chrome was started with --remote-debugging-port=9222)")
                login_page = self.browser_manager.connect_to_existing()
                print(f"Connected! Found page: {login_page.url}")
                tabs = [login_page]  # Just use the existing page for debug mode
            else:
                # Normal mode: Start fresh browser and login
                self.browser_manager.start(headless=False)
                login_page = self.browser_manager.new_tab()
                self._login(login_page, credentials)
                
                # STEP 1: Open ALL tabs upfront BEFORE filling any data
                # This ensures each tab gets to the Case Search page before we start
                print(f"DEBUG: Opening {len(patients)} tabs for patients:")
                for idx, p in enumerate(patients):
                    print(f"  Patient {idx+1}: {p.patient_name} - I693: {p.i693_path}")
                
                tabs = [login_page]  # First tab is the login tab
                
                # Open additional tabs for patients 2, 3, etc.
                for i in range(1, len(patients)):
                    print(f"DEBUG: Opening tab for patient {i+1}...")
                    new_tab = self.browser_manager.new_tab()
                    self.browser_manager.navigate_to_emedical(new_tab)
                    time.sleep(2)  # Wait for page to load
                    
                    # Click "Case search" menu item to go to page 1
                    case_search_selector = "#appMenu-caseSearch_0-body"
                    try:
                        new_tab.wait_for_selector(case_search_selector, state="visible", timeout=10000)
                        new_tab.click(case_search_selector)
                        print(f"DEBUG: Clicked 'Case search' for patient {i+1} tab")
                        new_tab.wait_for_load_state("networkidle")
                        time.sleep(2)
                    except Exception as e:
                        print(f"DEBUG: Could not click Case search: {e}")
                        # Try alternative selectors
                        try:
                            alt_selector = "span:has-text('Case search')"
                            new_tab.click(alt_selector)
                            print(f"DEBUG: Clicked alternative 'Case search' selector")
                            new_tab.wait_for_load_state("networkidle")
                            time.sleep(2)
                        except Exception:
                            print(f"DEBUG: Alternative selector also failed")
                    
                    tabs.append(new_tab)
                    print(f"DEBUG: Tab {i+1} ready at: {new_tab.url}")
            
            # STEP 2: Process patients SEQUENTIALLY (Playwright sync API is not thread-safe)
            # Each patient runs to completion before the next starts
            # All tabs are already open, so user can see which patient is currently processing
            for i, patient in enumerate(patients):
                tab = tabs[i]
                patient_num = i + 1
                print(f"DEBUG: Processing patient {patient_num}/{len(patients)} ({patient.patient_name})")
                
                try:
                    self._update_status(patient.patient_name, "processing", current_page=0)
                    self._process_patient(tab, patient, start_page=DEBUG_START_PAGE)
                    self._update_status(patient.patient_name, "ready_for_review", current_page=10)
                    print(f"DEBUG: Completed patient {patient_num} ({patient.patient_name})")
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
            
            # Don't close browser - leave tabs open for user review and manual submit
            # User will close browser when done
            
        except Exception as e:
            # On critical error, still try to leave browser open
            raise e
    
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
    
    def _process_patient(self, page: Page, patient: PatientFiles, start_page: int = 1) -> None:
        """
        Process a single patient in a browser tab.
        
        Args:
            page: Browser page/tab
            patient: Patient data and files
            start_page: Page to start from (1-6). Use for debugging/resuming.
        """
        if not patient.i693_data:
            raise ValueError(f"No I-693 data for patient {patient.patient_name}")
        
        # Skip to start_page if not starting from beginning
        if start_page <= 1:
            # Navigate to case search/create page
            page.goto(EMEDICAL_BASE_URL)
            page.wait_for_load_state("networkidle")
            time.sleep(1)  # Reduced from 2 seconds
            
            # Click "Case search" menu item to get to Page 1
            case_search_selector = "#appMenu-caseSearch_0-body"
            try:
                print(f"DEBUG: Looking for Case search selector...")
                page.wait_for_selector(case_search_selector, state="visible", timeout=5000)
                page.click(case_search_selector)
                print(f"DEBUG: Clicked 'Case search' to go to Page 1")
                print(f"DEBUG: Waiting for page to load...")
                page.wait_for_load_state("networkidle")
                time.sleep(1)  # Reduced from 2 seconds
                print(f"DEBUG: Case search page loaded")
            except Exception as e:
                print(f"DEBUG: Could not click Case search (may already be on page): {e}")
            
            # Page 1: Search for existing case or create new
            print(f"DEBUG: Starting Page 1 - filling search fields...")
            self._update_status(patient.patient_name, "processing", current_page=1)
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
            page.wait_for_selector(create_case_button, state="visible", timeout=10000)
            page.click(create_case_button)
            print(f"DEBUG: Clicked Create Case button, loading Page 2...")
            page.wait_for_load_state("networkidle")
            time.sleep(0.5)  # Reduced from 1 second
            print(f"DEBUG: Page 2 loaded")
        
        if start_page <= 2:
            # Page 2: Fill form fields
            self._update_status(patient.patient_name, "processing", current_page=2)
            self._fill_page(page, 2, patient.i693_data)
            
            # Checkpoint: Pause for user verification before clicking Create
            if 2 in CHECKPOINT_PAGES:
                print("DEBUG: Checkpoint - pausing for user verification on Page 2")
                if not self._show_checkpoint_dialog(2, patient.patient_name):
                    print("DEBUG: User cancelled at Page 2 checkpoint")
                    self._update_status(patient.patient_name, "error", error="Cancelled by user at Page 2")
                    return
            
            # Click "Create" button to proceed to Page 3
            self._click_next(page, 2)
            print("DEBUG: Clicked 'Create' button on Page 2, proceeding to Page 3")
        
        if start_page <= 3:
            # Page 3: Special handling - address popup
            self._update_status(patient.patient_name, "processing", current_page=3)
            self._fill_page3_address(page, patient.i693_data)
            self._click_next(page, 3)
        
        if start_page <= 4:
            # Page 4: Click Next to continue
            self._update_status(patient.patient_name, "processing", current_page=4)
            self._click_next(page, 4)
        
        if start_page <= 5:
            # Page 5: Identity confirmation
            self._update_status(patient.patient_name, "processing", current_page=5)
            self._fill_page5_identity(page, patient.i693_data)
            
            # Checkpoint: Pause for user verification before clicking Next
            if 5 in CHECKPOINT_PAGES:
                print("DEBUG: Checkpoint - pausing for user verification on Page 5")
                if not self._show_checkpoint_dialog(5, patient.patient_name):
                    print("DEBUG: User cancelled at Page 5 checkpoint")
                    self._update_status(patient.patient_name, "error", error="Cancelled by user at Page 5")
                    return
            
            self._click_next(page, 5)
            print("DEBUG: Clicked 'Next' button on Page 5, proceeding to Page 6")
        
        if start_page <= 6:
            # Page 6: Click Start Exam(s) and handle confirmation dialog
            self._update_status(patient.patient_name, "processing", current_page=6)
            self._fill_page6_start_exams(page)
        
        if start_page <= 7:
            # Page 7: Click "Selective History and TB" section to expand
            self._update_status(patient.patient_name, "processing", current_page=7)
            self._fill_page7_selective_tb(page)
        
        if start_page <= 8:
            # Page 8: Click "View exam" button
            self._update_status(patient.patient_name, "processing", current_page=8)
            self._fill_page8_view_exam(page)
        
        if start_page <= 9:
            # Page 9: Enter exam date
            self._update_status(patient.patient_name, "processing", current_page=9)
            self._fill_page9_exam_date(page, patient.i693_data)
        
        # Upload files after Page 9 (works in both normal and debug mode)
        # Page 10: Upload files and STOP
        self._update_status(patient.patient_name, "processing", current_page=10)
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
        from src.automation.field_map_emedical import get_page5_issuing_country
        
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
                    value = get_page5_issuing_country(id_type, country_of_birth)
                    print(f"DEBUG: Issuing country - ID type: '{id_type}', Country of birth: '{country_of_birth}' -> '{value}'")
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
                    if value and value_map:
                        if value in value_map:
                            value = value_map[value]
                        elif field_config.get("fallback_value"):
                            # Use fallback (e.g., "Other" for unknown ID types)
                            print(f"Warning: '{value}' not found in value_map, using fallback")
                            value = field_config.get("fallback_value")
                    
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
    
    def _fill_page3_address(self, page: Page, form_data: I693Form) -> None:
        """
        Fill Page 3 address popup and phone popup.
        
        Page 3 requires clicking an add button to open a popup,
        then filling address fields, then adding phone number.
        
        Args:
            page: Browser page
            form_data: Extracted I-693 data
        """
        # === FIRST: Add Address ===
        # Click the add button (+ icon) to open the address popup
        add_button = PAGE3_ADDRESS_POPUP["add_button"]
        page.wait_for_selector(add_button, state="visible", timeout=10000)
        page.click(add_button)
        time.sleep(3)  # Wait for popup to fully load
        
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
        apt_number = form_data.applicant.apt_number or ""
        unit_type = form_data.applicant.unit_type or ""
        
        # Filter out checkbox values like "Yes", "On", "True" from apt_number
        # Note: "1" is NOT filtered - it's a valid apt/suite number
        if apt_number and apt_number.lower() not in ("yes", "on", "true"):
            # Build full unit string with prefix
            # unit_type from PDF checkbox is typically a number: 1=APT, 2=STE, 3=FLR
            # or could be the text itself
            unit_prefix = ""
            if unit_type:
                unit_type_lower = unit_type.lower().strip()
                if unit_type_lower in ("1", "apt", "apt.", "apartment"):
                    unit_prefix = "APT "
                elif unit_type_lower in ("2", "ste", "ste.", "suite"):
                    unit_prefix = "STE "
                elif unit_type_lower in ("3", "flr", "flr.", "floor"):
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
        
        # Fill country code (1 for US)
        country_code_input = PAGE3_PHONE_POPUP["country_code_input"]
        page.wait_for_selector(country_code_input, state="visible", timeout=5000)
        page.fill(country_code_input, "1")  # US country code
        time.sleep(0.3)
        
        # Fill phone number (digits only, no dashes or formatting)
        phone_input = PAGE3_PHONE_POPUP["phone_input"]
        phone = form_data.applicant.phone or ""
        if phone:
            # Strip all non-digit characters (dashes, spaces, parentheses, etc.)
            phone_digits = ''.join(c for c in phone if c.isdigit())
            page.fill(phone_input, phone_digits)
            time.sleep(0.3)
        
        # Click Save button to close popup and save phone
        phone_save_button = PAGE3_PHONE_POPUP["save_button"]
        page.wait_for_selector(phone_save_button, state="visible", timeout=5000)
        page.click(phone_save_button)
        page.wait_for_load_state("networkidle")
        time.sleep(1)
    
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
        
        # Always select "Yes" for identity document provided
        identity_yes = PAGE5_IDENTITY["identity_doc_provided_yes"]
        page.wait_for_selector(identity_yes, state="visible", timeout=10000)
        page.click(identity_yes)
        print(f"DEBUG: Clicked 'Yes' for identity document provided")
        time.sleep(1)  # Wait for extra fields to appear
        
        # Get ID type from I-693 Part 5.1
        id_type = form_data.applicant.id_type or ""
        country_of_birth = form_data.applicant.country_of_birth or ""
        print(f"DEBUG: ID type from I-693: '{id_type}', Country of birth: '{country_of_birth}'")
        
        # Fill ID Document Type dropdown
        id_type_dropdown = PAGE5_IDENTITY.get("id_doc_type_dropdown")
        if id_type_dropdown:
            id_type_code = get_page5_id_type_code(id_type)
            print(f"DEBUG: Mapped ID type '{id_type}' to code '{id_type_code}'")
            try:
                page.select_option(id_type_dropdown, value=id_type_code)
                print(f"DEBUG: Selected ID type in dropdown: {id_type_code}")
                time.sleep(0.5)
                
                # If "Other" (code 06) is selected, fill the text description field
                if id_type_code == "06":
                    other_id_input = PAGE5_IDENTITY.get("other_id_doc_input", "#pre_exam-confirm_identity-other_id_doc_input")
                    try:
                        page.wait_for_selector(other_id_input, state="visible", timeout=3000)
                        # Use the original ID type text from I-693 (uppercase)
                        other_id_text = id_type.upper().strip()
                        page.fill(other_id_input, other_id_text)
                        print(f"DEBUG: Filled 'Other' ID description with: '{other_id_text}'")
                        time.sleep(0.3)
                    except Exception as e:
                        print(f"DEBUG: Could not fill Other ID text field: {e}")
            except Exception as e:
                print(f"DEBUG: Could not select ID type dropdown: {e}")
        
        # Fill Issuing Country dropdown based on ID type rules
        issuing_country_dropdown = PAGE5_IDENTITY.get("issuing_country_dropdown")
        if issuing_country_dropdown:
            issuing_country_code = get_page5_issuing_country(id_type, country_of_birth)
            print(f"DEBUG: Issuing country code: '{issuing_country_code}' (based on ID type and country of birth)")
            try:
                page.select_option(issuing_country_dropdown, value=issuing_country_code)
                print(f"DEBUG: Selected issuing country in dropdown: {issuing_country_code}")
                time.sleep(0.5)
            except Exception as e:
                print(f"DEBUG: Could not select issuing country dropdown: {e}")
        
        # Always select "No" for identity concerns
        concerns_no = PAGE5_IDENTITY["identity_concerns_no"]
        page.wait_for_selector(concerns_no, state="visible", timeout=5000)
        page.click(concerns_no)
        print(f"DEBUG: Clicked 'No' for identity concerns")
        time.sleep(0.5)
    
    def _fill_page6_start_exams(self, page: Page) -> None:
        """
        Click Start Exam(s) button and handle the browser confirmation dialog.
        
        Args:
            page: Browser page
        """
        # Set up dialog handler to accept the confirmation
        def handle_dialog(dialog):
            dialog.accept()
        
        page.on("dialog", handle_dialog)
        
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
        # Based on IGRA result: Negative = not required, Positive/Indeterminate = required
        try:
            radio_name = PAGE9_EXAM_DATE["chest_xray_req_radio_name"]
            
            # Determine chest X-ray requirement based on IGRA result
            if igra_result_raw == "N":  # Negative
                xray_req_value = "N_REQ"  # Not required
                print(f"DEBUG: IGRA Negative - Chest X-ray NOT required")
            else:  # Positive or Indeterminate
                xray_req_value = "REQ"  # Required
                print(f"DEBUG: IGRA Positive/Indeterminate - Chest X-ray required")
            
            xray_req_radio = f"input[name='{radio_name}'][value='{xray_req_value}']"
            page.wait_for_selector(xray_req_radio, state="visible", timeout=5000)
            page.click(xray_req_radio, force=True)
            print(f"DEBUG: Clicked chest X-ray requirement radio: '{xray_req_value}'")
            time.sleep(0.3)
            
            # If chest X-ray is required, select the reason checkbox
            if xray_req_value == "REQ":
                # First, uncheck all reason checkboxes to ensure only one is selected
                reason_checkboxes = [
                    PAGE9_EXAM_DATE["xray_reason_initial_screening"],
                    PAGE9_EXAM_DATE["xray_reason_tb_signs"],
                    PAGE9_EXAM_DATE["xray_reason_igra_exception"],
                ]
                
                for checkbox_selector in reason_checkboxes:
                    try:
                        checkbox = page.query_selector(checkbox_selector)
                        if checkbox and checkbox.is_checked():
                            checkbox.click()
                            print(f"DEBUG: Unchecked existing checkbox: {checkbox_selector}")
                            time.sleep(0.1)
                    except Exception:
                        pass  # Checkbox may not be visible yet
                
                # Now check the correct one: "Initial screening results"
                xray_reason_checkbox = PAGE9_EXAM_DATE["xray_reason_initial_screening"]
                try:
                    page.wait_for_selector(xray_reason_checkbox, state="visible", timeout=5000)
                    checkbox = page.query_selector(xray_reason_checkbox)
                    if checkbox and not checkbox.is_checked():
                        checkbox.click()
                        print(f"DEBUG: Checked 'Initial screening results' as X-ray reason")
                    else:
                        print(f"DEBUG: 'Initial screening results' already checked")
                    time.sleep(0.3)
                except Exception as e:
                    print(f"DEBUG: Error selecting X-ray reason checkbox: {e}")
                
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
        
        print(f"DEBUG: Page 9 complete")
    
    def _upload_documents(self, page: Page, patient_files: PatientFiles) -> None:
        """
        Upload the 3 required documents (I-693, Lab Results, Chest X-ray).
        
        Each upload requires:
        1. Click "Add New" button to open popup
        2. Select document type from dropdown
        3. Upload file via file input
        4. Wait for upload to complete
        
        Args:
            page: Browser page
            patient_files: PatientFiles containing paths to the 3 documents
        """
        from src.automation.field_map_emedical import PAGE9_FILE_UPLOADS
        
        # Define the 3 uploads: (document_type_key, file_path, display_name)
        uploads = [
            ("i693", patient_files.i693_path, "I-693 Form"),
            ("lab_results", patient_files.lab_results_path, "Lab Results (TST/IGRA)"),
            ("chest_xray", patient_files.chest_xray_path, "Chest X-ray"),
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
                
                # Step 2: Select document type from dropdown
                page.wait_for_selector(doc_type_dropdown, state="visible", timeout=5000)
                doc_type_value = doc_types.get(doc_type_key, "OTHR")
                page.select_option(doc_type_dropdown, value=doc_type_value)
                time.sleep(0.5)
                print(f"DEBUG: Selected document type: {doc_type_value}")
                
                # Step 3: Upload file using pyautogui + clipboard (most reliable for CDP browsers)
                # set_input_files and file_chooser don't work reliably with CDP-connected browsers
                print(f"DEBUG: Uploading file via native dialog: {file_path}")
                file_uploaded = False
                max_retries = 3
                
                for attempt in range(max_retries):
                    if file_uploaded:
                        break
                    
                    if attempt > 0:
                        print(f"DEBUG: Retry attempt {attempt + 1}/{max_retries}")
                        time.sleep(1)
                    
                    # PRIMARY METHOD: Use pyautogui with clipboard to handle native file dialog
                    # This is the most reliable for CDP-connected browsers since set_input_files doesn't work
                    try:
                        import pyautogui
                        import pyperclip
                        import pygetwindow as gw
                        
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
                            # Look for Open dialog (Windows file picker)
                            for title in ['Open', 'Choose File', 'Select file', 'File Upload']:
                                dialogs = gw.getWindowsWithTitle(title)
                                if dialogs:
                                    dialog = dialogs[0]
                                    dialog.activate()
                                    dialog.maximize()  # Ensure dialog is visible
                                    print(f"DEBUG: Focused dialog window: {dialog.title}")
                                    time.sleep(0.8)
                                    dialog_focused = True
                                    break
                        except Exception as focus_err:
                            print(f"DEBUG: Could not focus dialog: {focus_err}")
                        
                        if not dialog_focused and attempt < max_retries - 1:
                            # Dialog didn't open, try pressing Escape and retry
                            print(f"DEBUG: Dialog not found, pressing Escape and retrying...")
                            pyautogui.press('escape')
                            time.sleep(1)
                            continue
                        
                        # Copy file path to clipboard (handles special chars, spaces, backslashes)
                        file_path_str = str(file_path)
                        pyperclip.copy(file_path_str)
                        print(f"DEBUG: Copied to clipboard: {file_path_str}")
                        
                        # Clear any existing text in filename field and paste
                        time.sleep(0.3)
                        pyautogui.hotkey('ctrl', 'a')  # Select all in filename field
                        time.sleep(0.3)
                        pyautogui.hotkey('ctrl', 'v')  # Paste the path
                        print(f"DEBUG: Pasted file path via Ctrl+V")
                        time.sleep(0.8)
                        
                        # Press Enter to confirm file selection (or click Open button)
                        pyautogui.press('enter')
                        print(f"DEBUG: Pressed Enter to confirm file selection")
                        time.sleep(2.5)  # Wait for file selection to process
                        
                        # Verify dialog closed by checking if any Open dialogs remain
                        remaining_dialogs = gw.getWindowsWithTitle('Open')
                        if remaining_dialogs:
                            print(f"DEBUG: Dialog still open, pressing Enter again...")
                            pyautogui.press('enter')
                            time.sleep(2)
                        
                        file_uploaded = True
                        print(f"DEBUG: File upload via pyautogui completed: {file_path}")
                        
                    except ImportError as ie:
                        print(f"DEBUG: pyautogui/pyperclip not installed: {ie}")
                        break  # No point retrying if modules aren't installed
                    except Exception as e:
                        print(f"DEBUG: pyautogui method failed on attempt {attempt + 1}: {e}")
                        if attempt == max_retries - 1:
                            import traceback
                            traceback.print_exc()
                
                # FALLBACK: Try Playwright's set_input_files if pyautogui failed
                if not file_uploaded:
                    print(f"DEBUG: Trying Playwright set_input_files as fallback...")
                    try:
                        page.set_input_files(file_input, str(file_path))
                        time.sleep(1)
                        
                        # Check if file was set
                        filename = file_path.name
                        if page.locator(f"text='{filename}'").is_visible(timeout=1000):
                            file_uploaded = True
                            print(f"DEBUG: Fallback worked - filename visible")
                    except Exception as e2:
                        print(f"DEBUG: Fallback set_input_files also failed: {e2}")
                
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
                save_button = PAGE9_FILE_UPLOADS["save_button"]
                page.wait_for_selector(save_button, state="visible", timeout=5000)
                page.click(save_button)
                print(f"DEBUG: Clicked Save button")
                
                # Wait for popup to fully close by waiting for save button to disappear
                try:
                    page.wait_for_selector(save_button, state="hidden", timeout=10000)
                    print(f"DEBUG: Popup closed")
                except Exception:
                    # Fallback: wait a bit longer if we can't detect popup closing
                    time.sleep(2)
                    print(f"DEBUG: Waited for popup to close (fallback)")
                
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
    
    def close(self) -> None:
        """Close browser and cleanup."""
        self.browser_manager.close_all()
