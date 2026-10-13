"""
Dynamic selector discovery for eMedical portal.

The eMedical portal generates dynamic element IDs that change between
sessions and machines. This module discovers form elements at runtime
by their content, structure, and attributes rather than hardcoded IDs.

Each discover_page*() function runs JavaScript on the page to classify
elements, then updates the selector dicts in field_map_emedical.py in-place.
"""

import time
from playwright.sync_api import Page


def discover_page1_selectors(page: Page) -> None:
    """
    Discover the one dynamic selector on Page 1: the status_adjuster dropdown.
    
    Identifies it as the <select> with a "Status Adjuster" / "STSADJ" option.
    """
    from src.automation.field_map_emedical import PAGE1_FIELDS

    print("DEBUG: Discovering Page 1 selectors dynamically...")

    select_info = page.evaluate("""() => {
        const selects = document.querySelectorAll('select');
        const results = [];
        for (const sel of selects) {
            const opts = Array.from(sel.options).map(o => o.value);
            results.push({
                id: sel.id || '',
                hasStsAdj: opts.includes('STSADJ')
            });
        }
        return results;
    }""")

    for sel in select_info:
        if sel.get('hasStsAdj') and sel.get('id'):
            new_sel = f"#{sel['id']}"
            old_sel = PAGE1_FIELDS["status_adjuster"]["selector"]
            if old_sel != new_sel:
                print(f"DEBUG: Updated Page 1 'status_adjuster': {old_sel} -> {new_sel}")
                PAGE1_FIELDS["status_adjuster"]["selector"] = new_sel
            else:
                print(f"DEBUG: Page 1 'status_adjuster' unchanged: {new_sel}")
            return

    print("WARNING: Could not discover status_adjuster dropdown on Page 1")


def discover_page2_selectors(page: Page) -> None:
    """
    Discover all 6 dynamic selectors on Page 2 plus the Create button.

    Page 2 layout has TWO sections:
      Left  – "Applicant personal details":
              Sex, Date of birth, Country of Birth, City of Birth,
              Prior Country of Residence, Country of Nationality
      Right – "Identity document details":
              ID type, Number/ID, Issuing country, Date of issue, Date of expiry

    Classification logic (selects):
      • Sex dropdown           – has M / F option values
      • ID type dropdown       – has option values '01' and '07'
      • Country dropdowns (4)  – each has >50 options
        - Issuing country is the one closest in the DOM to the ID type
          dropdown (they share a section container).
        - The remaining 3, in DOM order, are:
          Country of Birth, Prior Country, Country of Nationality.

    Classification logic (text inputs):
      • Date inputs have a calendar-button sibling → skip them.
      • City of birth is the first visible, required, non-date text input.
    """
    from src.automation.field_map_emedical import PAGE2_FIELDS, PAGE_NAVIGATION

    print("DEBUG: Discovering Page 2 selectors dynamically...")
    time.sleep(1)

    # ------------------------------------------------------------------
    # Single JS call: selects (with DOM-proximity to ID-type), text
    # inputs (with date-picker detection), and buttons.
    # ------------------------------------------------------------------
    discovery = page.evaluate("""() => {
        // Helper: depth from el2 up to the shallowest ancestor shared with el1
        function commonAncestorDepth(el1, el2) {
            const anc = new Set();
            for (let p = el1; p; p = p.parentElement) anc.add(p);
            let depth = 0;
            for (let p = el2; p; p = p.parentElement, depth++) {
                if (anc.has(p)) return depth;
            }
            return 999;
        }

        const selects = Array.from(document.querySelectorAll('select'));

        // Locate the ID-type dropdown first (has values '01' and '07')
        const idTypeEl = selects.find(s => {
            const vals = new Set(Array.from(s.options).map(o => o.value));
            return vals.has('01') && vals.has('07');
        });

        const selectResults = selects.map(sel => {
            const opts = Array.from(sel.options);
            const vals = opts.map(o => o.value);
            return {
                id:   sel.id || '',
                name: sel.name || '',
                optionCount: opts.length,
                hasMF:       vals.includes('M') && vals.includes('F'),
                hasIdTypes:  vals.includes('01') && vals.includes('07'),
                isCountry:   opts.length > 50,
                distToIdType: idTypeEl && sel !== idTypeEl
                              ? commonAncestorDepth(idTypeEl, sel) : 999
            };
        });

        // --- Text inputs with date-picker detection ---
        const inputs = Array.from(document.querySelectorAll('input[type="text"]'));
        const inputResults = inputs
            .filter(inp => inp.offsetParent !== null || inp.closest('[style*="display"]'))
            .map(inp => {
                // A date-picker field typically has a <button> sibling
                // (the calendar icon) directly after it inside the same parent.
                const parent = inp.parentElement;
                let hasDatePicker = false;
                if (parent) {
                    // Check siblings for a button (calendar trigger)
                    const sibling = inp.nextElementSibling;
                    if (sibling && sibling.tagName === 'BUTTON') hasDatePicker = true;
                    // Also check for calendar/date-related classes anywhere in parent
                    if (!hasDatePicker) {
                        hasDatePicker = !!(parent.querySelector(
                            '[class*="calendar"], [class*="datepicker"], ' +
                            '[class*="date-picker"], [class*="ui-date"]'));
                    }
                }
                return {
                    id:        inp.id || '',
                    name:      inp.name || '',
                    isVisible: inp.offsetParent !== null,
                    isRequired: inp.hasAttribute('required'),
                    maxLength: inp.getAttribute('maxlength') || '',
                    hasDatePicker: hasDatePicker
                };
            });

        // --- Buttons ---
        const buttons = Array.from(document.querySelectorAll(
            'button, input[type="button"], input[type="submit"], ' +
            'a[role="button"], [class*="button"], [class*="btn"]'));
        const buttonResults = buttons.map(btn => ({
            id:   btn.id || '',
            text: (btn.textContent || btn.value || '').trim(),
            tagName: btn.tagName,
            type: btn.type || ''
        }));

        return { selects: selectResults, inputs: inputResults, buttons: buttonResults };
    }""")

    select_info = discovery['selects']
    input_info  = discovery['inputs']
    button_info = discovery['buttons']

    print(f"DEBUG: Found {len(select_info)} <select>, {len(input_info)} text inputs, {len(button_info)} buttons")

    # ------------------------------------------------------------------
    # Classify <select> elements
    # ------------------------------------------------------------------
    sex_selector      = None
    id_type_selector  = None
    country_entries   = []          # [(css, distToIdType)]  – keeps DOM order

    for sel in select_info:
        sel_id = sel.get('id', '')
        if not sel_id:
            continue
        css = f"#{sel_id}"
        if sel.get('hasMF'):
            sex_selector = css
            print(f"DEBUG: Discovered sex dropdown: {css}")
        elif sel.get('hasIdTypes'):
            id_type_selector = css
            print(f"DEBUG: Discovered ID type dropdown: {css}")
        elif sel.get('isCountry'):
            dist = sel.get('distToIdType', 999)
            country_entries.append((css, dist))
            print(f"DEBUG: Discovered country dropdown: {css} "
                  f"({sel.get('optionCount')} options, distToIdType={dist})")

    # Separate issuing_country (closest to ID-type) from applicant-section
    # country dropdowns.  The remaining ones stay in DOM order:
    #   [0] Country of Birth, [1] Prior Country, [2] Country of Nationality
    issuing_selector = None
    applicant_countries = []        # css selectors in DOM order

    if country_entries:
        min_dist = min(d for _, d in country_entries)
        # Find the entry with the smallest distance
        issuing_idx = next(i for i, (_, d) in enumerate(country_entries) if d == min_dist)
        issuing_selector = country_entries[issuing_idx][0]
        print(f"DEBUG: Issuing country (closest to ID type, dist={min_dist}): {issuing_selector}")
        applicant_countries = [css for i, (css, _) in enumerate(country_entries) if i != issuing_idx]
    else:
        applicant_countries = []

    cob_selector   = applicant_countries[0] if len(applicant_countries) > 0 else None
    prior_selector = applicant_countries[1] if len(applicant_countries) > 1 else None
    # applicant_countries[2] = Country of Nationality (not currently filled)

    # ------------------------------------------------------------------
    # Find city_of_birth text input (skip search boxes and date-pickers)
    # ------------------------------------------------------------------
    city_selector = None
    for inp in input_info:
        inp_id = inp.get('id', '')
        if not inp_id:
            continue
        if inp_id.startswith('caseSearch') or inp_id.startswith('logon') or inp_id.startswith('appMenu'):
            continue
        if not inp.get('isVisible'):
            continue
        # Skip date-picker inputs (Date of birth, Date of issue, Date of expiry)
        if inp.get('hasDatePicker'):
            print(f"DEBUG: Skipping date-picker input: #{inp_id}")
            continue
        # City field has required / maxlength; search box does not
        if inp.get('isRequired') or inp.get('maxLength'):
            city_selector = f"#{inp_id}"
            print(f"DEBUG: Discovered city_of_birth input: {city_selector}")
            break

    # Fallback: first visible non-date non-search text input with a long ID
    if not city_selector:
        for inp in input_info:
            inp_id = inp.get('id', '')
            if not inp_id or len(inp_id) < 15:
                continue
            if inp_id.startswith('caseSearch') or inp_id.startswith('logon') or inp_id.startswith('appMenu'):
                continue
            if not inp.get('isVisible') or inp.get('hasDatePicker'):
                continue
            city_selector = f"#{inp_id}"
            print(f"DEBUG: Discovered city_of_birth input (fallback): {city_selector}")
            break

    # ------------------------------------------------------------------
    # Find Create button
    # ------------------------------------------------------------------
    create_btn = None
    for btn in button_info:
        if 'create' in btn.get('text', '').lower().strip() and btn.get('id'):
            create_btn = f"#{btn['id']}"
            print(f"DEBUG: Discovered Create button: {create_btn}")
            break

    # ------------------------------------------------------------------
    # Apply discovered selectors
    # ------------------------------------------------------------------
    updates = {
        'sex': sex_selector,
        'country_of_birth': cob_selector,
        'city_of_birth': city_selector,
        'prior_country': prior_selector,
        'id_type': id_type_selector,
        'issuing_country': issuing_selector,
    }
    _apply_updates(PAGE2_FIELDS, updates, "Page 2")

    if create_btn:
        _update_nav(PAGE_NAVIGATION, 'page2_next', create_btn)
    else:
        print("WARNING: Could not discover Create button, using text-based fallback")
        PAGE_NAVIGATION['page2_next'] = "button:has-text('Create'), input[value='Create']"

    print("DEBUG: Page 2 selector discovery complete")


def discover_page3_selectors(page: Page) -> None:
    """
    Discover Page 3 address/phone popup selectors.
    
    Page 3 has an "Add New" button that opens a popup dialog.
    The popup contains a channel type dropdown, address fields, and a Save button.
    
    Strategy:
    - Add button: look for a button/link with add/plus functionality in the contacts area
    - After popup opens: discover channel dropdown, country dropdown, text inputs, 
      state dropdown, and Save button by their structure within the dialog.
    - Navigation "Next" button on page 3
    """
    from src.automation.field_map_emedical import PAGE3_ADDRESS_POPUP, PAGE3_PHONE_POPUP, PAGE_NAVIGATION

    print("DEBUG: Discovering Page 3 selectors dynamically...")
    time.sleep(1)

    # Step 1: Find the "Add New" button on the page
    # It's typically a small button/link with a plus icon or "Add" text
    add_button_id = page.evaluate("""() => {
        // Look for buttons with "Add" or "+" text, or typical add-new patterns
        const candidates = document.querySelectorAll('button, a, [role="button"], input[type="button"]');
        for (const btn of candidates) {
            const text = (btn.textContent || btn.value || '').trim().toLowerCase();
            const title = (btn.title || '').toLowerCase();
            const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
            // Match "Add New", "Add", "+" or similar
            if ((text.includes('add') || title.includes('add') || ariaLabel.includes('add') ||
                 text === '+' || text === 'new') && btn.id) {
                // Prefer buttons that are visible
                if (btn.offsetParent !== null || btn.offsetWidth > 0) {
                    return btn.id;
                }
            }
        }
        // Fallback: look for the specific pattern - small button near a grid/table
        const gridButtons = document.querySelectorAll('[id*="1a0"]');
        for (const btn of gridButtons) {
            if ((btn.tagName === 'BUTTON' || btn.tagName === 'A') && 
                btn.offsetParent !== null && btn.id) {
                return btn.id;
            }
        }
        return null;
    }""")

    if add_button_id:
        new_sel = f"#{add_button_id}"
        print(f"DEBUG: Discovered Page 3 Add button: {new_sel}")
        PAGE3_ADDRESS_POPUP["add_button"] = new_sel
        PAGE3_PHONE_POPUP["add_button"] = new_sel
    else:
        print("WARNING: Could not discover Page 3 Add button")

    # Step 2: Find Next button on Page 3
    _discover_next_button(page, PAGE_NAVIGATION, 'page3_next', "Page 3")

    # Step 3: We need to discover popup selectors WHEN the popup is open.
    # We can't do it now since the popup isn't open yet.
    # Instead, we'll store a flag to discover popup selectors when the popup opens.
    # The _fill_page3_address method will call discover_page3_popup_selectors() after clicking Add.
    print("DEBUG: Page 3 pre-popup discovery complete (popup selectors discovered when popup opens)")


def discover_page3_popup_selectors(page: Page) -> None:
    """
    Discover selectors inside the Page 3 address/phone popup dialog.
    Must be called AFTER the popup is open.
    
    Identifies elements by type within the dialog:
    - Channel type dropdown: <select> with options like "Address (Home)", "Email", etc.
    - Country dropdown: <select> with many (>50) country options
    - State dropdown: <select> with ~50-65 state/territory options
    - Text inputs: street, unit, city, zip (by order in DOM)
    - Save button: button with "Save" text in the dialog
    """
    from src.automation.field_map_emedical import PAGE3_ADDRESS_POPUP, PAGE3_PHONE_POPUP

    print("DEBUG: Discovering Page 3 popup selectors...")

    # Find the dialog container
    popup_info = page.evaluate("""() => {
        // Look for visible dialog/modal containers
        const dialogs = document.querySelectorAll('[role="dialog"], .ui-dialog, [class*="dialog"], [class*="dlg"], [id*="-dlg-"]');
        let dialogEl = null;
        for (const d of dialogs) {
            if (d.offsetParent !== null || d.offsetWidth > 0) {
                dialogEl = d;
                break;
            }
        }
        
        // If no dialog found by role, look for any visible overlay/popup
        if (!dialogEl) {
            const overlays = document.querySelectorAll('[class*="popup"], [class*="modal"], [class*="overlay"]');
            for (const o of overlays) {
                if (o.offsetParent !== null && o.querySelectorAll('select').length > 0) {
                    dialogEl = o;
                    break;
                }
            }
        }
        
        // If still not found, scan all visible selects for one that looks like channel type
        if (!dialogEl) {
            // Fallback: use document body
            dialogEl = document.body;
        }
        
        const result = { selects: [], inputs: [], buttons: [] };
        
        // Find all selects in the dialog area
        const selects = dialogEl.querySelectorAll('select');
        for (const sel of selects) {
            const opts = Array.from(sel.options).map(o => ({
                value: o.value,
                text: o.textContent.trim()
            }));
            result.selects.push({
                id: sel.id || '',
                optionCount: opts.length,
                // Channel type: has values like "3" (Address Home), "9" (Mobile), "1" (Email)
                hasChannelTypes: opts.some(o => o.value === '3') && opts.some(o => o.value === '9'),
                // Country: >50 options
                isCountryDropdown: opts.length > 50,
                // State: 50-70 options (US states + territories)
                isStateDropdown: opts.length >= 40 && opts.length <= 75 && !opts.some(o => o.value === '3' && o.text.includes('Address')),
                sampleTexts: opts.slice(0, 3).map(o => o.text)
            });
        }
        
        // Find text inputs in the dialog area.
        // Primary: scope to dialogEl.  Fallback: any visible input with '-dlg-' in its ID.
        let inputs = dialogEl.querySelectorAll('input[type="text"], input:not([type])');
        let inputArr = Array.from(inputs).filter(inp => inp.offsetParent !== null || inp.offsetWidth > 0);
        
        // If dialogEl was the body fallback, further filter to dialog inputs
        if (inputArr.length === 0 || dialogEl === document.body) {
            const allInputs = document.querySelectorAll('input[type="text"], input:not([type])');
            inputArr = Array.from(allInputs).filter(inp => {
                const id = inp.id || '';
                return id.includes('-dlg-') && (inp.offsetParent !== null || inp.offsetWidth > 0);
            });
        }
        
        for (const inp of inputArr) {
            result.inputs.push({
                id: inp.id || '',
                name: inp.name || '',
                placeholder: inp.placeholder || ''
            });
        }
        
        // Find buttons (save/close/cancel)
        const buttons = dialogEl.querySelectorAll('button, input[type="button"], a[role="button"]');
        for (const btn of buttons) {
            const text = (btn.textContent || btn.value || '').trim();
            result.buttons.push({
                id: btn.id || '',
                text: text
            });
        }
        
        return result;
    }""")

    # Classify selects
    channel_dropdown = None
    country_dropdown = None
    state_dropdown = None

    for sel in popup_info.get('selects', []):
        sel_id = sel.get('id', '')
        if not sel_id:
            continue
        css = f"#{sel_id}"
        if sel.get('hasChannelTypes'):
            channel_dropdown = css
            print(f"DEBUG: Discovered channel type dropdown: {css}")
        elif sel.get('isCountryDropdown'):
            country_dropdown = css
            print(f"DEBUG: Discovered popup country dropdown: {css} ({sel.get('optionCount')} options)")
        elif sel.get('isStateDropdown'):
            state_dropdown = css
            print(f"DEBUG: Discovered popup state dropdown: {css} ({sel.get('optionCount')} options)")

    # Classify text inputs by order: street, unit, city, zip
    # (country code and phone have different patterns)
    text_inputs = [inp for inp in popup_info.get('inputs', []) if inp.get('id')]
    text_input_selectors = [f"#{inp['id']}" for inp in text_inputs]
    print(f"DEBUG: Found {len(text_input_selectors)} text inputs in popup: {text_input_selectors}")

    # Find save button
    save_button = None
    for btn in popup_info.get('buttons', []):
        if 'save' in btn.get('text', '').lower() and btn.get('id'):
            save_button = f"#{btn['id']}"
            print(f"DEBUG: Discovered popup Save button: {save_button}")
            break

    # Update address popup selectors
    if channel_dropdown:
        PAGE3_ADDRESS_POPUP["channel_type_dropdown"] = channel_dropdown
        PAGE3_PHONE_POPUP["channel_type_dropdown"] = channel_dropdown
    if country_dropdown:
        PAGE3_ADDRESS_POPUP["country_dropdown"] = country_dropdown
    if save_button:
        PAGE3_ADDRESS_POPUP["save_button"] = save_button
        PAGE3_PHONE_POPUP["save_button"] = save_button

    # Map text inputs for address popup
    # Address popup text inputs (in order): street, unit, city, zip
    # But only assign if we have visible text inputs
    if len(text_input_selectors) >= 4:
        PAGE3_ADDRESS_POPUP["street_input"] = text_input_selectors[0]
        PAGE3_ADDRESS_POPUP["unit_input"] = text_input_selectors[1]
        PAGE3_ADDRESS_POPUP["city_input"] = text_input_selectors[2]
        PAGE3_ADDRESS_POPUP["zip_input"] = text_input_selectors[3]
        print(f"DEBUG: Mapped address text inputs: street={text_input_selectors[0]}, "
              f"unit={text_input_selectors[1]}, city={text_input_selectors[2]}, "
              f"zip={text_input_selectors[3]}")
    elif len(text_input_selectors) >= 1:
        print(f"WARNING: Expected 4+ text inputs in popup, found {len(text_input_selectors)}")

    if state_dropdown:
        PAGE3_ADDRESS_POPUP["state_dropdown"] = state_dropdown

    print("DEBUG: Page 3 popup selector discovery complete")


def discover_page3_phone_popup_selectors(page: Page) -> None:
    """
    Discover phone-specific fields in the re-opened popup.
    Called after channel type is changed to Mobile.
    
    Phone popup has: country code input, phone number input.
    Both inputs live inside the dialog and have '-dlg-' in their ID.
    """
    from src.automation.field_map_emedical import PAGE3_PHONE_POPUP

    print("DEBUG: Discovering Page 3 phone popup selectors...")

    # Find text inputs ONLY inside the dialog (ID contains '-dlg-')
    phone_inputs = page.evaluate("""() => {
        const inputs = document.querySelectorAll('input[type="text"], input:not([type])');
        const results = [];
        for (const inp of inputs) {
            const id = inp.id || '';
            // Only include inputs inside the dialog popup
            if (!id.includes('-dlg-')) continue;
            // Must be visible
            if (inp.offsetParent === null && inp.offsetWidth === 0) continue;
            results.push({
                id: id,
                maxLength: inp.getAttribute('maxlength') || '',
                size: inp.getAttribute('size') || '',
                width: inp.offsetWidth
            });
        }
        return results;
    }""")

    phone_input_selectors = [f"#{inp['id']}" for inp in phone_inputs if inp.get('id')]
    print(f"DEBUG: Found {len(phone_input_selectors)} phone dialog inputs: {phone_input_selectors}")

    # Phone popup has 2 inputs: country code (shorter/narrower) and phone number (wider)
    if len(phone_input_selectors) >= 2:
        # Country code is typically the narrower/shorter field
        # Sort by maxlength or width to identify country code vs phone
        # But in DOM order, country code comes first
        PAGE3_PHONE_POPUP["country_code_input"] = phone_input_selectors[0]
        PAGE3_PHONE_POPUP["phone_input"] = phone_input_selectors[1]
        print(f"DEBUG: Mapped phone inputs: country_code={phone_input_selectors[0]}, "
              f"phone={phone_input_selectors[1]}")
    elif len(phone_input_selectors) == 1:
        # Only one input - assume it's the phone number
        PAGE3_PHONE_POPUP["phone_input"] = phone_input_selectors[0]
        print(f"DEBUG: Mapped single phone input: {phone_input_selectors[0]}")
    else:
        print("WARNING: No phone dialog inputs found! Phone fields will use existing selectors.")

    print("DEBUG: Page 3 phone popup discovery complete")


def discover_page6_selectors(page: Page) -> None:
    """
    Discover the Start Exam(s) button on Page 6.
    
    Identifies it as a button with text containing 'Start Exam' or similar.
    """
    from src.automation.field_map_emedical import PAGE6_START_EXAMS

    print("DEBUG: Discovering Page 6 selectors dynamically...")
    time.sleep(1)

    button_id = page.evaluate("""() => {
        const buttons = document.querySelectorAll('button, a, input[type="button"], [role="button"]');
        for (const btn of buttons) {
            const text = (btn.textContent || btn.value || '').trim().toLowerCase();
            if (text.includes('start exam') && btn.id) {
                return btn.id;
            }
        }
        // Fallback: look for any button whose text contains "start"
        for (const btn of buttons) {
            const text = (btn.textContent || btn.value || '').trim().toLowerCase();
            if (text.includes('start') && btn.id && btn.offsetParent !== null) {
                return btn.id;
            }
        }
        return null;
    }""")

    if button_id:
        new_sel = f"#{button_id}"
        old_sel = PAGE6_START_EXAMS.get("start_exams_button", "")
        if old_sel != new_sel:
            print(f"DEBUG: Updated Page 6 'start_exams_button': {old_sel} -> {new_sel}")
        PAGE6_START_EXAMS["start_exams_button"] = new_sel
    else:
        print("WARNING: Could not discover Start Exam(s) button on Page 6")

    print("DEBUG: Page 6 selector discovery complete")


def discover_page7_selectors(page: Page) -> None:
    """
    Discover the Selective History and TB expandable section on Page 7.
    
    Looks for a <summary> or clickable header containing 'Selective' or 'TB' text.
    """
    from src.automation.field_map_emedical import PAGE7_SELECTIVE_TB

    print("DEBUG: Discovering Page 7 selectors dynamically...")
    time.sleep(1)

    selector = page.evaluate("""() => {
        // Look for <summary> elements (expandable sections)
        const summaries = document.querySelectorAll('summary');
        for (const s of summaries) {
            const text = s.textContent.toLowerCase();
            if (text.includes('selective') || text.includes('tb') || text.includes('tuberculosis')) {
                // Return a reliable selector - prefer the summary itself
                if (s.id) return '#' + s.id;
                // If summary has a child with an id, build a has-selector
                const child = s.querySelector('[id]');
                if (child) return 'summary:has(#' + child.id + ')';
                // Fallback: use text-based selector
                return null;
            }
        }
        return null;
    }""")

    if selector:
        old_sel = PAGE7_SELECTIVE_TB.get("selective_tb_section", "")
        if old_sel != selector:
            print(f"DEBUG: Updated Page 7 'selective_tb_section': {old_sel} -> {selector}")
        PAGE7_SELECTIVE_TB["selective_tb_section"] = selector
    else:
        # Fallback to text-based selector
        PAGE7_SELECTIVE_TB["selective_tb_section"] = "summary:has-text('Selective')"
        print("WARNING: Could not discover Selective TB section by ID, using text-based fallback")

    print("DEBUG: Page 7 selector discovery complete")


def discover_page8_selectors(page: Page) -> None:
    """
    Discover the View Exam button on Page 8.
    """
    from src.automation.field_map_emedical import PAGE8_VIEW_EXAM

    print("DEBUG: Discovering Page 8 selectors dynamically...")
    time.sleep(1)

    button_id = page.evaluate("""() => {
        const buttons = document.querySelectorAll('button, a, input[type="button"], [role="button"]');
        for (const btn of buttons) {
            const text = (btn.textContent || btn.value || '').trim().toLowerCase();
            if ((text.includes('view exam') || text.includes('view')) && btn.id) {
                if (btn.offsetParent !== null || btn.offsetWidth > 0) {
                    return btn.id;
                }
            }
        }
        return null;
    }""")

    if button_id:
        new_sel = f"#{button_id}"
        old_sel = PAGE8_VIEW_EXAM.get("view_exam_button", "")
        if old_sel != new_sel:
            print(f"DEBUG: Updated Page 8 'view_exam_button': {old_sel} -> {new_sel}")
        PAGE8_VIEW_EXAM["view_exam_button"] = new_sel
    else:
        print("WARNING: Could not discover View Exam button on Page 8")

    print("DEBUG: Page 8 selector discovery complete")


def discover_page9_selectors(page: Page) -> None:
    """
    Discover all Page 9 selectors: exam date, IGRA, chest X-ray, sputum, TB classification.
    
    This is the most complex page with ~50 dynamic selectors. Strategy:
    - Exam date: the first visible date-like input field
    - IGRA radio: radio button with value 'IGRA'
    - IGRA test dropdown: <select> with QNTFN/TSPOT options
    - IGRA date: date input near the IGRA section
    - IGRA result radio: radio group with NGTV/PSTV/INDT values
    - Chest X-ray radio: radio group with REQ/N_REQ values
    - X-ray reason checkboxes: checkboxes near the X-ray section
    - X-ray read date: date input in the X-ray section
    - X-ray result radio: radio group with NRM/ABN values
    - X-ray abnormal findings: multiple checkboxes (12 items)
    - Sputum radio: radio group with NI/IND values
    - Sputum reason checkboxes
    - Sputum smear/culture rows: sets of 3 (date, date, dropdown) × 3 rows
    - TB classification: checkboxes for NO_TB, CLASS_A, B0-B2, B_OTHER
    """
    from src.automation.field_map_emedical import PAGE9_EXAM_DATE

    print("DEBUG: Discovering Page 9 selectors dynamically...")
    time.sleep(1)

    # Comprehensive scan of the page
    page_elements = page.evaluate("""() => {
        const result = {
            radios: [],
            selects: [],
            checkboxes: [],
            textInputs: []
        };
        
        // ===== RADIO BUTTONS =====
        // Group radios by name
        const radioGroups = {};
        const radios = document.querySelectorAll('input[type="radio"]');
        for (const r of radios) {
            const name = r.name || '';
            if (!name) continue;
            if (!radioGroups[name]) radioGroups[name] = [];
            radioGroups[name].push({
                value: r.value || '',
                id: r.id || ''
            });
        }
        for (const [name, values] of Object.entries(radioGroups)) {
            const vals = values.map(v => v.value);
            result.radios.push({
                name: name,
                values: vals,
                hasIGRA: vals.includes('IGRA'),
                hasReqNreq: vals.includes('REQ') && vals.includes('N_REQ'),
                hasNrmAbn: vals.includes('NRM') && vals.includes('ABN'),
                hasNiInd: vals.includes('NI') && vals.includes('IND'),
                hasPstvNgtv: vals.includes('PSTV') && vals.includes('NGTV')
            });
        }
        
        // ===== SELECT DROPDOWNS =====
        const selects = document.querySelectorAll('select');
        for (const sel of selects) {
            const opts = Array.from(sel.options).map(o => o.value);
            result.selects.push({
                id: sel.id || '',
                optionCount: opts.length,
                hasQntfn: opts.includes('QNTFN'),
                hasPosNeg: opts.includes('POS') && opts.includes('NEG'),
                hasNtm: opts.includes('NTM'),
                sampleValues: opts.slice(0, 8)
            });
        }
        
        // ===== CHECKBOXES =====
        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
        for (const cb of checkboxes) {
            // Get the label text for this checkbox
            let labelText = '';
            if (cb.id) {
                const label = document.querySelector('label[for="' + cb.id.replace('_input', '') + '"]');
                if (label) labelText = label.textContent.trim();
            }
            if (!labelText) {
                const parent = cb.closest('label');
                if (parent) labelText = parent.textContent.trim();
            }
            if (!labelText) {
                // Try next sibling or parent's text
                const next = cb.nextElementSibling;
                if (next) labelText = next.textContent.trim();
            }
            result.checkboxes.push({
                id: cb.id || '',
                name: cb.name || '',
                value: cb.value || '',
                labelText: labelText.substring(0, 80)  // Truncate long labels
            });
        }
        
        // ===== TEXT/DATE INPUTS =====
        const inputs = document.querySelectorAll('input[type="text"], input:not([type])');
        for (const inp of inputs) {
            if (inp.type === 'radio' || inp.type === 'checkbox' || inp.type === 'hidden') continue;
            result.textInputs.push({
                id: inp.id || '',
                name: inp.name || '',
                placeholder: inp.placeholder || '',
                isVisible: inp.offsetParent !== null || inp.offsetWidth > 0
            });
        }

        // ===== TEXTAREAS =====
        const textareas = document.querySelectorAll('textarea');
        for (const ta of textareas) {
            result.textareas = result.textareas || [];
            result.textareas.push({
                id: ta.id || '',
                name: ta.name || '',
                isVisible: ta.offsetParent !== null || ta.offsetWidth > 0
            });
        }
        
        return result;
    }""")

    radios = page_elements.get('radios', [])
    selects = page_elements.get('selects', [])
    checkboxes = page_elements.get('checkboxes', [])
    text_inputs = page_elements.get('textInputs', [])

    print(f"DEBUG: Page 9 scan: {len(radios)} radio groups, {len(selects)} selects, "
          f"{len(checkboxes)} checkboxes, {len(text_inputs)} text inputs")

    # === Map radio groups ===
    for rg in radios:
        name = rg['name']
        if rg.get('hasIGRA'):
            _update_page9(PAGE9_EXAM_DATE, "igra_radio", f"input[name='{name}'][value='IGRA']")
            print(f"DEBUG: Discovered IGRA radio: name='{name}'")
        elif rg.get('hasPstvNgtv'):
            _update_page9(PAGE9_EXAM_DATE, "igra_result_radio_name", name)
            print(f"DEBUG: Discovered IGRA result radio: name='{name}'")
        elif rg.get('hasReqNreq'):
            _update_page9(PAGE9_EXAM_DATE, "chest_xray_req_radio_name", name)
            print(f"DEBUG: Discovered chest X-ray req radio: name='{name}'")
        elif rg.get('hasNrmAbn'):
            _update_page9(PAGE9_EXAM_DATE, "xray_result_radio_name", name)
            print(f"DEBUG: Discovered X-ray result radio: name='{name}'")
        elif rg.get('hasNiInd'):
            _update_page9(PAGE9_EXAM_DATE, "sputum_radio_name", name)
            print(f"DEBUG: Discovered sputum radio: name='{name}'")

    # === Map select dropdowns ===
    igra_dropdown = None
    smear_dropdowns = []
    culture_dropdowns = []

    for sel in selects:
        sel_id = sel.get('id', '')
        if not sel_id:
            continue
        css = f"#{sel_id}"
        if sel.get('hasQntfn'):
            igra_dropdown = css
            _update_page9(PAGE9_EXAM_DATE, "igra_test_dropdown", css)
            print(f"DEBUG: Discovered IGRA test dropdown: {css}")
        elif sel.get('hasPosNeg'):
            if sel.get('hasNtm'):
                culture_dropdowns.append(css)
            else:
                smear_dropdowns.append(css)

    # Map smear and culture result dropdowns to rows
    smear_rows = PAGE9_EXAM_DATE.get("sputum_smear_rows", [])
    for i, css in enumerate(smear_dropdowns[:3]):
        if i < len(smear_rows):
            smear_rows[i]["result_dropdown"] = css
            print(f"DEBUG: Discovered smear row {i+1} result dropdown: {css}")

    culture_rows = PAGE9_EXAM_DATE.get("sputum_culture_rows", [])
    for i, css in enumerate(culture_dropdowns[:3]):
        if i < len(culture_rows):
            culture_rows[i]["result_dropdown"] = css
            print(f"DEBUG: Discovered culture row {i+1} result dropdown: {css}")

    # === Map checkboxes by label text ===
    xray_findings = PAGE9_EXAM_DATE.get("xray_abnormal_findings", {})
    tb_class = PAGE9_EXAM_DATE.get("tb_classification_checkboxes", {})

    # Label patterns for X-ray findings
    xray_label_map = {
        "infiltrate": "xray_infiltrate",
        "reticular": "xray_reticular",
        "cavit": "xray_cavity",
        "nodule": "xray_nodules",  # "Nodule or mass with poorly defined margins"
        "pleural eff": "xray_pleural",
        "hilar": "xray_hilar",
        "miliary": "xray_miliary",
        "linear": "xray_linear",
        "discrete": "xray_discrete_nodule",
        "volume": "xray_volume_loss",
        "thick pleur": "xray_thick_pleural",
        "other": "xray_other",
    }

    # Label patterns for TB classification
    tb_label_map = {
        "no class": "NO_TB",
        "class a": "CLASS_A",
        "b0": "B0_PULM",
        "b1 tb, pulm": "B1_PULM",
        "b1 tb, extra": "B1_EXTRAPULM",
        "b2": "B2_LTBI",
        "b, other": "B_OTHER",
        "class b, other": "B_OTHER",
    }

    # Label patterns for X-ray reason checkboxes
    xray_reason_map = {
        "initial screening": "xray_reason_initial_screening",
        "signs": "xray_reason_tb_signs",
        "symptom": "xray_reason_tb_signs",
        "igra exception": "xray_reason_igra_exception",
    }

    # Label patterns for sputum reason checkboxes
    sputum_reason_map = {
        "signs or symptoms": "sputum_reason_signs_symptoms",
        "chest x-ray": "sputum_reason_chest_xray",
        "hiv": "sputum_reason_hiv_extrapulm",
        "end of treatment": "sputum_reason_end_treatment",
    }

    for cb in checkboxes:
        cb_id = cb.get('id', '')
        if not cb_id:
            continue
        css = f"#{cb_id}"
        label = cb.get('labelText', '').lower()

        # Try X-ray findings match
        for pattern, field_key in xray_label_map.items():
            if pattern in label:
                # Special case: "discrete" could match "discrete nodule" or "discrete linear"
                if pattern == "nodule" and "discrete" in label:
                    xray_findings["xray_discrete_nodule"] = css
                    print(f"DEBUG: Discovered xray finding '{field_key}' -> {css} (label: '{label[:40]}')")
                elif pattern == "nodule" and "discrete" not in label:
                    xray_findings["xray_nodules"] = css
                    print(f"DEBUG: Discovered xray finding '{field_key}' -> {css} (label: '{label[:40]}')")
                elif pattern != "nodule":
                    xray_findings[field_key] = css
                    print(f"DEBUG: Discovered xray finding '{field_key}' -> {css} (label: '{label[:40]}')")
                break

        # Try TB classification match
        for pattern, class_key in tb_label_map.items():
            if pattern in label:
                tb_class[class_key] = css
                print(f"DEBUG: Discovered TB classification '{class_key}' -> {css} (label: '{label[:40]}')")
                break

        # Try X-ray reason match
        for pattern, reason_key in xray_reason_map.items():
            if pattern in label:
                _update_page9(PAGE9_EXAM_DATE, reason_key, css)
                print(f"DEBUG: Discovered X-ray reason '{reason_key}' -> {css} (label: '{label[:40]}')")
                break

        # Try sputum reason match
        for pattern, reason_key in sputum_reason_map.items():
            if pattern in label:
                _update_page9(PAGE9_EXAM_DATE, reason_key, css)
                print(f"DEBUG: Discovered sputum reason '{reason_key}' -> {css} (label: '{label[:40]}')")
                break

    # === Map text/date inputs ===
    # Visible text inputs on Page 9, in DOM order, are typically:
    # exam_date, igra_date, xray_read_date, then sputum date fields
    # IMPORTANT: Filter to only Page 9 inputs (ID starts with 'hr513-') to
    # exclude the ever-present page search box (#_0b0b1a_input etc.)
    visible_inputs = [
        inp for inp in text_inputs
        if inp.get('isVisible') and inp.get('id') and inp['id'].startswith('hr513-')
    ]
    print(f"DEBUG: {len(visible_inputs)} Page 9 text inputs (hr513- prefix)")

    # === Map textareas ===
    textareas = page_elements.get('textareas', [])
    visible_textareas = [
        ta for ta in textareas
        if ta.get('isVisible') and ta.get('id') and ta['id'].startswith('hr513-')
    ]
    if visible_textareas:
        remarks_ta = f"#{visible_textareas[-1]['id']}"
        _update_page9(PAGE9_EXAM_DATE, "remarks_textarea", remarks_ta)
        print(f"DEBUG: Discovered remarks textarea: {remarks_ta}")

    if visible_inputs:
        # First visible input is typically the exam date
        _update_page9(PAGE9_EXAM_DATE, "exam_date_input", f"#{visible_inputs[0]['id']}")
        print(f"DEBUG: Discovered exam_date_input: #{visible_inputs[0]['id']}")

    # IGRA date and X-ray date need context — they appear after their radio buttons are clicked
    # We'll try to find them by position relative to other discovered elements
    # For now, map remaining visible inputs if they exist
    if len(visible_inputs) >= 2:
        _update_page9(PAGE9_EXAM_DATE, "igra_date_input", f"#{visible_inputs[1]['id']}")
        print(f"DEBUG: Discovered igra_date_input: #{visible_inputs[1]['id']}")

    if len(visible_inputs) >= 3:
        _update_page9(PAGE9_EXAM_DATE, "xray_read_date_input", f"#{visible_inputs[2]['id']}")
        print(f"DEBUG: Discovered xray_read_date_input: #{visible_inputs[2]['id']}")

    # Map sputum smear/culture dates if enough inputs are present
    # After xray_read_date, inputs come in groups of 2 (specimen_date, result_date) per row
    # 3 smear rows × 2 dates = 6 inputs, 3 culture rows × 2 dates = 6 inputs
    if len(visible_inputs) >= 4:
        date_offset = 3  # Start after exam_date, igra_date, xray_read_date
        smear_rows = PAGE9_EXAM_DATE.get("sputum_smear_rows", [])
        culture_rows = PAGE9_EXAM_DATE.get("sputum_culture_rows", [])

        for row_idx in range(3):
            idx_spec = date_offset + (row_idx * 2)
            idx_res = date_offset + (row_idx * 2) + 1
            if idx_spec < len(visible_inputs) and row_idx < len(smear_rows):
                smear_rows[row_idx]["specimen_date"] = f"#{visible_inputs[idx_spec]['id']}"
            if idx_res < len(visible_inputs) and row_idx < len(smear_rows):
                smear_rows[row_idx]["result_date"] = f"#{visible_inputs[idx_res]['id']}"

        culture_date_offset = date_offset + 6
        for row_idx in range(3):
            idx_spec = culture_date_offset + (row_idx * 2)
            idx_res = culture_date_offset + (row_idx * 2) + 1
            if idx_spec < len(visible_inputs) and row_idx < len(culture_rows):
                culture_rows[row_idx]["specimen_date"] = f"#{visible_inputs[idx_spec]['id']}"
            if idx_res < len(visible_inputs) and row_idx < len(culture_rows):
                culture_rows[row_idx]["result_date"] = f"#{visible_inputs[idx_res]['id']}"

    print("DEBUG: Page 9 selector discovery complete")


def discover_page9_deferred_selectors(page: Page) -> None:
    """
    Re-discover Page 9 selectors for fields that only appear after 
    radio buttons are clicked (IGRA fields, X-ray fields, sputum fields).
    
    Call this AFTER the IGRA radio has been clicked and fields have appeared.
    """
    from src.automation.field_map_emedical import PAGE9_EXAM_DATE

    print("DEBUG: Re-discovering Page 9 deferred selectors...")

    # Re-scan visible inputs now that more fields are shown
    # Only include Page 9 inputs (hr513- prefix) — exclude the page search box
    visible_inputs = page.evaluate("""() => {
        const inputs = document.querySelectorAll('input[type="text"], input:not([type])');
        const results = [];
        for (const inp of inputs) {
            if (inp.type === 'radio' || inp.type === 'checkbox' || inp.type === 'hidden') continue;
            const id = inp.id || '';
            if (!id.startsWith('hr513-')) continue;
            if (inp.offsetParent !== null || inp.offsetWidth > 0) {
                results.push({ id: id });
            }
        }
        return results;
    }""")

    visible_ids = [f"#{inp['id']}" for inp in visible_inputs if inp.get('id')]
    print(f"DEBUG: After IGRA click, {len(visible_ids)} visible inputs: {visible_ids[:6]}...")

    # Re-discover selects that may now be visible
    new_selects = page.evaluate("""() => {
        const selects = document.querySelectorAll('select');
        const results = [];
        for (const sel of selects) {
            if (sel.offsetParent === null && sel.offsetWidth === 0) continue;
            const opts = Array.from(sel.options).map(o => o.value);
            results.push({
                id: sel.id || '',
                hasQntfn: opts.includes('QNTFN'),
                hasPosNeg: opts.includes('POS') && opts.includes('NEG'),
                hasNtm: opts.includes('NTM'),
                optionCount: opts.length
            });
        }
        return results;
    }""")

    for sel in new_selects:
        sel_id = sel.get('id', '')
        if not sel_id:
            continue
        css = f"#{sel_id}"
        if sel.get('hasQntfn'):
            _update_page9(PAGE9_EXAM_DATE, "igra_test_dropdown", css)

    # Map date inputs by position
    if len(visible_ids) >= 1:
        _update_page9(PAGE9_EXAM_DATE, "exam_date_input", visible_ids[0])
    if len(visible_ids) >= 2:
        _update_page9(PAGE9_EXAM_DATE, "igra_date_input", visible_ids[1])
    if len(visible_ids) >= 3:
        _update_page9(PAGE9_EXAM_DATE, "xray_read_date_input", visible_ids[2])

    print("DEBUG: Page 9 deferred selector re-discovery complete")


def discover_page9_file_upload_selectors(page: Page) -> None:
    """
    Discover file upload popup selectors on Page 9.
    
    The upload area has an Add New button and a popup with:
    - Document type dropdown
    - File input
    - Description textarea
    - Save button
    """
    from src.automation.field_map_emedical import PAGE9_FILE_UPLOADS

    print("DEBUG: Discovering Page 9 file upload selectors...")
    time.sleep(0.5)

    # Find "Add New" button for uploads
    add_btn_id = page.evaluate("""() => {
        const buttons = document.querySelectorAll('button, a, input[type="button"], [role="button"]');
        for (const btn of buttons) {
            const text = (btn.textContent || btn.value || '').trim().toLowerCase();
            if ((text.includes('add new') || text.includes('add document') || text === 'add') && btn.id) {
                if (btn.offsetParent !== null || btn.offsetWidth > 0) {
                    return btn.id;
                }
            }
        }
        // Fallback: look for small add buttons
        for (const btn of buttons) {
            const text = (btn.textContent || btn.value || '').trim();
            if ((text === '+' || text === 'Add') && btn.id && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
                return btn.id;
            }
        }
        return null;
    }""")

    if add_btn_id:
        new_sel = f"#{add_btn_id}"
        old_sel = PAGE9_FILE_UPLOADS.get("add_new_button", "")
        if old_sel != new_sel:
            print(f"DEBUG: Updated file upload 'add_new_button': {old_sel} -> {new_sel}")
        PAGE9_FILE_UPLOADS["add_new_button"] = new_sel

    print("DEBUG: Page 9 file upload selector discovery complete")


def discover_page9_upload_popup_selectors(page: Page) -> None:
    """
    Discover selectors inside the file upload popup dialog.
    Must be called AFTER the upload popup is open.
    """
    from src.automation.field_map_emedical import PAGE9_FILE_UPLOADS

    print("DEBUG: Discovering upload popup selectors...")

    popup_info = page.evaluate("""() => {
        const result = { selects: [], fileInputs: [], textareas: [], buttons: [] };
        
        // Only look inside the dialog popup — elements whose ID contains '-dlg-'
        
        // Find visible selects inside dialog (document type dropdown)
        const selects = document.querySelectorAll('select');
        for (const sel of selects) {
            const id = sel.id || '';
            if (!id.includes('-dlg-')) continue;
            if (sel.offsetParent !== null || sel.offsetWidth > 0) {
                const opts = Array.from(sel.options).map(o => o.value);
                result.selects.push({
                    id: id,
                    hasDocTypes: opts.includes('RIMEVR') || opts.includes('OTHR') || opts.includes('TIRPT'),
                    optionCount: opts.length
                });
            }
        }
        
        // Find file inputs (these may not have -dlg- but are rarely duplicated)
        const fileInputs = document.querySelectorAll('input[type="file"]');
        for (const fi of fileInputs) {
            result.fileInputs.push({ id: fi.id || '' });
        }
        
        // Find textareas inside dialog (description)
        const textareas = document.querySelectorAll('textarea');
        for (const ta of textareas) {
            const id = ta.id || '';
            if (!id.includes('-dlg-')) continue;
            if (ta.offsetParent !== null || ta.offsetWidth > 0) {
                result.textareas.push({ id: id });
            }
        }
        // Also check for text inputs inside dialog that could be description fields
        const textInputs = document.querySelectorAll('input[type="text"]');
        for (const inp of textInputs) {
            const id = inp.id || '';
            if (!id.includes('-dlg-')) continue;
            if (inp.offsetParent !== null && !id.includes('file')) {
                result.textareas.push({ id: id });
            }
        }
        
        // Find save/upload buttons inside dialog
        const buttons = document.querySelectorAll('button, input[type="button"], a[role="button"]');
        for (const btn of buttons) {
            const id = btn.id || '';
            if (!id.includes('-dlg-')) continue;
            const text = (btn.textContent || btn.value || '').trim().toLowerCase();
            if ((text.includes('save') || text.includes('upload') || text.includes('ok')) && id) {
                result.buttons.push({ id: id, text: text });
            }
        }
        
        return result;
    }""")

    # Map document type dropdown
    for sel in popup_info.get('selects', []):
        if sel.get('hasDocTypes') and sel.get('id'):
            new_sel = f"#{sel['id']}"
            old_sel = PAGE9_FILE_UPLOADS.get("document_type_dropdown", "")
            if old_sel != new_sel:
                print(f"DEBUG: Updated upload 'document_type_dropdown': {old_sel} -> {new_sel}")
            PAGE9_FILE_UPLOADS["document_type_dropdown"] = new_sel
            break

    # Map file input
    for fi in popup_info.get('fileInputs', []):
        if fi.get('id'):
            new_sel = f"#{fi['id']}"
            old_sel = PAGE9_FILE_UPLOADS.get("file_input", "")
            if old_sel != new_sel:
                print(f"DEBUG: Updated upload 'file_input': {old_sel} -> {new_sel}")
            PAGE9_FILE_UPLOADS["file_input"] = new_sel
            break

    # Map description textarea
    for ta in popup_info.get('textareas', []):
        if ta.get('id'):
            new_sel = f"#{ta['id']}"
            old_sel = PAGE9_FILE_UPLOADS.get("description_textarea", "")
            if old_sel != new_sel:
                print(f"DEBUG: Updated upload 'description_textarea': {old_sel} -> {new_sel}")
            PAGE9_FILE_UPLOADS["description_textarea"] = new_sel
            break

    # Map save button (prefer "save" over "ok" or "upload")
    for btn in sorted(popup_info.get('buttons', []), key=lambda b: 0 if 'save' in b.get('text', '') else 1):
        if btn.get('id'):
            new_sel = f"#{btn['id']}"
            old_sel = PAGE9_FILE_UPLOADS.get("save_button", "")
            if old_sel != new_sel:
                print(f"DEBUG: Updated upload 'save_button': {old_sel} -> {new_sel}")
            PAGE9_FILE_UPLOADS["save_button"] = new_sel
            break

    print("DEBUG: Upload popup selector discovery complete")


def discover_navigation_buttons(page: Page, page_num: int) -> None:
    """
    Discover the Next/continue navigation button for a given page.
    
    Looks for buttons with text like 'Next', 'Continue', 'Save & Continue', etc.
    Updates PAGE_NAVIGATION[f'page{page_num}_next'].
    """
    from src.automation.field_map_emedical import PAGE_NAVIGATION
    _discover_next_button(page, PAGE_NAVIGATION, f'page{page_num}_next', f"Page {page_num}")


# ============================================================
# Internal helpers
# ============================================================

def _apply_updates(field_dict: dict, updates: dict, page_label: str) -> None:
    """Apply discovered selectors to a field dict, logging changes."""
    for field_key, new_selector in updates.items():
        if new_selector and field_key in field_dict:
            old_sel = field_dict[field_key].get('selector', '')
            if old_sel != new_selector:
                print(f"DEBUG: Updated {page_label} '{field_key}': {old_sel} -> {new_selector}")
                field_dict[field_key]['selector'] = new_selector
            else:
                print(f"DEBUG: {page_label} '{field_key}' unchanged: {new_selector}")
        elif not new_selector and field_key in field_dict:
            print(f"WARNING: Could not discover selector for {page_label} field '{field_key}'")


def _update_nav(nav_dict: dict, key: str, new_selector: str) -> None:
    """Update a navigation button selector."""
    old_sel = nav_dict.get(key, '')
    if old_sel != new_selector:
        print(f"DEBUG: Updated nav '{key}': {old_sel} -> {new_selector}")
    nav_dict[key] = new_selector


def _update_page9(page9_dict: dict, key: str, new_selector: str) -> None:
    """Update a Page 9 selector."""
    old_sel = page9_dict.get(key, '')
    if old_sel != new_selector:
        print(f"DEBUG: Updated Page 9 '{key}': {old_sel} -> {new_selector}")
    page9_dict[key] = new_selector


def _discover_next_button(page: Page, nav_dict: dict, nav_key: str, page_label: str) -> None:
    """Discover the Next/Continue button on the current page."""
    button_id = page.evaluate("""() => {
        const buttons = document.querySelectorAll('button, a, input[type="button"], input[type="submit"], [role="button"]');
        // Priority 1: button with text "Next"
        for (const btn of buttons) {
            const text = (btn.textContent || btn.value || '').trim().toLowerCase();
            if (text === 'next' && btn.id && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
                return btn.id;
            }
        }
        // Priority 2: button with text containing "next" or "continue" or "save"
        for (const btn of buttons) {
            const text = (btn.textContent || btn.value || '').trim().toLowerCase();
            if ((text.includes('next') || text.includes('continue') || text.includes('save & continue'))
                && btn.id && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
                return btn.id;
            }
        }
        return null;
    }""")

    if button_id:
        _update_nav(nav_dict, nav_key, f"#{button_id}")
        print(f"DEBUG: Discovered {page_label} Next button: #{button_id}")
    else:
        print(f"WARNING: Could not discover Next button for {page_label}")
