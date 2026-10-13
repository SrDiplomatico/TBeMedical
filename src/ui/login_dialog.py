"""Login dialog for eMedical credentials."""

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Credentials:
    """eMedical login credentials."""
    username: str
    password: str


class LoginDialog(tk.Toplevel):
    """
    Modal dialog for entering eMedical credentials.
    Credentials are encrypted for the current Windows user when submitted.
    """
    
    def __init__(
        self,
        parent: tk.Tk,
        on_login: Callable[[Credentials], None],
        initial_credentials: Optional[Credentials] = None,
    ):
        super().__init__(parent)
        
        self.on_login = on_login
        self.credentials: Optional[Credentials] = None
        self.initial_credentials = initial_credentials
        
        self.title("eMedical Login")
        self.geometry("400x240")
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._center_window(parent)
        
        # Focus username field
        self.username_entry.focus_set()
    
    def _create_widgets(self):
        """Create dialog widgets."""
        # Main frame with padding
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(
            main_frame, 
            text="Enter eMedical Credentials",
            font=("Segoe UI", 12, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # Note about security
        note_label = ttk.Label(
            main_frame,
            text="Credentials are encrypted and saved for your Windows account.",
            font=("Segoe UI", 8),
            foreground="gray"
        )
        note_label.pack(pady=(0, 10))
        
        # Form frame
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X)
        
        # Username
        ttk.Label(form_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(form_frame, width=30)
        self.username_entry.grid(row=0, column=1, pady=5, padx=(10, 0))
        if self.initial_credentials:
            self.username_entry.insert(0, self.initial_credentials.username)
        
        # Password
        ttk.Label(form_frame, text="Password:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.password_entry = ttk.Entry(form_frame, width=30, show="•")
        self.password_entry.grid(row=1, column=1, pady=5, padx=(10, 0))
        if self.initial_credentials:
            self.password_entry.insert(0, self.initial_credentials.password)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(20, 0))
        
        tk.Button(button_frame, text="Login", command=self._on_login_click,
                  width=10, relief=tk.RAISED).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=self._on_cancel,
                  width=10, relief=tk.RAISED).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key
        self.bind("<Return>", lambda e: self._on_login_click())
        self.bind("<Escape>", lambda e: self._on_cancel())
    
    def _center_window(self, parent: tk.Tk):
        """Center dialog over parent window."""
        self.update_idletasks()
        
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        
        w = self.winfo_width()
        h = self.winfo_height()
        
        x = parent_x + (parent_w - w) // 2
        y = parent_y + (parent_h - h) // 2
        
        self.geometry(f"+{x}+{y}")
    
    def _on_login_click(self):
        """Handle login button click."""
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        
        if not username or not password:
            tk.messagebox.showwarning(
                "Missing Credentials",
                "Please enter both username and password.",
                parent=self
            )
            return
        
        self.credentials = Credentials(username=username, password=password)
        self.on_login(self.credentials)
        self.destroy()
    
    def _on_cancel(self):
        """Handle cancel button click."""
        self.credentials = None
        self.destroy()
