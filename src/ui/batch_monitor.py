"""Batch processing monitor panel."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional
from dataclasses import dataclass


@dataclass
class PatientStatus:
    """Status information for a patient in the batch."""
    patient_name: str
    status: str  # "pending", "processing", "ready_for_review", "submitted", "error"
    current_page: int = 0
    total_pages: int = 4
    error_message: str = ""


class BatchMonitor(ttk.Frame):
    """
    Panel showing real-time status of batch processing.
    Displays status for up to 10 concurrent patients.
    """
    
    STATUS_COLORS = {
        "pending": "#888888",
        "processing": "#2196F3",
        "ready_for_review": "#FF9800",
        "submitted": "#4CAF50",
        "error": "#F44336",
    }
    
    STATUS_TEXT = {
        "pending": "Pending",
        "processing": "Processing...",
        "ready_for_review": "⚠ Review Required",
        "submitted": "✓ Submitted",
        "error": "✗ Error",
    }
    
    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        
        self.patient_frames: dict[str, dict] = {}
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create monitor widgets."""
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            header_frame,
            text="Batch Processing Status",
            font=("Segoe UI", 11, "bold")
        ).pack(side=tk.LEFT)
        
        self.progress_label = ttk.Label(
            header_frame,
            text="0 / 0 complete",
            font=("Segoe UI", 10)
        )
        self.progress_label.pack(side=tk.RIGHT)
        
        # Scrollable patient list
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.patients_frame = ttk.Frame(canvas)
        
        self.patients_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.patients_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def set_patients(self, patient_names: list[str]):
        """
        Initialize the monitor with patient names.
        
        Args:
            patient_names: List of patient name prefixes
        """
        # Clear existing
        for widget in self.patients_frame.winfo_children():
            widget.destroy()
        self.patient_frames.clear()
        
        # Create row for each patient
        for i, name in enumerate(patient_names[:10]):  # Max 10
            frame = ttk.Frame(self.patients_frame)
            frame.pack(fill=tk.X, pady=2)
            
            # Patient name
            name_label = ttk.Label(
                frame, 
                text=f"{i+1}. {name}",
                width=25,
                anchor=tk.W
            )
            name_label.pack(side=tk.LEFT, padx=(0, 10))
            
            # Progress bar
            progress = ttk.Progressbar(
                frame,
                length=100,
                mode="determinate",
                maximum=4
            )
            progress.pack(side=tk.LEFT, padx=(0, 10))
            
            # Status label
            status_label = ttk.Label(
                frame,
                text="Pending",
                width=20,
                anchor=tk.W
            )
            status_label.pack(side=tk.LEFT)
            
            self.patient_frames[name] = {
                "frame": frame,
                "name_label": name_label,
                "progress": progress,
                "status_label": status_label,
            }
        
        self._update_summary()
    
    def update_patient_status(self, patient_name: str, status: PatientStatus):
        """
        Update the status display for a patient.
        
        Args:
            patient_name: Patient name prefix
            status: New status information
        """
        if patient_name not in self.patient_frames:
            return
        
        widgets = self.patient_frames[patient_name]
        
        # Update progress bar
        widgets["progress"]["value"] = status.current_page
        
        # Update status text and color
        status_text = self.STATUS_TEXT.get(status.status, status.status)
        if status.status == "processing":
            status_text = f"Page {status.current_page}/{status.total_pages}"
        elif status.status == "error" and status.error_message:
            status_text = f"Error: {status.error_message[:20]}..."
        
        widgets["status_label"]["text"] = status_text
        
        self._update_summary()
    
    def _update_summary(self):
        """Update the summary progress label."""
        total = len(self.patient_frames)
        completed = sum(
            1 for w in self.patient_frames.values()
            if "submitted" in w["status_label"]["text"].lower() or 
               "review" in w["status_label"]["text"].lower()
        )
        self.progress_label["text"] = f"{completed} / {total} complete"
    
    def reset(self):
        """Clear all patient status."""
        for widget in self.patients_frame.winfo_children():
            widget.destroy()
        self.patient_frames.clear()
        self.progress_label["text"] = "0 / 0 complete"
