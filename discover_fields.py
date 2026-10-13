"""
Utility script to discover form field names in a PDF.
Run this with a real I-693 PDF to find actual field names.

Usage:
    python discover_fields.py "path/to/i693.pdf"
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import fitz  # PyMuPDF


def discover_fields(pdf_path: str):
    """Print all form fields in a PDF."""
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"ERROR: File not found: {pdf_path}")
        return
    
    print(f"\n{'='*80}")
    print(f"FORM FIELDS IN: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    doc = fitz.open(str(pdf_path))
    
    all_fields = []
    
    for page_num, page in enumerate(doc):
        page_fields = []
        for widget in page.widgets():
            if widget.field_name:
                field_info = {
                    "name": widget.field_name,
                    "value": widget.field_value or "(empty)",
                    "type": widget.field_type_string,
                    "page": page_num + 1
                }
                page_fields.append(field_info)
                all_fields.append(field_info)
        
        if page_fields:
            print(f"--- Page {page_num + 1} ({len(page_fields)} fields) ---\n")
            for f in page_fields:
                value_display = f["value"][:60] + "..." if len(str(f["value"])) > 60 else f["value"]
                print(f"  [{f['type']:12}] {f['name']}")
                print(f"               Value: {value_display}\n")
    
    doc.close()
    
    print(f"{'='*80}")
    print(f"TOTAL: {len(all_fields)} form fields found")
    print(f"{'='*80}\n")
    
    # Also save to a text file for reference
    output_file = pdf_path.parent / f"{pdf_path.stem}_fields.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Form fields in: {pdf_path.name}\n\n")
        for field in all_fields:
            f.write(f"Page {field['page']}: [{field['type']}] {field['name']}\n")
            f.write(f"    Value: {field['value']}\n\n")
    
    print(f"Field list saved to: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # If no argument, prompt for file
        print("Drag and drop a PDF file here, or enter the path:")
        pdf_path = input("> ").strip().strip('"')
    else:
        pdf_path = sys.argv[1]
    
    if pdf_path:
        discover_fields(pdf_path)
    else:
        print("No file provided.")
