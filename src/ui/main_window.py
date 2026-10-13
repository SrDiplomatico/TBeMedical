"""Main application window with patient bucket UI."""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Optional
import threading
import subprocess
import os

from src.config.settings import MAX_CONCURRENT_PATIENTS
from src.config.credential_store import load_credentials, save_credentials
from src.models.i693_form import PatientFiles
from src.parser.pdf_reader import extract_i693_data, validate_i693_form
from src.automation.field_map_emedical import sanitize_name
from src.ui.login_dialog import LoginDialog, Credentials
from src.ui.patient_bucket import PatientBucket, PatientBucketData
from src.ui.batch_monitor import PatientStatus


class MainWindow:
    """Main application window for PDF Form Data Extractor."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PDF Form Data Extractor - eMedical Automation")
        self.root.geometry("850x650")
        self.root.minsize(750, 550)
        
        # State
        self.patient_buckets: list[PatientBucket] = []
        saved_credentials = load_credentials()
        self.credentials = Credentials(*saved_credentials) if saved_credentials else None
        self.automation_running = False
        
        self._create_widgets()
        self._create_menu()
    
    def _create_menu(self):
        """Create application menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Clear All", command=self._clear_all)
        file_menu.add_separator()
        file_menu.add_command(label="Change eMedical Credentials...", command=self._change_credentials)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
    
    def _create_widgets(self):
        """Create main window widgets."""
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        
        # ===== Header =====
        header = ttk.Frame(self.root, padding="10")
        header.grid(row=0, column=0, sticky="ew")
        
        ttk.Label(
            header, 
            text="Select files for each patient, then start automation",
            font=("Segoe UI", 10)
        ).pack(side=tk.LEFT)
        
        self.start_button = ttk.Button(
            header,
            text="▶ Start Automation",
            command=self._start_automation,
            state=tk.DISABLED
        )
        self.start_button.pack(side=tk.RIGHT)
        
        # Stop button (initially hidden)
        self.stop_button = ttk.Button(
            header,
            text="⏹ STOP",
            command=self._stop_automation,
            style="Stop.TButton"
        )
        self.stop_button.pack(side=tk.RIGHT, padx=(0, 10))
        self.stop_button.pack_forget()  # Hide initially
        
        # Configure stop button style (red background)
        style = ttk.Style()
        style.configure("Stop.TButton", foreground="red", font=("Segoe UI", 10, "bold"))
        
        # Start page selector
        start_page_frame = ttk.Frame(header)
        start_page_frame.pack(side=tk.RIGHT, padx=(0, 20))
        
        ttk.Label(start_page_frame, text="Start from:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.start_page_var = tk.StringVar(value="Login (New Case)")
        self.start_page_combo = ttk.Combobox(
            start_page_frame,
            textvariable=self.start_page_var,
            values=[
                "Login (New Case)",
                "Page 1 (Already Logged In)",
                "Page 2 (Applicant Details)",
                "Page 3 (Address)",
                "Page 4 (Photo)",
                "Page 9 (Exam Data)",
                "Page 9 (No Uploads)"
            ],
            state="readonly",
            width=24
        )
        self.start_page_combo.pack(side=tk.LEFT)
        
        # Skip the checkpoint pauses and run straight through to the final submit page
        self.skip_checkpoints_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            start_page_frame,
            text="Run straight through",
            variable=self.skip_checkpoints_var,
        ).pack(side=tk.LEFT, padx=(10, 0))
        
        # Launch Chrome button (for "Already Logged In" mode)
        self.launch_chrome_btn = ttk.Button(
            start_page_frame,
            text="🌐 Launch Chrome",
            command=self._launch_chrome_debug,
            width=15
        )
        self.launch_chrome_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # Upload Documents button (re-upload when on last page)
        self.upload_docs_btn = ttk.Button(
            start_page_frame,
            text="📎 Upload Docs",
            command=self._upload_documents_manual,
            width=14
        )
        self.upload_docs_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # ===== Main content - Patient Buckets =====
        content = ttk.Frame(self.root, padding="10")
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        
        # Create patient buckets
        for i in range(MAX_CONCURRENT_PATIENTS):
            bucket = PatientBucket(
                content, 
                bucket_number=i + 1,
                on_change=self._on_bucket_change
            )
            bucket.grid(row=0, column=i, sticky="nsew", padx=5, pady=5)
            self.patient_buckets.append(bucket)
        
        # ===== Details Panel =====
        details_frame = ttk.LabelFrame(self.root, text="Extracted Data Preview", padding="10")
        details_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        self.details_text = tk.Text(
            details_frame,
            height=8,
            font=("Consolas", 9),
            state=tk.DISABLED,
            wrap=tk.WORD
        )
        self.details_text.pack(fill=tk.X, expand=True)
        
        # Extract preview button
        ttk.Button(
            details_frame,
            text="Preview Extracted Data",
            command=self._preview_extraction
        ).pack(pady=(5, 0))
        
        # ===== Status bar =====
        self.status_var = tk.StringVar(value="Select files for at least one patient to begin")
        status_bar = ttk.Label(
            self.root, 
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(5, 2)
        )
        status_bar.grid(row=3, column=0, sticky="ew")
    
    def _get_start_page(self) -> int:
        """Get the selected start page number.
        
        Returns:
            0 = Login (New Case) - do login + start from page 1
            1 = Page 1 (Already Logged In) - skip login, start from page 1
            2 = Page 2 (Applicant Details) - skip login, resume from page 2
            3 = Page 3 (Address) - skip login, resume from page 3
            4 = Page 4 (Photo) - skip login, resume from page 4
            9 = Page 9 (Exam Data) - skip login, resume from page 9
        """
        selection = self.start_page_var.get()
        if "Login" in selection:
            return 0  # Do login + page 1
        elif "Page 1" in selection:
            return 1  # Skip login, start at page 1
        elif "Page 2" in selection:
            return 2
        elif "Page 3" in selection:
            return 3
        elif "Page 4" in selection:
            return 4
        elif "Page 9" in selection:
            return 9
        return 0  # Default to login flow
    
    def _get_skip_uploads(self) -> bool:
        """Returns True if the selected start option requests skipping file uploads."""
        return "No Uploads" in self.start_page_var.get()
    
    def _on_bucket_change(self):
        """Handle changes in patient buckets."""
        # Count complete buckets
        complete_count = sum(1 for b in self.patient_buckets if b.is_complete())
        
        if complete_count > 0:
            self.start_button.config(state=tk.NORMAL)
            self.status_var.set(f"{complete_count} patient(s) ready for automation")
        else:
            self.start_button.config(state=tk.DISABLED)
            self.status_var.set("Select files for at least one patient to begin")
    
    def _preview_extraction(self):
        """Preview extracted data from I-693 files."""
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        
        lines = []
        
        for bucket in self.patient_buckets:
            if bucket.is_empty():
                continue
            
            data = bucket.get_data()
            lines.append(f"=== {data.patient_label} ===")
            
            if data.i693_path and data.i693_path.exists():
                try:
                    form_data = extract_i693_data(data.i693_path)
                    
                    # Applicant Info
                    lines.append("--- APPLICANT INFO ---")
                    lines.append(f"  Name: {form_data.applicant.given_name} {form_data.applicant.middle_name} {form_data.applicant.family_name}")
                    
                    # Warn if eMedical will reject characters in the name
                    name_changes = self._get_name_adjustments(form_data)
                    if name_changes:
                        bucket.set_notice(
                            "⚠ Name adjusted for eMedical: "
                            + "; ".join(name_changes)
                        )
                        lines.append("  ⚠ Name adjusted for eMedical (unsupported characters removed):")
                        for change in name_changes:
                            lines.append(f"      {change}")
                    else:
                        bucket.set_notice("")
                    
                    lines.append(f"  A-Number: {form_data.applicant.a_number}")
                    lines.append(f"  DOB: {form_data.applicant.date_of_birth}")
                    lines.append(f"  Sex: {form_data.applicant.sex}")
                    lines.append(f"  Birth Place: {form_data.applicant.city_of_birth}, {form_data.applicant.country_of_birth}")
                    unit_text = " ".join(
                        p for p in (form_data.applicant.unit_type, form_data.applicant.apt_number) if p
                    )
                    lines.append(f"  Address: {form_data.applicant.street_address} {unit_text}".rstrip())
                    lines.append(f"           {form_data.applicant.city}, {form_data.applicant.state} {form_data.applicant.zip_code}")
                    lines.append(f"  Phone: {form_data.applicant.phone}")
                    lines.append(f"  ID: {form_data.applicant.id_type} - {form_data.applicant.id_number}")
                    
                    # Civil Surgeon Info
                    lines.append("")
                    lines.append("--- CIVIL SURGEON ---")
                    lines.append(f"  Name: {form_data.civil_surgeon.surgeon_given_name} {form_data.civil_surgeon.surgeon_family_name}")
                    lines.append(f"  USCIS ID: {form_data.civil_surgeon.uscis_id}")
                    lines.append(f"  Practice: {form_data.civil_surgeon.practice_name}")
                    lines.append(f"  Exam Date: {form_data.examination.exam_date}")
                    lines.append(f"  Overall Finding: {form_data.examination.overall_finding}")
                    
                    # TB Screening
                    lines.append("")
                    lines.append("--- TB SCREENING ---")
                    lines.append(f"  Test Type: {form_data.examination.tb_test_type}")
                    if form_data.examination.tb_skin_test_date:
                        lines.append(f"  TST Date: {form_data.examination.tb_skin_test_date}")
                        lines.append(f"  TST Result: {form_data.examination.tb_skin_test_result}")
                    if form_data.examination.igra_test_date:
                        lines.append(f"  IGRA Date: {form_data.examination.igra_test_date}")
                        lines.append(f"  IGRA Result: {form_data.examination.igra_test_result}")
                    lines.append(f"  TB Classification: {form_data.examination.tb_classification}")
                    
                    # Chest X-ray
                    if form_data.examination.chest_xray_date:
                        lines.append(f"  X-ray Date: {form_data.examination.chest_xray_date}")
                        lines.append(f"  X-ray Result: {form_data.examination.chest_xray_result}")
                    
                    # Vaccinations
                    lines.append("")
                    lines.append("--- VACCINATIONS ---")
                    lines.append(f"  Tdap Type: {form_data.vaccinations.tdap_type}")
                    lines.append(f"  Tdap Date: {form_data.vaccinations.tdap_date_1}")
                    lines.append(f"  Polio Type: {form_data.vaccinations.polio_type}")
                    lines.append(f"  Polio Date: {form_data.vaccinations.polio_date_1}")
                    lines.append(f"  MMR Date 1: {form_data.vaccinations.mmr_date_1}")
                    lines.append(f"  MMR Date 2: {form_data.vaccinations.mmr_date_2}")
                    lines.append(f"  Varicella Date 1: {form_data.vaccinations.varicella_date_1}")
                    lines.append(f"  Varicella Date 2: {form_data.vaccinations.varicella_date_2}")
                    lines.append(f"  Influenza: {form_data.vaccinations.influenza_date_1}")
                    lines.append(f"  Hep B: {form_data.vaccinations.hep_b_date_1}")
                    lines.append(f"  COVID: {form_data.vaccinations.covid_date_1}")
                    
                    # Results
                    lines.append("")
                    lines.append("--- RESULTS ---")
                    lines.append(f"  Vaccination Result: {form_data.examination.vaccination_results}")
                    lines.append(f"  Remarks: {form_data.examination.vaccination_remarks}")
                    
                    warnings = validate_i693_form(form_data)
                    if warnings:
                        lines.append("")
                        lines.append(f"  ⚠ Warnings: {', '.join(warnings)}")
                except Exception as e:
                    lines.append(f"  ❌ Error: {e}")
            else:
                lines.append("  (No I-693 file selected)")
            
            lines.append("")
        
        if not lines:
            lines.append("No patient data to preview. Select files first.")
        
        self.details_text.insert(tk.END, "\n".join(lines))
        self.details_text.config(state=tk.DISABLED)
    
    def _get_name_adjustments(self, form_data) -> list[str]:
        """
        Report name fields that eMedical will not accept as-is.
        
        eMedical rejects periods and other punctuation in name fields, so the
        automation strips them before typing. This lists any resulting change
        so the user knows the eMedical record will not match the I-693 exactly.
        
        Args:
            form_data: Extracted I693Form
            
        Returns:
            List of "Field: 'original' → 'sanitized'" strings (empty if no change)
        """
        changes = []
        for label, raw in (
            ("Given name", form_data.applicant.given_name),
            ("Family name", form_data.applicant.family_name),
        ):
            if not raw:
                continue
            cleaned = sanitize_name(raw)
            if cleaned != raw:
                changes.append(f"{label}: '{raw}' → '{cleaned}'")
        return changes
    
    def _clear_all(self):
        """Clear all patient buckets."""
        for bucket in self.patient_buckets:
            bucket._clear_all()
        
        self.details_text.config(state=tk.NORMAL)
        self.details_text.delete(1.0, tk.END)
        self.details_text.config(state=tk.DISABLED)
    
    def _get_ready_patients(self) -> list[PatientFiles]:
        """Get PatientFiles for all complete buckets."""
        patients = []
        
        for bucket in self.patient_buckets:
            if not bucket.is_complete():
                continue
            
            data = bucket.get_data()
            
            patient = PatientFiles(
                patient_name=data.patient_label,
                i693_path=data.i693_path,
                lab_results_path=data.lab_results_path,
                chest_xray_path=data.chest_xray_path,
            )
            
            # Extract I-693 data
            try:
                patient.i693_data = extract_i693_data(data.i693_path)
                patient.is_valid = True
                
                # Surface any name characters eMedical will not accept
                name_changes = self._get_name_adjustments(patient.i693_data)
                bucket.set_notice(
                    "⚠ Name adjusted for eMedical: " + "; ".join(name_changes)
                    if name_changes else ""
                )
            except Exception as e:
                patient.validation_errors.append(f"Extraction error: {e}")
                patient.is_valid = False
            
            patients.append(patient)
        
        return patients
    
    def _get_patients_with_files(self) -> list:
        """Get PatientFiles for buckets that have at least one file (for upload-only mode)."""
        from src.models.i693_form import PatientFiles
        
        patients = []
        for bucket in self.patient_buckets:
            if not bucket.has_any_files():
                continue
            
            data = bucket.get_data()
            patient = PatientFiles(
                patient_name=data.patient_label,
                i693_path=data.i693_path,
                lab_results_path=data.lab_results_path,
                chest_xray_path=data.chest_xray_path,
            )
            patient.is_valid = True  # No extraction needed for upload-only
            patients.append(patient)
        
        return patients
    
    def _start_automation(self):
        """Start the batch automation process."""
        if self.automation_running:
            messagebox.showwarning(
                "Automation Running",
                "Automation is already in progress."
            )
            return
        
        patients = self._get_ready_patients()
        
        print(f"DEBUG _start_automation: Got {len(patients)} patients from _get_ready_patients:")
        for idx, p in enumerate(patients):
            print(f"  DEBUG: Patient {idx+1}: {p.patient_name}, has i693_data: {p.i693_data is not None}")
        
        if not patients:
            messagebox.showwarning(
                "No Patients Ready",
                "Please select all 3 files for at least one patient."
            )
            return
        
        # Validate that I-693 data was extracted for every patient.
        # Without this, _process_patient raises immediately on Page 9 / fill steps.
        bad = [p for p in patients if p.i693_data is None]
        if bad:
            details = "\n".join(
                f"- {p.patient_name}: {'; '.join(p.validation_errors) or 'extraction returned no data'}"
                for p in bad
            )
            messagebox.showerror(
                "I-693 Extraction Failed",
                "Could not extract I-693 form data for the following patient(s):\n\n"
                f"{details}\n\n"
                "Make sure each I-693 PDF has fillable form fields filled in, "
                "then re-select the file and try again."
            )
            return
        
        # Get selected start page
        start_page = self._get_start_page()
        skip_uploads = self._get_skip_uploads()
        
        # For CDP modes (Already Logged In / Resume), ensure Chrome debug port is ready
        if start_page >= 1:
            if not self._ensure_chrome_debug_ready(start_page):
                return  # Chrome not ready or user cancelled
        
        if start_page >= 1:
            self._run_automation(patients, start_page, skip_uploads)
        elif self.credentials:
            self._run_automation(patients, start_page, skip_uploads)
        else:
            LoginDialog(
                self.root,
                lambda creds: self._on_login(creds, patients, start_page, skip_uploads),
            )
    
    def _change_credentials(self):
        """Open the login dialog to update stored credentials without starting automation."""
        def _on_creds(creds: Credentials):
            save_credentials(creds.username, creds.password)
            self.credentials = creds
            stored_indicator = "*" * len(creds.password)
            self.status_var.set(
                f"Credentials saved for '{creds.username}' (password {stored_indicator})."
            )

        LoginDialog(self.root, _on_creds, initial_credentials=self.credentials)

    def _on_login(self, credentials: Credentials, patients: list[PatientFiles], start_page: int = 1, skip_uploads: bool = False):
        """Handle login credentials received."""
        save_credentials(credentials.username, credentials.password)
        self.credentials = credentials
        self._run_automation(patients, start_page, skip_uploads)
    
    def _run_automation(self, patients: list[PatientFiles], start_page: int = 1, skip_uploads: bool = False):
        """Run the automation in a background thread."""
        if start_page == 0 and not self.credentials:
            return
        
        skip_checkpoints = self.skip_checkpoints_var.get()
        
        self.automation_running = True
        self.start_button.config(state=tk.DISABLED)
        self.start_button.pack_forget()  # Hide start button
        self.stop_button.pack(side=tk.RIGHT, padx=(0, 10))  # Show stop button
        self.status_var.set("Starting automation...")
        
        # Run in background thread
        thread = threading.Thread(
            target=self._automation_thread, 
            args=(patients, start_page, skip_uploads, skip_checkpoints),
            daemon=True
        )
        thread.start()
    
    def _automation_thread(self, patients: list[PatientFiles], start_page: int = 1, skip_uploads: bool = False, skip_checkpoints: bool = False):
        """Background thread for running automation."""
        print(f"DEBUG _automation_thread: Called with {len(patients)} patients, start_page={start_page}")
        for idx, p in enumerate(patients):
            print(f"  DEBUG: Thread patient {idx+1}: {p.patient_name}, has i693_data: {p.i693_data is not None}")
        
        stopped_by_user = False
        self._patient_statuses = {}  # Track patient statuses for error reporting
        
        try:
            from src.automation.emedical import EMedicalAutomation
            
            print("DEBUG _automation_thread: Creating EMedicalAutomation...")
            automation = EMedicalAutomation()
            print("DEBUG _automation_thread: Calling run_batch...")
            automation.run_batch(
                patients=patients,
                credentials=self.credentials,
                start_page=start_page,
                skip_uploads=skip_uploads,
                skip_checkpoints=skip_checkpoints,
                on_status_update=self._update_status_from_thread
            )
            print("DEBUG _automation_thread: run_batch completed successfully")
            
            # Check if stopped by user
            if EMedicalAutomation.is_stop_requested():
                stopped_by_user = True
                self.root.after(0, lambda: self.status_var.set(
                    "Automation stopped by user."
                ))
                self.root.after(0, lambda: messagebox.showinfo(
                    "Automation Stopped",
                    "Automation was stopped by user.\n\n" +
                    "Browser tabs remain open for manual review."
                ))
            else:
                # Check if any patients had errors
                error_patients = [
                    name for name, status in getattr(self, '_patient_statuses', {}).items()
                    if status and getattr(status, 'status', '') == 'error'
                ]
                if error_patients:
                    error_list = ', '.join(error_patients)
                    self.root.after(0, lambda: self.status_var.set(
                        f"Automation finished with errors for: {error_list}"
                    ))
                    self.root.after(0, lambda el=error_list: messagebox.showwarning(
                        "Automation Finished with Errors",
                        f"Some patients had errors: {el}\n\n" +
                        "Please check the browser tabs and retry failed patients."
                    ))
                else:
                    self.root.after(0, lambda: self.status_var.set(
                        "Automation complete. Review tabs and submit manually."
                    ))
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Automation Complete",
                        "All forms have been filled.\n\n" +
                        "Please review each browser tab and click Submit manually."
                    ))
        
        except StopIteration as e:
            # User requested stop
            stopped_by_user = True
            print(f"DEBUG _automation_thread: Stopped by user: {e}")
            self.root.after(0, lambda: self.status_var.set("Automation stopped by user."))
            self.root.after(0, lambda: messagebox.showinfo(
                "Automation Stopped",
                "Automation was stopped by user.\n\n" +
                "Browser tabs remain open for manual review."
            ))
            
        except Exception as e:
            err_msg = str(e)  # Capture before 'e' is deleted after except block
            if "stopped by user" in err_msg.lower():
                stopped_by_user = True
                self.root.after(0, lambda: self.status_var.set("Automation stopped by user."))
            else:
                self.root.after(0, lambda: messagebox.showerror(
                    "Automation Error",
                    f"An error occurred: {err_msg}"
                ))
                self.root.after(0, lambda: self.status_var.set(f"Error: {err_msg}"))
        
        finally:
            self.automation_running = False
            self.root.after(0, self._restore_start_button)
    
    def _update_status_from_thread(self, patient_name: str, status: PatientStatus):
        """Update UI from automation thread (thread-safe)."""
        # Track status for error reporting at completion
        if hasattr(self, '_patient_statuses'):
            self._patient_statuses[patient_name] = status
        self.root.after(0, lambda: self.status_var.set(
            f"Processing: {patient_name} - Page {status.current_page}/4"
        ))
    
    def _stop_automation(self):
        """Stop the running automation process."""
        from src.automation.emedical import EMedicalAutomation
        
        if not self.automation_running:
            return
        
        # Request stop
        EMedicalAutomation.request_stop()
        self.status_var.set("Stopping automation... (will stop after current operation)")
        self.stop_button.config(state=tk.DISABLED, text="Stopping...")
    
    def _restore_start_button(self):
        """Restore the start button and hide stop button."""
        self.stop_button.pack_forget()  # Hide stop button
        self.stop_button.config(state=tk.NORMAL, text="⏹ STOP")  # Reset stop button state
        self.start_button.pack(side=tk.RIGHT)  # Show start button
        self.start_button.config(state=tk.NORMAL)
    
    def _ensure_chrome_debug_ready(self, start_page: int) -> bool:
        """Ensure Chrome is running with remote debugging port for CDP modes.
        
        Auto-launches Chrome if port 9222 is not open. Shows a dialog asking
        the user to log into eMedical and navigate to the correct page.
        
        Args:
            start_page: Page number to start from (1, 2, 3, 9, etc.)
            
        Returns:
            True if Chrome debug port is ready, False if failed or user cancelled.
        """
        import socket
        import time as _time
        
        def _port_open(port=9222):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                s.close()
                return result == 0
            except Exception:
                return False
        
        # If port already open, Chrome debug is already running
        if _port_open():
            self.status_var.set("Chrome debug port 9222 detected. Ready to connect.")
            return True
        
        # Port not open - auto-launch Chrome with debug mode
        self.status_var.set("Launching Chrome with remote debugging...")
        self.root.update()
        
        # Find Chrome executable
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        
        chrome_path = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_path = path
                break
        
        if not chrome_path:
            messagebox.showerror(
                "Chrome Not Found",
                "Could not find Chrome installation.\n\n"
                "Please manually launch Chrome with:\n"
                "chrome.exe --remote-debugging-port=9222\n\n"
                "Then try again."
            )
            return False
        
        try:
            # Use separate user data dir to avoid conflicts with existing Chrome
            user_data_dir = os.path.join(os.environ.get('TEMP', ''), 'chrome_emedical_debug')
            
            cmd = [
                chrome_path,
                "--remote-debugging-port=9222",
                f"--user-data-dir={user_data_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "https://www.emedical.immi.gov.au/eMedUI/eMedical"
            ]
            
            subprocess.Popen(cmd, shell=False)
            
            # Wait for port to become available (up to 15 seconds)
            self.status_var.set("Waiting for Chrome debug port to open...")
            self.root.update()
            
            port_opened = False
            for _ in range(30):  # 30 x 0.5s = 15 seconds
                _time.sleep(0.5)
                self.root.update()
                if _port_open():
                    port_opened = True
                    break
            
            if not port_opened:
                messagebox.showerror(
                    "Chrome Launch Failed",
                    "Chrome was launched but debug port 9222 is not responding.\n\n"
                    "This may mean another Chrome instance absorbed the new window.\n\n"
                    "To fix:\n"
                    "1. Close ALL Chrome windows completely\n"
                    "2. Try again"
                )
                return False
            
            # Chrome is running with debug port - ask user to log in
            page_descriptions = {
                1: "the Case Search / Dashboard page",
                2: "the new case Applicant Details page",
                3: "the patient's case on the Address page",
                9: "the patient's case on the Exam Data page",
            }
            page_desc = page_descriptions.get(start_page, f"Page {start_page}")
            
            result = messagebox.askokcancel(
                "Chrome Launched - Please Log In",
                f"Chrome has been launched with remote debugging.\n\n"
                f"Please complete these steps in the Chrome window:\n"
                f"1. Log into eMedical\n"
                f"2. Open/search for the patient's case\n"
                f"3. Navigate to {page_desc}\n\n"
                f"Click OK when you're on the correct page,\n"
                f"or Cancel to abort."
            )
            
            if not result:
                self.status_var.set("Automation cancelled.")
                return False
            
            self.status_var.set("Chrome ready. Starting automation...")
            return True
            
        except Exception as e:
            messagebox.showerror(
                "Chrome Launch Failed",
                f"Failed to launch Chrome:\n{e}\n\n"
                "Try manually running:\n"
                "chrome.exe --remote-debugging-port=9222"
            )
            return False
    
    def _upload_documents_manual(self):
        """Manually upload documents when user is already on the last page."""
        if self.automation_running:
            messagebox.showwarning(
                "Automation Running",
                "Cannot upload while automation is in progress."
            )
            return
        
        # Find the first bucket with ANY files (not requiring all 3)
        patients = self._get_patients_with_files()
        if not patients:
            messagebox.showwarning(
                "No Files Selected",
                "Please select at least one file for a patient."
            )
            return
        
        # If multiple patients, let user know we'll upload for the first one
        patient = patients[0]
        
        # Build file list showing which files are present
        file_lines = []
        if patient.i693_path and patient.i693_path.exists():
            file_lines.append(f"  I-693: {patient.i693_path.name}")
        if patient.lab_results_path and patient.lab_results_path.exists():
            file_lines.append(f"  Lab: {patient.lab_results_path.name}")
        if patient.chest_xray_path and patient.chest_xray_path.exists():
            file_lines.append(f"  X-ray: {patient.chest_xray_path.name}")
        
        file_text = "\n".join(file_lines)
        count = len(file_lines)
        
        result = messagebox.askokcancel(
            "Upload Documents",
            f"Will upload {count} file(s) for: {patient.patient_name}\n\n"
            f"Files:\n{file_text}\n\n"
            f"Make sure Chrome is on the last page (uploads page) for this patient.\n"
            f"Click OK to proceed."
        )
        if not result:
            return
        
        # Run upload in background thread
        self.automation_running = True
        self.upload_docs_btn.config(state=tk.DISABLED, text="Uploading...")
        self.status_var.set(f"Uploading documents for {patient.patient_name}...")
        
        thread = threading.Thread(
            target=self._upload_documents_thread,
            args=(patient,),
            daemon=True
        )
        thread.start()
    
    def _upload_documents_thread(self, patient: PatientFiles):
        """Background thread for manual document upload."""
        try:
            from src.automation.emedical import EMedicalAutomation
            
            automation = EMedicalAutomation()
            automation.upload_documents_only(patient)
            
            self.root.after(0, lambda: self.status_var.set(
                f"Documents uploaded for {patient.patient_name}. Review and submit manually."
            ))
            self.root.after(0, lambda: messagebox.showinfo(
                "Upload Complete",
                f"Documents uploaded for {patient.patient_name}.\n\n"
                "Please review the uploads in the browser and submit manually."
            ))
        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda: self.status_var.set(f"Upload error: {err_msg}"))
            self.root.after(0, lambda: messagebox.showerror(
                "Upload Error",
                f"Failed to upload documents:\n{err_msg}"
            ))
        finally:
            self.automation_running = False
            self.root.after(0, lambda: self.upload_docs_btn.config(
                state=tk.NORMAL, text="📎 Upload Docs"
            ))
    
    def _launch_chrome_debug(self):
        """Launch Chrome with remote debugging port enabled for 'Already Logged In' mode."""
        import socket
        import time as _time
        
        # Check if port 9222 is already in use (Chrome debug already running)
        def _port_open(port=9222):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                s.close()
                return result == 0
            except Exception:
                return False
        
        if _port_open():
            answer = messagebox.askyesno(
                "Chrome Already Running",
                "Chrome with remote debugging is already running on port 9222.\n\n"
                "Do you want to close it and relaunch a fresh Chrome?\n\n"
                "Yes → Kill existing Chrome and relaunch\n"
                "No  → Keep existing Chrome (log in there manually)"
            )
            if answer:
                # Kill all Chrome processes and relaunch below
                try:
                    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                                   capture_output=True, timeout=10)
                    _time.sleep(2)  # Wait for Chrome to fully close
                except Exception:
                    pass
                # Fall through to the launch logic below
            else:
                self.status_var.set("Chrome debug port 9222 already open. Ready for 'Already Logged In' mode.")
                return
        
        # Common Chrome installation paths on Windows
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        
        # Find Chrome
        chrome_path = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_path = path
                break
        
        if not chrome_path:
            messagebox.showerror(
                "Chrome Not Found",
                "Could not find Chrome installation.\n\n"
                "Please install Google Chrome or manually run:\n"
                "chrome.exe --remote-debugging-port=9222"
            )
            return
        
        # Check if regular Chrome is already running (will eat our --remote-debugging-port flag)
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            chrome_running = "chrome.exe" in result.stdout.lower()
        except Exception:
            chrome_running = False
        
        if chrome_running:
            answer = messagebox.askyesno(
                "Chrome Already Running",
                "Chrome is already running WITHOUT remote debugging.\n\n"
                "The remote debugging flag will be IGNORED when Chrome\n"
                "is already running with the same profile.\n\n"
                "Close ALL Chrome windows first?\n\n"
                "(Click Yes to close Chrome and relaunch,\n"
                " click No to try launching anyway with a separate profile)"
            )
            if answer:
                # Kill all Chrome processes
                try:
                    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], 
                                   capture_output=True, timeout=10)
                    _time.sleep(2)  # Wait for Chrome to fully close
                except Exception:
                    pass
        
        try:
            # Launch Chrome with remote debugging enabled
            # Use a separate user data dir to avoid conflicts with existing Chrome
            user_data_dir = os.path.join(os.environ.get('TEMP', ''), 'chrome_emedical_debug')
            
            cmd = [
                chrome_path,
                "--remote-debugging-port=9222",
                f"--user-data-dir={user_data_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "https://www.emedical.immi.gov.au/eMedUI/eMedical"
            ]
            
            subprocess.Popen(cmd, shell=False)
            
            # Wait for the port to become available (up to 10 seconds)
            self.status_var.set("Launching Chrome... waiting for debug port to open...")
            self.root.update()
            port_opened = False
            for _ in range(20):
                _time.sleep(0.5)
                if _port_open():
                    port_opened = True
                    break
            
            if port_opened:
                self.status_var.set("Chrome launched with debug port 9222. Log into eMedical, then start automation.")
                messagebox.showinfo(
                    "Chrome Launched",
                    "Chrome has been launched with remote debugging enabled.\n\n"
                    "Steps:\n"
                    "1. Log into eMedical in the Chrome window\n"
                    "2. Navigate to Case Search page\n"
                    "3. Select 'Page 1 (Already Logged In)' in this app\n"
                    "4. Click Start Automation"
                )
            else:
                self.status_var.set("Chrome launched but debug port not detected. Check if Chrome opened correctly.")
                messagebox.showwarning(
                    "Port Not Detected",
                    "Chrome was launched but port 9222 is not responding.\n\n"
                    "This usually means another Chrome instance is running\n"
                    "and absorbed the new window.\n\n"
                    "To fix:\n"
                    "1. Close ALL Chrome windows completely\n"
                    "2. Click 'Launch Chrome' again\n\n"
                    "Or manually run in Command Prompt:\n"
                    "chrome.exe --remote-debugging-port=9222"
                )
            
        except Exception as e:
            messagebox.showerror(
                "Launch Failed",
                f"Failed to launch Chrome:\n{e}\n\n"
                "Try manually running:\n"
                "chrome.exe --remote-debugging-port=9222"
            )
    
    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "About",
            "PDF Form Data Extractor\n\n"
            "Extracts I-693 form data and automates entry into eMedical.\n\n"
            f"Supports {MAX_CONCURRENT_PATIENTS} patients per batch.\n\n"
            "Each patient requires 3 files:\n"
            "  • I-693 Form (PDF)\n"
            "  • Lab Results (PDF)\n"
            "  • Chest X-ray Report (PDF)"
        )
    
    def run(self):
        """Start the main application loop."""
        self.root.mainloop()
