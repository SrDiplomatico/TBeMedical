# PDF Form Data Extractor - AI Coding Instructions

## Project Overview
Python Windows desktop application that batch extracts form field data from filled-out USCIS I-693 PDFs (fillable AcroForm fields) and automates entry into Australia's eMedical system. Processes up to 10 patients concurrently, each with 3 files.

**Target System**: [Australia eMedical Portal](https://www.emedical.immi.gov.au/eMedUI/eMedical)

## Patient File Structure
Each patient requires **3 files** in the batch folder:
```
batch_folder/
├── Smith_I693.pdf           # I-693 form (data extraction source)
├── Smith_LabResults.pdf     # Lab results (upload on final page)
├── Smith_ChestXray.pdf      # Chest x-ray report (upload on final page)
├── Johnson_I693.pdf
├── Johnson_LabResults.pdf
├── Johnson_ChestXray.pdf
└── ...
```
**File naming convention**: `{PatientName}_I693.pdf`, `{PatientName}_LabResults.pdf`, `{PatientName}_ChestXray.pdf`
- Patient name prefix must match exactly across all 3 files
- App groups files by matching prefix before the underscore

## Technology Stack
- **Language**: Python 3.11+
- **PDF Parsing**: PyMuPDF (`fitz`) for AcroForm field extraction
- **UI Framework**: tkinter (built-in, lightweight)
- **Browser Automation**: Playwright (preferred) or Selenium for eMedical form filling
- **Data Storage**: JSON for extracted records, SQLite for batch tracking

## Architecture

### Project Structure
```
src/
├── main.py              # Application entry point
├── ui/                  # tkinter UI components
│   ├── main_window.py   # Main application window (batch list, status, progress)
│   ├── login_dialog.py  # Secure credential entry for eMedical login
│   └── batch_monitor.py # Real-time automation progress display
├── parser/
│   ├── pdf_reader.py    # PDF field extraction using PyMuPDF
│   └── field_mapping.py # I-693 field name → data model mapping
├── models/
│   └── i693_form.py     # Dataclass for I-693 form structure
├── automation/
│   ├── browser.py       # Playwright browser session management
│   ├── emedical.py      # eMedical page navigation & form filling
│   ├── pages/           # Page-specific automation
│   │   ├── login.py     # Login page handling
│   │   ├── page1.py     # First data entry page
│   │   ├── page2.py     # Second data entry page
│   │   ├── page3.py     # Third data entry page
│   │   └── page4.py     # Final page / submission
│   └── field_map_emedical.py  # I-693 fields → eMedical selectors by page
└── config/
    └── settings.py      # Timing delays, retry settings
```

### Key Data Flows
1. User selects batch folder containing patient files (up to 10 patients, 3 files each)
2. App groups files by patient (I-693 + lab results + chest x-ray)
3. Parser extracts AcroForm fields from each I-693 PDF
4. UI displays patient list with extraction status and file validation
5. User enters eMedical credentials in app (not stored to disk)
6. **Concurrent automation**: Opens up to 10 browser tabs (one per patient)
7. Each tab: login → fill pages 1-3 → upload files on page 4 → **STOP before final submit**
8. User manually reviews each tab's uploads, then clicks submit
9. UI tracks which patients are ready for review vs submitted

## Concurrent Processing Model
```
┌─────────────────────────────────────────────────────────┐
│  Main App (tkinter)                                     │
│  - File selection & grouping                            │
│  - Credential entry                                     │
│  - Progress monitoring for all 10 tabs                  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Browser Context (single login session, shared cookies) │
├─────────┬─────────┬─────────┬─────────┬─────────────────┤
│  Tab 1  │  Tab 2  │  Tab 3  │   ...   │     Tab 10      │
│Patient 1│Patient 2│Patient 3│         │   Patient 10    │
│ ✓ Done  │ ✓ Done  │ Running │         │    Queued       │
└─────────┴─────────┴─────────┴─────────┴─────────────────┘
```

## I-693 → eMedical Field Mapping
Create mapping from I-693 PDF fields to eMedical web form selectors, organized by page:
```python
# field_map_emedical.py
EMEDICAL_PAGES = {
    "page1": {
        "applicant.family_name": "#familyName",
        "applicant.given_name": "#givenNames",
        "applicant.dob": "#dateOfBirth",
        # ... page 1 fields
    },
    "page2": {
        # ... page 2 fields
    },
    # ... pages 3-4
}

# Button selectors for page navigation
PAGE_NAVIGATION = {
    "page1_next": "#nextButton",      # Update with actual selectors
    "page2_next": "#submitBtn",
    "page3_ok": ".modal-ok",
    "final_submit": "#completeButton",  # DO NOT auto-click - user reviews first
}

# File upload selectors on final page
FILE_UPLOADS = {
    "lab_results": "#labResultsUpload",
    "chest_xray": "#chestXrayUpload",
}
```

## Development Conventions

### PDF Field Extraction Pattern
```python
import fitz  # PyMuPDF

def extract_fields(pdf_path: str) -> dict[str, str]:
    doc = fitz.open(pdf_path)
    fields = {}
    for page in doc:
        for widget in page.widgets():
            if widget.field_name:
                fields[widget.field_name] = widget.field_value or ""
    return fields
```

### Browser Automation Pattern
```python
from playwright.sync_api import sync_playwright

class EMedicalAutomation:
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.context = self.browser.new_context()  # Shared session for all tabs
    
    def login(self, username: str, password: str):
        # Login in first tab, cookies shared across all tabs
        page = self.context.new_page()
        page.goto("https://www.emedical.immi.gov.au/eMedUI/eMedical")
        page.fill("#username", username)  # Update selectors
        page.fill("#password", password)
        page.click("#loginButton")
        page.wait_for_load_state("networkidle")
        return page
    
    def process_patient(self, page, patient_data: PatientFiles):
        """Process one patient in one tab - stops before final submit"""
        # Fill pages 1-3
        for page_num in range(1, 4):
            self.fill_page(page, page_num, patient_data.i693_data)
            self.click_next(page, page_num)
        
        # Page 4: Upload files
        page.set_input_files("#labResultsUpload", patient_data.lab_results_path)
        page.set_input_files("#chestXrayUpload", patient_data.chest_xray_path)
        
        # STOP HERE - Do NOT click final submit
        # User will manually review and submit
    
    def run_batch(self, patients: list[PatientFiles], credentials):
        self.login(credentials.username, credentials.password)
        
        # Open tabs for all patients (up to 10)
        for patient in patients[:10]:
            tab = self.context.new_page()
            self.process_patient(tab, patient)
        
        # All tabs now waiting at final submit for user review
```

### Data Validation
- **A-Number**: Strip leading 'A', validate 9 digits, store as string
- **Dates**: Parse from PDF format, convert to eMedical expected format (likely DD/MM/YYYY for AU)
- **Checkboxes**: Map to appropriate eMedical radio/checkbox interactions

### Error Handling
- Skip unreadable PDFs, log error, continue batch
- Validate PDF contains expected I-693 fields before processing
- Pause automation on eMedical errors, allow user intervention
- Handle session timeouts gracefully (prompt re-login)

## Browser Automation Guidelines
- **Credentials in memory only** - entered via login dialog, never persisted to disk
- **Visible browser** - headless=False so user can monitor/intervene
- **Configurable delays** - eMedical may need delays between fields/pages
- **Multi-step navigation** - handle next/submit/ok buttons between pages
- **Wait for page loads** - use `wait_for_load_state("networkidle")` after navigation
- **Error recovery** - if automation fails, log error, skip form, continue batch
- **Session timeout handling** - detect timeout, prompt re-login, resume batch
- **CRITICAL: Stop before final submit** - all tabs pause at upload page for user review

## Build & Run
```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install pymupdf playwright

# Install Playwright browsers (first time only)
playwright install chromium

# Run application
python src/main.py
```

### Dependencies (`requirements.txt`)
```
PyMuPDF>=1.23.0
playwright>=1.40.0
```

## Testing
```powershell
pytest tests/ -v
```
- Use synthetic I-693 PDFs with known field values in `tests/fixtures/`
- Test partial completions (missing fields should not crash)
- Test batch processing with mix of valid/invalid PDFs
- Mock browser automation for unit tests
