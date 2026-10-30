"""Application settings and configuration."""

# Browser automation timing (milliseconds)
FIELD_DELAY_MS = 100  # Delay after filling each field
PAGE_LOAD_TIMEOUT_MS = 30000  # Max wait for page load
LOGIN_TIMEOUT_MS = 60000  # Max wait for login to complete

# Batch processing
MAX_CONCURRENT_PATIENTS = 6  # Number of patient buckets/tabs
BUCKET_COLUMNS = 3  # Patient buckets per row in the main window

# eMedical URLs
EMEDICAL_BASE_URL = "https://www.emedical.immi.gov.au/eMedUI/eMedical"

# Debug settings - set to page number to skip previous pages
# Set to 1 for normal operation (login + all pages)
# Set to 3+ to skip login and previous pages (you must already be logged in and on that page)
DEBUG_START_PAGE = 1  # Start from login for full run

# Checkpoint pause pages - show confirmation dialog before clicking next/create on these pages
# This allows user to verify data before proceeding
CHECKPOINT_PAGES = [2, 5]  # Pause before submitting Pages 2 and 5
