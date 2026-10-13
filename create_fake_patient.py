"""
Create a fake test patient I-693 PDF with all fields filled.
"""
import fitz  # PyMuPDF
from pathlib import Path


def fill_pdf_with_test_data(input_pdf: str, output_pdf: str):
    """Fill PDF form with fake test patient data."""
    
    doc = fitz.open(input_pdf)
    
    # Fake test data for Patient 1
    test_data = {
        # Part 1 - Applicant Information (repeated on multiple pages)
        "Pt1Line1a_FamilyName": "TESTPATIENT",
        "Pt1Line1b_GivenName": "JOHNATHAN",
        "Pt1Line1c_MiddleName": "MICHAEL",
        "Pt1Line3e_AlienNumber": "123456789",
        "Pt1Line3_DateOfBirth": "01/15/1985",
        "Pt1Line3_CountryofBirth": "Mexico",
        "Pt1Line3_CityTownVillageofBirth": "Mexico City",
        "Pt1Line3f_USCISOnlineAcctNumber": "USC1234567890",
        
        # Address
        "Pt1Line2_StreetNumberName": "123 Main Street",
        "Pt1Line2_AptSteFlrNumber": "Apt 4B",
        "P1Line2_CityOrTown": "Los Angeles",
        "P1Line2_State": "CA",
        "P1Line2_ZipCode": "90001",
        "P1Line2_Country": "United States",
        "P1Line2_Province": "",
        "P1Line2_PostalCode": "",
        
        # Contact
        "Pt2Line3_DaytimePhone": "555-123-4567",
        "Pt2Line4_Mobilephone": "555-987-6543",
        "Pt2Line5_EmailAddress": "testpatient1@email.com",
        "Pt2Line6_DateofSignature": "11/01/2025",
        
        # Part 5 - ID
        "Pt5Line1_ApplicantFormOfID": "Passport",
        "Pt5Line2_IDNumber": "TEST123456789",
        
        # Part 6 - Exam Results
        "Pt6Line2_DateoExam": "11/01/2025",
        "Pt6Line3_DateofExam1": "11/01/2025",
        "Pt6Line3_DateofExam2": "11/05/2025",
        "Pt6Line3_DateofExam3": "11/10/2025",
        
        # Part 7 - Civil Surgeon
        "Pt7Line1_FamilyName": "SMITH",
        "Pt7Line1_GivenName": "DOCTOR",
        "Pt7Line1_MiddleName": "A",
        "Pt7Line1_CivilSurgeonID": "CS12345",
        "Pt7Line2_MedPracticeName": "Test Medical Clinic",
        "Pt7Line3_StreetNumberName": "456 Medical Drive",
        "Pt7Line3_AptSteFlrNumber": "Suite 100",
        "Pt7Line3_CityOrTown": "Los Angeles",
        "Pt7Line3_State": "CA",
        "Pt7Line3_ZipCode": "90002",
        "Pt7Line4_StreetNumberName": "456 Medical Drive",
        "Pt7Line4_CityOrTown": "Los Angeles",
        "Pt7Line4_State": "CA",
        "Pt7Line4_ZipCode": "90002",
        "Pt7Line5_DaytimePhone": "555-222-3333",
        "Pt7Line6_MobilePhone": "555-444-5555",
        "Pt7Line7_EmailAddress": "drsmith@testclinic.com",
        "Pt7Line8_DateofSignature": "11/15/2025",
        
        # Part 8 - TB Testing
        "Pt8Line1A1_TSDate": "11/01/2025",
        "Pt8Line1A1_QFDate": "11/02/2025",
        "Pt8Line1A3_XrayTakenDate": "11/03/2025",
        "Pt8Line1A3_XrayReadDate": "11/04/2025",
        "Pt8Line1A7_Remarks": "No abnormalities detected",
        
        # Syphilis Testing
        "Pt8Line1B1a_name": "RPR Test",
        "Pt8Line1B1b_DateNontrepoemaltest": "11/01/2025",
        "Pt7Line1B1c_TiterOne": "Non-reactive",
        "Pt8Line1B1c_DateNontreponemalTest": "11/01/2025",
        "Pt8Line1B3_Remarks": "Negative",
        
        # Gonorrhea
        "Pt8Line1C1a_name": "NAAT Test",
        "Pt7Line1C1b_DateScreeningNucleicAcid": "11/01/2025",
        
        # Vaccination dates
        "Pt10Line1_DTDateReceived1": "01/15/1986",
        "Pt10Line1_DTDateReceived2": "03/15/1986",
        "Pt10Line1_DTDateReceived3": "05/15/1986",
        "Pt10Line2_TdDateReceived1": "01/15/2015",
        "Pt10Line6_HBDateReceived1": "01/15/1986",
        "Pt10Line6_HBDateReceived2": "02/15/1986",
        "Pt10Line6_HBDateReceived3": "07/15/1986",
        "Pt10Line7a_DateReceived_1": "01/15/1986",
        "Pt10Line7b_DateReceived_2": "05/15/1986",
        "Pt10Line8a_DateReceived_1": "01/15/1986",
        "Pt10Line8b_DateReceived_2": "05/15/1986",
        "Pt10Line9a_DateReceived_1": "10/15/2024",
        
        # Complete series
        "Pt10Line1_DTCompleteSeries": "Yes",
        "Pt10Line2_TdCompleteSeries": "Yes",
        "Pt10Line1_HBCompleteSeries": "Yes",
    }
    
    # Checkbox data (field name pattern -> value to set)
    checkbox_data = {
        # Gender - Male
        "Pt1Line3_Gender[0]": True,  # Male
        "Pt1Line3_Gender[1]": False,  # Female
        
        # Unit type - Apt.  Field-name index order is REVERSED vs. the visual
        # left-to-right layout: [2]=Apt, [1]=Ste, [0]=Flr.
        "Pt1Line2_Unit[0]": False,  # Flr
        "Pt1Line2_Unit[1]": False,  # Ste
        "Pt1Line2_Unit[2]": True,  # Apt
        
        # Overall Finding - Class A (No disease)
        "Pt6Line1_OverallFinding[0]": True,  # Class A
        "Pt6Line1_OverallFinding[1]": False,  # Class B
        "Pt6Line1_OverallFinding[2]": False,  # No Class
        
        # TB Test - IGRA (Quantiferon)
        "Pt8Line1A_GammarRelease[0]": False,  # TST
        "Pt8Line1A_GammarRelease[1]": True,   # IGRA
        "Pt8Line1A_GammarRelease[2]": False,  # Both
        
        # TB Result - Positive (for IGRA)
        "Pt8Line1A1_Result[0]": True,   # Positive - CHECKED
        "Pt8Line1A1_Result[1]": False,  # Negative
        "Pt8Line1A1_Result[2]": False,  # Indeterminate
        
        # Initial TB Screening - No chest X-ray needed
        "Pt8Line1A2_InitialScreening[0]": True,  # No CXR needed
        "Pt8Line1A2_InitialScreening[1]": False,
        "Pt8Line1A2_InitialScreening[2]": False,
        "Pt8Line1A2_InitialScreening[3]": False,
        
        # Chest X-ray - Normal
        "Pt8Line1A3_Results[0]": True,   # Normal
        "Pt8Line1A3_Results[1]": False,  # Abnormal
        
        # TB Classification - No TB
        "Pt8Line1A6_TBClassification[0]": True,   # No TB
        "Pt8Line1A6_TBClassification[1]": False,
        "Pt8Line1A6_TBClassification[2]": False,
        "Pt8Line1A6_TBClassification[3]": False,
        "Pt8Line1A6_TBClassification[4]": False,
        "Pt8Line1A6_TBClassification[5]": False,
        "Pt8Line1A6_TBClassification[6]": False,
        
        # Syphilis - Non-reactive
        "Pt8Line1B1c_SyphilisScreen[0]": False,  # Reactive
        "Pt8Line1B1c_SyphilisScreen[1]": True,   # Non-reactive
        
        # Syphilis findings - No Class
        "Pt8Line1B2_Findings[0]": True,   # No disease
        "Pt8Line1B2_Findings[1]": False,  # Class A
        "Pt8Line1B2_Findings[2]": False,  # Class B
        
        # Gonorrhea - Negative
        "Pt8Line1C1c[0]": False,  # Positive
        "Pt8Line1C1c[1]": True,   # Negative
        
        # Gonorrhea findings
        "Pt8Line1c2_Findings[0]": True,   # No disease
        "Pt8Line1c2_Findings[1]": False,
        "Pt8Line1c2_Findings[2]": False,
        
        # Hansen's Disease
        "Pt8Line1D1_Findings[0]": True,   # No disease
        "Pt8Line1D1_Findings[1]": False,
        "Pt8Line1D1_Findings[2]": False,
        
        # Mental/Physical Disorders - None
        "Pt8Line2A_Disorders[0]": True,   # No disorder
        "Pt8Line2A_Disorders[1]": False,
        "Pt8Line2A_Disorders[2]": False,
        "Pt8Line2A_Disorders[3]": False,
        "Pt8Line2A_Disorders[4]": False,
        
        # Drug abuse - No
        "Pt8Line3A_Findings[0]": True,   # No
        "Pt8Line3A_Findings[1]": False,
        "Pt8Line3A_Findings[2]": False,
        "Pt8Line3A_Findings[3]": False,
        
        # Vaccination results - Complete
        "P10_Results[0]": True,   # Complete
        "P10_Results[1]": False,  # Incomplete
        "P10_Results[2]": False,  # Blanket waiver
    }
    
    # Fill all pages
    for page in doc:
        for widget in page.widgets():
            if not widget.field_name:
                continue
            
            field_name = widget.field_name
            
            # Handle text fields
            if widget.field_type_string == "Text":
                for key, value in test_data.items():
                    if key in field_name:
                        widget.field_value = value
                        widget.update()
                        break
            
            # Handle checkboxes
            elif widget.field_type_string == "CheckBox":
                for pattern, should_check in checkbox_data.items():
                    if pattern in field_name:
                        if should_check:
                            widget.field_value = True
                        else:
                            widget.field_value = False
                        widget.update()
                        break
            
            # Handle combo boxes (dropdowns)
            elif widget.field_type_string == "ComboBox":
                if "State" in field_name:
                    widget.field_value = "CA"
                    widget.update()
    
    # Save the filled PDF
    doc.save(output_pdf)
    doc.close()
    print(f"Created fake test patient PDF: {output_pdf}")


if __name__ == "__main__":
    input_pdf = "Truly unlocked_i-693.pdf"
    output_pdf = "TestPatient1_I693.pdf"
    
    fill_pdf_with_test_data(input_pdf, output_pdf)
    print("\nDone! You can now use TestPatient1_I693.pdf for testing.")
