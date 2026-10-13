"""
Test script to verify login, page1, and page2 selectors work correctly.

This script will:
1. Open eMedical portal
2. Prompt you for credentials (not stored)
3. Attempt login
4. Fill page1 fields, click search/create
5. Fill page2 fields

Usage:
    python -m src.automation.test_selectors [path_to_i693_pdf]
"""

import json
import asyncio
import sys
import re
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

# Load selectors
SELECTORS_FILE = Path(__file__).parent / "discovered_selectors.json"
EMEDICAL_URL = "https://www.emedical.immi.gov.au/eMedUI/eMedical"


def load_selectors() -> dict:
    """Load selectors from JSON file."""
    with open(SELECTORS_FILE, 'r') as f:
        return json.load(f)


def convert_date_to_emedical_format(date_str: str) -> str:
    """
    Convert date to eMedical format: DD MMM YYYY (e.g., "01 Jan 1990")
    
    Handles various input formats:
    - MM/DD/YYYY
    - DD/MM/YYYY  
    - YYYY-MM-DD
    - Already in DD MMM YYYY format
    """
    if not date_str:
        return ""
    
    # Already in correct format?
    if re.match(r'^\d{2} [A-Za-z]{3} \d{4}$', date_str):
        return date_str
    
    # Try various date formats
    formats_to_try = [
        "%m/%d/%Y",   # MM/DD/YYYY (US format - most likely from I-693)
        "%d/%m/%Y",   # DD/MM/YYYY
        "%Y-%m-%d",   # YYYY-MM-DD (ISO)
        "%m-%d-%Y",   # MM-DD-YYYY
        "%d-%m-%Y",   # DD-MM-YYYY
    ]
    
    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d %b %Y")  # "01 Jan 1990"
        except ValueError:
            continue
    
    # If nothing worked, return original
    print(f"   ⚠️ Could not parse date: {date_str}")
    return date_str


def get_test_data(pdf_path: str = None) -> dict:
    """Get test data - either from PDF or use sample data."""
    if pdf_path:
        # Import and extract from PDF
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.parser.pdf_reader import extract_i693_data
        
        form_data = extract_i693_data(Path(pdf_path))
        return {
            "family_name": form_data.applicant.family_name,
            "given_name": form_data.applicant.given_name,
            "date_of_birth": form_data.applicant.date_of_birth,
            "id_number": form_data.applicant.id_number,
            "sex": form_data.applicant.sex,
            "country_of_birth": form_data.applicant.country_of_birth,
        }
    else:
        # Sample test data
        return {
            "family_name": "TEST",
            "given_name": "USER",
            "date_of_birth": "03/07/1999",  # Will be converted to "07 Mar 1999"
            "id_number": "TEST123456",
            "sex": "Male",  # For page2 dropdown
            "country_of_birth": "Mexico",
            "city_of_birth": "Mexico City",
            "prior_country_of_residence": "Mexico",
            "issuing_country": "Mexico",
        }


async def select_dropdown_option(page: Page, selector: str, option_text: str):
    """
    Select an option from a dropdown by clicking it and selecting the option.
    
    Handles various dropdown implementations:
    1. Click to open dropdown
    2. Wait for options to appear
    3. Click the matching option
    """
    print(f"   🔽 Opening dropdown: {selector}")
    
    # Click the dropdown to open it
    await page.click(selector)
    await asyncio.sleep(0.5)  # Wait for dropdown animation
    
    # Try to find and click the option
    # Common patterns for dropdown options
    option_selectors = [
        f"text='{option_text}'",  # Exact text match
        f"text={option_text}",     # Contains text
        f"li:has-text('{option_text}')",  # List item
        f"div:has-text('{option_text}')",  # Div
        f"span:has-text('{option_text}')",  # Span
        f"option:has-text('{option_text}')",  # Select option
        f"[role='option']:has-text('{option_text}')",  # ARIA option role
    ]
    
    for opt_selector in option_selectors:
        try:
            # Wait briefly for the option to be visible
            option = page.locator(opt_selector).first
            if await option.is_visible(timeout=1000):
                await option.click()
                print(f"   ✅ Selected: {option_text}")
                return True
        except:
            continue
    
    print(f"   ⚠️ Could not find option: {option_text}")
    return False


async def fill_autocomplete_dropdown(page: Page, selector: str, value: str):
    """
    Fill an autocomplete/combobox dropdown field.
    
    These fields typically:
    1. Type text to filter options
    2. Show a dropdown list
    3. Require clicking an option from the list
    """
    print(f"   🔽 Filling autocomplete: {selector} with '{value}'")
    
    try:
        # Clear and type the value
        await page.fill(selector, "")
        await page.type(selector, value, delay=50)  # Type slowly to trigger autocomplete
        await asyncio.sleep(1)  # Wait for dropdown to appear
        
        # Try to find and click the first matching option
        option_selectors = [
            f"li:has-text('{value}')",
            f"div.option:has-text('{value}')",
            f"[role='option']:has-text('{value}')",
            f"[role='listbox'] li:has-text('{value}')",
            f".dropdown-item:has-text('{value}')",
            f".autocomplete-option:has-text('{value}')",
        ]
        
        for opt_selector in option_selectors:
            try:
                option = page.locator(opt_selector).first
                if await option.is_visible(timeout=1000):
                    await option.click()
                    print(f"   ✅ Selected from dropdown: {value}")
                    return True
            except:
                continue
        
        # If no dropdown option found, just press Enter to confirm
        await page.keyboard.press("Enter")
        print(f"   ✅ Typed and confirmed: {value}")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def test_login_and_page1(username: str, password: str, test_data: dict):
    """Test login and page1 field filling."""
    selectors = load_selectors()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()
        
        print(f"\n🌐 Opening eMedical: {EMEDICAL_URL}")
        await page.goto(EMEDICAL_URL)
        await page.wait_for_load_state("networkidle")
        
        # ===== TEST LOGIN =====
        print("\n" + "="*50)
        print("TESTING LOGIN PAGE")
        print("="*50)
        
        login = selectors.get("login", {})
        
        # Username
        if login.get("username"):
            print(f"\n📝 Filling username: {login['username']}")
            try:
                await page.fill(login["username"], username)
                print("   ✅ Username filled")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Password
        if login.get("password"):
            print(f"\n🔑 Filling password: {login['password']}")
            try:
                await page.fill(login["password"], password)
                print("   ✅ Password filled")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Submit
        if login.get("submit"):
            print(f"\n🔘 Clicking login: {login['submit']}")
            try:
                await page.click(login["submit"])
                print("   ✅ Login button clicked")
                
                # Wait for navigation
                print("   ⏳ Waiting for page to load...")
                await page.wait_for_load_state("networkidle", timeout=30000)
                print(f"   📍 Current URL: {page.url}")
            except PlaywrightTimeout:
                print("   ⚠️ Timeout waiting for page load")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # ===== TEST PAGE 1 =====
        print("\n" + "="*50)
        print("TESTING PAGE 1 FIELDS")
        print("="*50)
        
        # Convert date to eMedical format
        dob_converted = convert_date_to_emedical_format(test_data.get("date_of_birth", ""))
        test_data_display = {**test_data, "date_of_birth": f"{test_data.get('date_of_birth', '')} → {dob_converted}"}
        print(f"\nTest data: {test_data_display}")
        
        # Wait for the page to be ready (wait for a key element to appear)
        print("\n⏳ Waiting for data entry page to load...")
        try:
            await page.wait_for_selector("#caseSearch-_0d3c2b_input", timeout=15000)
            print("   ✅ Data entry page loaded")
        except PlaywrightTimeout:
            print("   ⚠️ Page didn't load in time, continuing anyway...")
        
        page1 = selectors.get("page1", {})
        
        # Dropdown: Status Adjuster (fixed value) - use direct option selector
        dropdown_option_selector = "#caseSearch-_0d3c2b_input > option:nth-child(2)"
        print(f"\n📝 Selecting dropdown (Status Adjuster): {dropdown_option_selector}")
        try:
            # For <select> elements, use select_option with the option's value or index
            await page.select_option("#caseSearch-_0d3c2b_input", index=1)  # 0-based, so index 1 = 2nd option
            print("   ✅ Selected: Status Adjuster")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Family name
        if page1.get("family_name"):
            print(f"\n📝 Filling family_name: {page1['family_name']}")
            try:
                await page.fill(page1["family_name"], test_data.get("family_name", ""))
                print(f"   ✅ Filled with: {test_data.get('family_name', '')}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Given name
        if page1.get("given_name"):
            print(f"\n📝 Filling given_name: {page1['given_name']}")
            try:
                await page.fill(page1["given_name"], test_data.get("given_name", ""))
                print(f"   ✅ Filled with: {test_data.get('given_name', '')}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Date of birth - convert to eMedical format (DD MMM YYYY)
        if page1.get("date_of_birth"):
            print(f"\n📝 Filling date_of_birth: {page1['date_of_birth']}")
            try:
                await page.fill(page1["date_of_birth"], dob_converted)
                print(f"   ✅ Filled with: {dob_converted}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # ID number
        if page1.get("ID"):
            print(f"\n📝 Filling ID: {page1['ID']}")
            try:
                await page.fill(page1["ID"], test_data.get("id_number", ""))
                print(f"   ✅ Filled with: {test_data.get('id_number', '')}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Search button
        if page1.get("search_button"):
            print(f"\n🔘 Clicking search: {page1['search_button']}")
            try:
                await page.click(page1["search_button"])
                print("   ✅ Search clicked")
                await asyncio.sleep(2)  # Wait for search results
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Create case button
        if page1.get("createcase_button"):
            print(f"\n🔘 Clicking create case: {page1['createcase_button']}")
            try:
                await page.click(page1["createcase_button"])
                print("   ✅ Create case clicked")
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # ===== TEST PAGE 2 =====
        print("\n" + "="*50)
        print("TESTING PAGE 2 FIELDS")
        print("="*50)
        
        page2 = selectors.get("page2", {})
        
        # Wait for page 2 to load
        print("\n⏳ Waiting for page 2 to load...")
        await asyncio.sleep(2)
        
        # Sex dropdown (native select)
        if page2.get("sex"):
            print(f"\n📝 Selecting sex: {page2['sex']}")
            try:
                # Try selecting by visible text first, then by index
                try:
                    await page.select_option(page2["sex"], label=test_data.get("sex", "Male"))
                except:
                    # If label doesn't work, try index (1=Male, 2=Female typically)
                    await page.select_option(page2["sex"], index=1)
                print(f"   ✅ Selected: {test_data.get('sex', 'Male')}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Country of birth (autocomplete dropdown)
        if page2.get("country_of_birth"):
            print(f"\n📝 Filling country_of_birth: {page2['country_of_birth']}")
            await fill_autocomplete_dropdown(page, page2["country_of_birth"], test_data.get("country_of_birth", ""))
        
        # City of birth (text field)
        if page2.get("city_of_birth"):
            print(f"\n📝 Filling city_of_birth: {page2['city_of_birth']}")
            try:
                await page.fill(page2["city_of_birth"], test_data.get("city_of_birth", ""))
                print(f"   ✅ Filled with: {test_data.get('city_of_birth', '')}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Prior country of residence (autocomplete dropdown)
        if page2.get("prior_county_of_residence"):
            print(f"\n📝 Filling prior_country_of_residence: {page2['prior_county_of_residence']}")
            await fill_autocomplete_dropdown(page, page2["prior_county_of_residence"], test_data.get("prior_country_of_residence", ""))
        
        # Identity document / ID number (page 2) - text field
        if page2.get("ID_number"):
            print(f"\n📝 Filling ID_number (page2): {page2['ID_number']}")
            try:
                await page.fill(page2["ID_number"], test_data.get("id_number", ""))
                print(f"   ✅ Filled with: {test_data.get('id_number', '')}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Issuing country (autocomplete dropdown)
        if page2.get("issuing_country"):
            print(f"\n📝 Filling issuing_country: {page2['issuing_country']}")
            await fill_autocomplete_dropdown(page, page2["issuing_country"], test_data.get("issuing_country", ""))
        
        # ===== SUMMARY =====
        print("\n" + "="*50)
        print("TEST COMPLETE - LOGIN + PAGE 1 + PAGE 2")
        print("="*50)
        print("""
Check the browser to verify:
1. ✓ Did the login work?
2. ✓ Were the page1 fields filled correctly?
3. ✓ Did search/create case work?
4. ✓ Were the page2 fields filled correctly?

If something didn't work, note the field and we'll fix the selector.
""")
        
        input("\n⏸️  Press ENTER to close the browser...")
        await browser.close()


async def main():
    # Get PDF path if provided
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    if pdf_path:
        print(f"📄 Using data from PDF: {pdf_path}")
    else:
        print("📄 Using sample test data (no PDF provided)")
    
    # Get credentials
    print("\n" + "="*50)
    print("eMedical Login Credentials")
    print("="*50)
    print("(Credentials are NOT stored - only used for this test)")
    
    username = input("\nUsername: ").strip()
    password = input("Password: ").strip()
    
    if not username or not password:
        print("❌ Username and password are required")
        return
    
    # Get test data
    test_data = get_test_data(pdf_path)
    
    # Run test
    await test_login_and_page1(username, password, test_data)


if __name__ == "__main__":
    asyncio.run(main())
