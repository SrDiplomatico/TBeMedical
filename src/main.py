"""
PDF Form Data Extractor - Main Entry Point

Extracts I-693 form data from PDFs and automates entry into eMedical portal.
Supports up to 10 concurrent patients per batch.

Usage:
    python -m src.main  (from project root)
    OR
    python src/main.py  (with path setup)
"""

import sys
from pathlib import Path

# Add src to path for imports when running as script
src_path = Path(__file__).parent
project_root = src_path.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main():
    """Application entry point."""
    # Import here after path setup
    from src.ui.main_window import MainWindow
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
