# PDF Form Data Extractor (eMedical Automation)

Windows desktop app that extracts I-693 form data from fillable PDFs and automates data
entry into the Australian eMedical portal.

## Install on a workstation (no Python needed)

1. Install **Google Chrome** if it is not already installed.
2. Copy `PDFFormExtractor.zip` to the PC and unzip it anywhere (Desktop, `C:\Apps`, etc.).
3. Run `PDFFormExtractor\PDFFormExtractor.exe`. Pin it to the taskbar if you like.

Everything the app writes (logs, debug screenshots, saved eMedical credentials) lives in
`%LOCALAPPDATA%\PDF Form Data Extractor\`. Credentials are encrypted with Windows DPAPI
and only readable by the Windows user who saved them.

The first launch may show a Windows SmartScreen warning because the executable is not
code-signed. Click **More info → Run anyway**.

### Troubleshooting

| Symptom | Fix |
|---|---|
| "Google Chrome was not found" | Install Chrome from google.com/chrome. Non-standard install: set `CHROME_PATH` to the full path of `chrome.exe`. |
| App opens then nothing happens | Check `%LOCALAPPDATA%\PDF Form Data Extractor\logs\app_YYYY-MM-DD.log` |
| Chrome launches but automation can't connect | Close every Chrome window, then try again (an existing Chrome absorbs the debug flag). |

## Get the package from GitHub (no local setup)

Every push to `main` builds the Windows package automatically.

1. Open the repository on github.com and click the **Actions** tab.
2. Click the most recent **Build Windows package** run (green check mark).
3. Scroll to **Artifacts** at the bottom and click **PDFFormExtractor-windows** to download the zip.

To start a build by hand: Actions tab → **Build Windows package** (left sidebar) →
**Run workflow** → **Run workflow**. Wait a few minutes, then download the artifact as above.

To publish a permanent download on the **Releases** page, create a tag such as `v1.0.0`
(Releases → Draft a new release → Choose a tag → type `v1.0.0` → Publish). The workflow
attaches `PDFFormExtractor.zip` to that release.

## Build the package (developer machine)

Requires Python 3.11+ from python.org on PATH. Then:

```bat
build.bat
```

This creates a build virtual environment, runs PyInstaller using `PDFFormExtractor.spec`,
self-tests the result, and produces `dist\PDFFormExtractor.zip`. Build on Windows; a
PyInstaller build only targets the OS it runs on.

## Run from source (developer machine)

```bat
run_app.bat
```

Creates `.venv`, installs `requirements.txt`, and starts `src\main.py`. For Playwright's
own Chromium instead of installed Chrome during development, run
`.venv\Scripts\playwright install chromium` once; the app falls back to it automatically
when Chrome isn't available (source runs only, never in the packaged build).

Quick health check from either mode:

```bat
python src\main.py --self-test
```
