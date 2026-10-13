"""Patient bucket widget for file selection."""

import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class PatientBucketData:
    """Data from a patient bucket."""
    patient_label: str
    i693_path: Optional[Path] = None
    lab_results_path: Optional[Path] = None
    chest_xray_path: Optional[Path] = None
    
    def is_complete(self) -> bool:
        """Check if all 3 files are selected."""
        return all([
            self.i693_path and self.i693_path.exists(),
            self.lab_results_path and self.lab_results_path.exists(),
            self.chest_xray_path and self.chest_xray_path.exists(),
        ])
    
    def has_any_files(self) -> bool:
        """Check if at least one file is selected."""
        return any([
            self.i693_path and self.i693_path.exists(),
            self.lab_results_path and self.lab_results_path.exists(),
            self.chest_xray_path and self.chest_xray_path.exists(),
        ])
    
    def get_missing_files(self) -> list[str]:
        """Get list of missing file types."""
        missing = []
        if not self.i693_path or not self.i693_path.exists():
            missing.append("I-693 Form")
        if not self.lab_results_path or not self.lab_results_path.exists():
            missing.append("Lab Results")
        if not self.chest_xray_path or not self.chest_xray_path.exists():
            missing.append("Chest X-ray")
        return missing


class PatientBucket(ttk.LabelFrame):
    """
    Widget for selecting 3 files for one patient.
    Shows 3 file slots: I-693, Lab Results, Chest X-ray
    """
    
    def __init__(
        self, 
        parent: tk.Widget, 
        bucket_number: int,
        on_change: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent, text=f"Patient {bucket_number}", padding="10")
        
        self.bucket_number = bucket_number
        self.on_change = on_change
        
        # File paths
        self.i693_path: Optional[Path] = None
        self.lab_results_path: Optional[Path] = None
        self.chest_xray_path: Optional[Path] = None
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create the file selection widgets."""
        # Configure grid
        self.columnconfigure(1, weight=1)
        
        # Patient name/label entry
        ttk.Label(self, text="Label:").grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.label_entry = ttk.Entry(self, width=30)
        self.label_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=(0, 10))
        self.label_entry.insert(0, f"Patient {self.bucket_number}")
        
        # I-693 file
        ttk.Label(self, text="I-693 Form:").grid(row=1, column=0, sticky="w", pady=2)
        self.i693_label = ttk.Label(self, text="(not selected)", foreground="gray", anchor="w")
        self.i693_label.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(self, text="Browse...", width=10, command=self._select_i693).grid(row=1, column=2, pady=2)
        
        # Lab Results file
        ttk.Label(self, text="Lab Results:").grid(row=2, column=0, sticky="w", pady=2)
        self.lab_label = ttk.Label(self, text="(not selected)", foreground="gray", anchor="w")
        self.lab_label.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(self, text="Browse...", width=10, command=self._select_lab).grid(row=2, column=2, pady=2)
        
        # Chest X-ray file
        ttk.Label(self, text="Chest X-ray:").grid(row=3, column=0, sticky="w", pady=2)
        self.xray_label = ttk.Label(self, text="(not selected)", foreground="gray", anchor="w")
        self.xray_label.grid(row=3, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(self, text="Browse...", width=10, command=self._select_xray).grid(row=3, column=2, pady=2)
        
        # Status indicator
        self.status_frame = ttk.Frame(self)
        self.status_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        
        self.status_label = ttk.Label(
            self.status_frame, 
            text="⚠ Select all 3 files",
            foreground="orange"
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Clear button
        ttk.Button(
            self.status_frame, 
            text="Clear All", 
            command=self._clear_all
        ).pack(side=tk.RIGHT)
        
        # Notice label - hidden until there is something to report
        # (e.g. a name that had unsupported characters removed for eMedical)
        self.notice_label = ttk.Label(
            self,
            text="",
            foreground="#B36B00",
            anchor="w",
            justify=tk.LEFT,
            wraplength=320
        )
    
    def set_notice(self, text: str):
        """
        Show or hide the bucket's notice line.
        
        Args:
            text: Message to display, or an empty string to hide the notice
        """
        if text:
            self.notice_label.config(text=text)
            self.notice_label.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        else:
            self.notice_label.config(text="")
            self.notice_label.grid_remove()
    
    def _select_file(self, title: str) -> Optional[Path]:
        """Open file dialog and return selected path."""
        filepath = filedialog.askopenfilename(
            title=title,
            filetypes=[
                ("PDF files", "*.pdf"),
                ("All files", "*.*")
            ]
        )
        if filepath:
            return Path(filepath)
        return None
    
    def _update_label(self, label: ttk.Label, path: Optional[Path]):
        """Update a file label with the selected filename."""
        if path and path.exists():
            # Show just filename, truncate if too long
            name = path.name
            if len(name) > 80:
                name = name[:77] + "..."
            label.config(text=f"✓ {name}", foreground="green")
        else:
            label.config(text="(not selected)", foreground="gray")
    
    def _update_status(self):
        """Update the overall status indicator."""
        if self.is_complete():
            self.status_label.config(text="✓ Ready", foreground="green")
        else:
            missing = self.get_data().get_missing_files()
            self.status_label.config(
                text=f"⚠ Missing: {', '.join(missing)}", 
                foreground="orange"
            )
        
        if self.on_change:
            self.on_change()
    
    def _select_i693(self):
        """Select I-693 file."""
        path = self._select_file("Select I-693 Form PDF")
        if path:
            self.i693_path = path
            self._update_label(self.i693_label, path)
            self.set_notice("")  # Stale notice no longer applies to the new file
            self._update_status()
    
    def _select_lab(self):
        """Select lab results file."""
        path = self._select_file("Select Lab Results PDF")
        if path:
            self.lab_results_path = path
            self._update_label(self.lab_label, path)
            self._update_status()
    
    def _select_xray(self):
        """Select chest x-ray file."""
        path = self._select_file("Select Chest X-ray PDF")
        if path:
            self.chest_xray_path = path
            self._update_label(self.xray_label, path)
            self._update_status()
    
    def _clear_all(self):
        """Clear all selected files."""
        self.i693_path = None
        self.lab_results_path = None
        self.chest_xray_path = None
        
        self._update_label(self.i693_label, None)
        self._update_label(self.lab_label, None)
        self._update_label(self.xray_label, None)
        
        self.label_entry.delete(0, tk.END)
        self.label_entry.insert(0, f"Patient {self.bucket_number}")
        
        self.set_notice("")
        self._update_status()
    
    def is_complete(self) -> bool:
        """Check if all files are selected."""
        return all([
            self.i693_path and self.i693_path.exists(),
            self.lab_results_path and self.lab_results_path.exists(),
            self.chest_xray_path and self.chest_xray_path.exists(),
        ])
    
    def has_any_files(self) -> bool:
        """Check if at least one file is selected."""
        return any([
            self.i693_path and self.i693_path.exists(),
            self.lab_results_path and self.lab_results_path.exists(),
            self.chest_xray_path and self.chest_xray_path.exists(),
        ])
    
    def is_empty(self) -> bool:
        """Check if no files are selected."""
        return not any([self.i693_path, self.lab_results_path, self.chest_xray_path])
    
    def get_data(self) -> PatientBucketData:
        """Get the bucket data."""
        return PatientBucketData(
            patient_label=self.label_entry.get().strip() or f"Patient {self.bucket_number}",
            i693_path=self.i693_path,
            lab_results_path=self.lab_results_path,
            chest_xray_path=self.chest_xray_path,
        )
