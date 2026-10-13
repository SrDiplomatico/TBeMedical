"""Dialog for collecting missing patient data during automation."""

import tkinter as tk
from tkinter import ttk
from typing import Optional


# US states for the state dropdown
US_STATES = [
    ("", "-- Select State --"),
    ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
    ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"),
    ("DC", "District of Columbia"), ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"),
    ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"),
    ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"),
    ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"),
    ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"),
    ("NV", "Nevada"), ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"),
    ("NY", "New York"), ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"),
    ("OK", "Oklahoma"), ("OR", "Oregon"), ("PA", "Pennsylvania"), ("RI", "Rhode Island"),
    ("SC", "South Carolina"), ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"),
    ("UT", "Utah"), ("VT", "Vermont"), ("VA", "Virginia"), ("WA", "Washington"),
    ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming"),
    ("AS", "American Samoa"), ("GU", "Guam"), ("MP", "Northern Mariana Islands"),
    ("PR", "Puerto Rico"), ("VI", "U.S. Virgin Islands"),
]


class MissingDataDialog:
    """
    Shows a popup listing missing fields and lets the user supply values.

    Designed to be called from the automation thread — creates its own
    temporary Tk root, blocks until the user responds, then returns the
    filled-in values.
    """

    def __init__(self, patient_name: str, missing_fields: list[dict]):
        """
        Args:
            patient_name: Name shown in the dialog title.
            missing_fields: List of dicts, each with:
                - "label": human-readable field name (e.g. "State")
                - "key":   data key used to apply the value back
                - "type":  "text" or "state_dropdown" (determines widget)
        """
        self.patient_name = patient_name
        self.missing_fields = missing_fields
        self.result: Optional[dict[str, str]] = None  # key -> user-entered value

    def show(self) -> Optional[dict[str, str]]:
        """
        Display the dialog and block until the user clicks Continue or Cancel.

        Returns:
            dict mapping field keys to user-entered values, or None if cancelled.
        """
        root = tk.Tk()
        root.withdraw()

        dialog = tk.Toplevel(root)
        dialog.title(f"Missing Data — {self.patient_name}")
        dialog.attributes("-topmost", True)
        dialog.resizable(False, False)
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._on_cancel(root, dialog))

        main = ttk.Frame(dialog, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main,
            text=f"Patient: {self.patient_name}",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Label(
            main,
            text="The following required fields are missing from the PDF.\n"
                 "Please enter the correct values to continue.",
            font=("Segoe UI", 9),
            foreground="gray",
        ).pack(anchor=tk.W, pady=(0, 15))

        # Build a row for each missing field
        widgets: dict[str, tk.Widget] = {}
        form = ttk.Frame(main)
        form.pack(fill=tk.X)

        for i, field in enumerate(self.missing_fields):
            ttk.Label(form, text=f"{field['label']}:").grid(
                row=i, column=0, sticky=tk.W, pady=5, padx=(0, 10)
            )

            if field.get("type") == "state_dropdown":
                combo = ttk.Combobox(
                    form,
                    values=[f"{abbr} - {name}" if abbr else name for abbr, name in US_STATES],
                    state="readonly",
                    width=30,
                )
                combo.current(0)
                combo.grid(row=i, column=1, pady=5)
                widgets[field["key"]] = combo
            else:
                entry = ttk.Entry(form, width=32)
                entry.grid(row=i, column=1, pady=5)
                widgets[field["key"]] = entry

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(
            btn_frame,
            text="Continue",
            command=lambda: self._on_continue(root, dialog, widgets),
        ).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(
            btn_frame,
            text="Skip (leave blank)",
            command=lambda: self._on_skip(root, dialog),
        ).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(
            btn_frame,
            text="Cancel Automation",
            command=lambda: self._on_cancel(root, dialog),
        ).pack(side=tk.RIGHT)

        # Center on screen
        dialog.update_idletasks()
        w = dialog.winfo_width()
        h = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (w // 2)
        y = (dialog.winfo_screenheight() // 2) - (h // 2)
        dialog.geometry(f"+{x}+{y}")

        dialog.grab_set()
        root.mainloop()
        return self.result

    def _on_continue(self, root: tk.Tk, dialog: tk.Toplevel, widgets: dict):
        values: dict[str, str] = {}
        for key, widget in widgets.items():
            raw = widget.get().strip()
            if isinstance(widget, ttk.Combobox) and raw:
                # Extract abbreviation from "TX - Texas" format
                if " - " in raw and not raw.startswith("--"):
                    raw = raw.split(" - ")[0].strip()
                elif raw.startswith("--"):
                    raw = ""
            values[key] = raw
        self.result = values
        dialog.destroy()
        root.destroy()

    def _on_skip(self, root: tk.Tk, dialog: tk.Toplevel):
        self.result = {}  # empty dict = skip, proceed with blanks
        dialog.destroy()
        root.destroy()

    def _on_cancel(self, root: tk.Tk, dialog: tk.Toplevel):
        self.result = None  # None = cancel automation
        dialog.destroy()
        root.destroy()
