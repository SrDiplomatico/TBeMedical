"""
PDF Form Data Extractor - Main Entry Point

Extracts I-693 form data from PDFs and automates entry into eMedical portal.
Supports up to 10 concurrent patients per batch.

Usage:
    python src/main.py              Run the application
    python src/main.py --self-test  Import every module and exit (used by the build script)

When running from a PyInstaller build, stdout/stderr are redirected to a log file in
%LOCALAPPDATA%\\PDF Form Data Extractor\\logs so DEBUG output is still available.
"""

import sys
from pathlib import Path

# Add src and project root to path for imports when running as a script
src_path = Path(__file__).parent
project_root = src_path.parent
for p in (str(src_path), str(project_root)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _setup_logging() -> None:
    """In a windowed PyInstaller build there is no console; send output to a log file."""
    from src.config.paths import is_frozen, logs_dir

    if not is_frozen():
        return
    try:
        import datetime

        log_path = logs_dir() / f"app_{datetime.date.today():%Y-%m-%d}.log"
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
        print(f"\n===== Application started {datetime.datetime.now():%Y-%m-%d %H:%M:%S} =====")
    except Exception:
        # Never let logging setup prevent the app from starting
        pass


def self_test() -> int:
    """Import every runtime module and verify bundled resources. Returns exit code."""
    failures: list[str] = []

    checks = [
        ("fitz (PyMuPDF)", "fitz"),
        ("playwright", "playwright.sync_api"),
        ("config.settings", "src.config.settings"),
        ("config.paths", "src.config.paths"),
        ("config.credential_store", "src.config.credential_store"),
        ("models", "src.models.i693_form"),
        ("parser", "src.parser.pdf_reader"),
        ("automation.browser", "src.automation.browser"),
        ("automation.emedical", "src.automation.emedical"),
        ("ui.main_window (tkinter)", "src.ui.main_window"),
    ]
    import importlib

    for label, module in checks:
        try:
            importlib.import_module(module)
            print(f"  OK    {label}")
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL  {label}: {e}")
            failures.append(label)

    from src.config.paths import resource_path, find_chrome, is_frozen, project_root as _root

    template = resource_path("Truly unlocked_i-693.pdf")
    if template.is_file():
        print(f"  OK    template PDF ({template})")
    else:
        print(f"  FAIL  template PDF missing at {template}")
        failures.append("template PDF")

    try:
        import playwright, os

        driver = Path(os.path.dirname(playwright.__file__)) / "driver"
        node = next((f for f in driver.iterdir() if f.name.startswith("node")), None) if driver.is_dir() else None
        if node:
            print(f"  OK    playwright driver ({node})")
        else:
            print(f"  FAIL  playwright driver missing at {driver}")
            failures.append("playwright driver")
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL  playwright driver: {e}")
        failures.append("playwright driver")

    chrome = find_chrome()
    print(f"  INFO  frozen={is_frozen()} root={_root()}")
    print(f"  INFO  Google Chrome: {chrome or 'not found (required at runtime)'}")

    if failures:
        print(f"SELF-TEST FAILED: {', '.join(failures)}")
        return 1
    print("SELF-TEST PASSED")
    return 0


def main() -> None:
    """Application entry point."""
    if "--self-test" in sys.argv:
        sys.exit(self_test())

    _setup_logging()

    # Import here after path setup
    from src.ui.main_window import MainWindow

    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
