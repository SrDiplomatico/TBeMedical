"""
Utility to discover all dropdown options on the current eMedical page.

This script will:
1. Login to eMedical
2. Navigate to a page
3. Find all <select> elements and autocomplete fields
4. Extract all available options
5. Save them to a JSON file for reference

Usage:
    python -m src.automation.discover_dropdowns
"""

import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

SELECTORS_FILE = Path(__file__).parent / "discovered_selectors.json"
DROPDOWNS_FILE = Path(__file__).parent / "dropdown_options.json"
EMEDICAL_URL = "https://www.emedical.immi.gov.au/eMedUI/eMedical"


def load_selectors() -> dict:
    """Load selectors from JSON file."""
    with open(SELECTORS_FILE, 'r') as f:
        return json.load(f)


async def discover_select_options(page: Page) -> dict:
    """
    Find all <select> elements on the page and extract their options.
    """
    print("\n🔍 Discovering <select> dropdown options...")
    
    # Wait for page to be stable
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except:
        pass
    
    try:
        selects = await page.query_selector_all("select")
    except Exception as e:
        print(f"   ⚠️ Error finding selects: {e}")
        return {}
    
    dropdown_data = {}
    
    for select in selects:
        try:
            # Get select element info
            select_id = await select.get_attribute("id") or ""
            select_name = await select.get_attribute("name") or ""
            select_class = await select.get_attribute("class") or ""
            
            # Build a usable selector
            if select_id:
                selector = f"#{select_id}"
            elif select_name:
                selector = f"select[name='{select_name}']"
            else:
                continue
            
            # Get all options
            options = await select.query_selector_all("option")
            option_list = []
            
            for opt in options:
                value = await opt.get_attribute("value") or ""
                text = await opt.inner_text()
                option_list.append({
                    "value": value,
                    "text": text.strip()
                })
            
            dropdown_data[selector] = {
                "id": select_id,
                "name": select_name,
                "class": select_class,
                "options": option_list
            }
            
            print(f"\n   📋 {selector}")
            for opt in option_list[:5]:  # Show first 5 options
                print(f"      - {opt['text']} (value: {opt['value']})")
            if len(option_list) > 5:
                print(f"      ... and {len(option_list) - 5} more options")
                
        except Exception as e:
            print(f"   ⚠️ Error reading select: {e}")
    
    return dropdown_data


async def discover_autocomplete_fields(page: Page) -> dict:
    """
    Find input fields that look like autocomplete/combobox fields.
    These typically have attributes like 'autocomplete', 'list', or specific classes.
    """
    print("\n🔍 Discovering autocomplete/combobox fields...")
    
    # Wait for page to be stable
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except:
        pass
    
    # Look for inputs that might be autocomplete fields
    autocomplete_data = {}
    
    # Common patterns for autocomplete inputs
    patterns = [
        "input[list]",  # Has datalist
        "input[role='combobox']",
        "input[aria-autocomplete]",
        "input[class*='autocomplete']",
        "input[class*='typeahead']",
        "input[id*='_input']",  # eMedical pattern
    ]
    
    for pattern in patterns:
        try:
            inputs = await page.query_selector_all(pattern)
            for inp in inputs:
                inp_id = await inp.get_attribute("id") or ""
                inp_name = await inp.get_attribute("name") or ""
                inp_placeholder = await inp.get_attribute("placeholder") or ""
                inp_list = await inp.get_attribute("list") or ""
                
                if inp_id:
                    selector = f"#{inp_id}"
                elif inp_name:
                    selector = f"input[name='{inp_name}']"
                else:
                    continue
                
                # Skip if already found
                if selector in autocomplete_data:
                    continue
                
                autocomplete_data[selector] = {
                    "id": inp_id,
                    "name": inp_name,
                    "placeholder": inp_placeholder,
                    "datalist_id": inp_list,
                    "type": "autocomplete"
                }
                
                # If has datalist, get those options
                if inp_list:
                    datalist = await page.query_selector(f"datalist#{inp_list}")
                    if datalist:
                        options = await datalist.query_selector_all("option")
                        option_list = []
                        for opt in options:
                            value = await opt.get_attribute("value") or ""
                            option_list.append(value)
                        autocomplete_data[selector]["options"] = option_list
                
                print(f"\n   📝 {selector}")
                print(f"      placeholder: {inp_placeholder}")
                if inp_list:
                    print(f"      datalist: #{inp_list}")
                    
        except Exception as e:
            pass
    
    return autocomplete_data


async def discover_all_inputs(page: Page) -> dict:
    """
    Get all input fields on the page for reference.
    """
    print("\n🔍 Discovering all input fields...")
    
    inputs = await page.query_selector_all("input:not([type='hidden']), select, textarea")
    input_data = {}
    
    for inp in inputs:
        try:
            tag = await inp.evaluate("el => el.tagName.toLowerCase()")
            inp_id = await inp.get_attribute("id") or ""
            inp_name = await inp.get_attribute("name") or ""
            inp_type = await inp.get_attribute("type") or ""
            inp_placeholder = await inp.get_attribute("placeholder") or ""
            
            if inp_id:
                selector = f"#{inp_id}"
            elif inp_name:
                selector = f"{tag}[name='{inp_name}']"
            else:
                continue
            
            # Get label if exists
            label_text = ""
            if inp_id:
                label = await page.query_selector(f"label[for='{inp_id}']")
                if label:
                    label_text = await label.inner_text()
            
            input_data[selector] = {
                "tag": tag,
                "id": inp_id,
                "name": inp_name,
                "type": inp_type,
                "placeholder": inp_placeholder,
                "label": label_text.strip()
            }
            
        except Exception as e:
            pass
    
    print(f"   Found {len(input_data)} input fields")
    return input_data


async def main():
    selectors = load_selectors()
    
    print("\n" + "="*60)
    print("eMedical Dropdown Discovery Tool")
    print("="*60)
    print("(Credentials are NOT stored - only used for this session)")
    
    username = input("\nUsername: ").strip()
    password = input("Password: ").strip()
    
    if not username or not password:
        print("❌ Username and password are required")
        return
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=300)
        page = await browser.new_page()
        
        # Login
        print(f"\n🌐 Opening eMedical: {EMEDICAL_URL}")
        await page.goto(EMEDICAL_URL)
        await page.wait_for_load_state("networkidle")
        
        login = selectors.get("login", {})
        await page.fill(login["username"], username)
        await page.fill(login["password"], password)
        await page.click(login["submit"])
        
        print("⏳ Logging in...")
        await page.wait_for_load_state("networkidle", timeout=30000)
        
        all_dropdown_data = {}
        
        while True:
            print("\n" + "="*60)
            print(f"📍 Current URL: {page.url}")
            print("="*60)
            
            print("\nOptions:")
            print("  1. Discover dropdowns on this page")
            print("  2. Discover all inputs on this page")
            print("  3. Test clicking a specific dropdown to see options")
            print("  4. Save discoveries to file")
            print("  5. Navigate (you control the browser)")
            print("  q. Quit")
            
            choice = input("\nChoice: ").strip().lower()
            
            if choice == "1":
                # Discover <select> dropdowns
                select_data = await discover_select_options(page)
                all_dropdown_data["selects"] = select_data
                
                # Discover autocomplete fields
                autocomplete_data = await discover_autocomplete_fields(page)
                all_dropdown_data["autocompletes"] = autocomplete_data
                
            elif choice == "2":
                input_data = await discover_all_inputs(page)
                all_dropdown_data["all_inputs"] = input_data
                
                # Print summary
                print("\n📋 Input fields found:")
                for selector, info in input_data.items():
                    label = info.get("label", "") or info.get("placeholder", "") or info.get("id", "")
                    print(f"   {selector}: {label} [{info['tag']}/{info['type']}]")
                
            elif choice == "3":
                selector = input("Enter selector to click (e.g., #dropdown-id): ").strip()
                if selector:
                    try:
                        print(f"🖱️ Clicking {selector}...")
                        await page.click(selector)
                        await asyncio.sleep(1)
                        
                        # Try to find visible options
                        print("Looking for dropdown options...")
                        
                        # Check for various dropdown patterns
                        option_patterns = [
                            "li[role='option']",
                            "[role='listbox'] li",
                            ".dropdown-menu li",
                            ".autocomplete-suggestions div",
                            "[class*='option']",
                        ]
                        
                        for pattern in option_patterns:
                            options = await page.query_selector_all(pattern)
                            if options and len(options) > 0:
                                print(f"\n   Found options with pattern: {pattern}")
                                for opt in options[:10]:
                                    text = await opt.inner_text()
                                    print(f"      - {text.strip()}")
                                if len(options) > 10:
                                    print(f"      ... and {len(options) - 10} more")
                                break
                        
                        # Press Escape to close dropdown
                        await page.keyboard.press("Escape")
                        
                    except Exception as e:
                        print(f"❌ Error: {e}")
                
            elif choice == "4":
                # Save to file
                with open(DROPDOWNS_FILE, 'w') as f:
                    json.dump(all_dropdown_data, f, indent=2)
                print(f"\n✅ Saved to {DROPDOWNS_FILE}")
                
            elif choice == "5":
                print("\n👆 Navigate in the browser, then press Enter to continue...")
                input()
                
            elif choice == "q":
                break
        
        await browser.close()
        print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
