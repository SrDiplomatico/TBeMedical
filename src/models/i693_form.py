"""Data models for I-693 form and patient files."""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass
class ApplicantInfo:
    """Part 1: Applicant information."""
    family_name: str = ""
    given_name: str = ""
    middle_name: str = ""
    a_number: str = ""  # 9 digits, stored without leading 'A'
    uscis_account: str = ""
    date_of_birth: str = ""  # Keep as string, format varies
    country_of_birth: str = ""
    city_of_birth: str = ""
    sex: str = ""  # "M" or "F"
    
    # Address (US)
    street_address: str = ""
    apt_number: str = ""
    unit_type: str = ""  # APT, STE, FLR
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = ""
    province: str = ""
    postal_code: str = ""
    
    # Contact
    phone: str = ""
    mobile_phone: str = ""
    email: str = ""
    signature_date: str = ""
    
    # ID
    id_type: str = ""  # Cleaned ID type (e.g. "PASSPORT"), without country suffix
    id_type_raw: str = ""  # Raw value from PDF (e.g. "PASSPORT - PERU")
    id_issuing_country: str = ""  # Country parsed from id_type if present (e.g. "PERU")
    id_number: str = ""


@dataclass
class InterpreterInfo:
    """Part 3: Interpreter information."""
    family_name: str = ""
    given_name: str = ""
    organization: str = ""
    phone: str = ""
    mobile_phone: str = ""
    email: str = ""
    language: str = ""


@dataclass
class MedicalExamination:
    """Parts 6, 8: Medical examination findings."""
    # Overall finding (Part 6)
    overall_finding: str = ""  # A, B, or blank
    exam_date: str = ""
    
    # TB Screening (Part 8 Section 1A)
    tb_test_type: str = ""  # TST or QF (QuantiFERON)
    tb_skin_test_date: str = ""
    tb_skin_test_result: str = ""  # P=Positive, N=Negative (derived)
    igra_test_date: str = ""
    igra_test_result: str = ""  # P=Positive, N=Negative, I=Indeterminate (derived)
    initial_tb_screening: str = ""  # A, B, C options
    
    # TB Result checkboxes (raw values from PDF)
    tb_result_positive: str = ""  # "P" if checked, "Off" if not
    tb_result_negative: str = ""  # "N" or similar if checked, "Off" if not
    tb_result_indeterminate: str = ""  # If checked, "Off" if not
    
    # Chest X-ray
    chest_xray_result: str = ""  # N=Normal, A=Abnormal (derived from checkboxes)
    chest_xray_normal: str = ""  # Raw checkbox value for Normal
    chest_xray_abnormal: str = ""  # Raw checkbox value for Abnormal
    chest_xray_date: str = ""
    chest_xray_read_date: str = ""
    
    # X-ray abnormality findings (checkboxes)
    xray_infiltrate: str = ""
    xray_reticular: str = ""
    xray_miliary: str = ""
    xray_nodules: str = ""
    xray_cavity: str = ""
    xray_hilar: str = ""
    xray_pleural: str = ""
    xray_linear: str = ""
    xray_thick_pleural: str = ""
    xray_volume_loss: str = ""
    xray_discrete_nodule: str = ""
    xray_other: str = ""
    
    # TB Classification (Part 8.1.A(6)) - checkboxes
    # NOTE: PDF field indices do NOT follow visual layout order!
    tb_class_no_tb: str = ""           # [0] on_state=NOClassA - No Class A or Class B TB
    tb_class_a: str = ""               # [1] on_state=CA - Class A Tuberculosis disease
    tb_class_b1_pulm: str = ""         # [2] on_state=B1Pul - B1 TB, Pulmonary
    tb_class_b0: str = ""              # [3] on_state=B0 - B0 TB, Pulmonary
    tb_class_b1_extrapulm: str = ""    # [4] on_state=B1Extrapul - B1 TB, Extrapulmonary
    tb_class_b2_ltbi: str = ""         # [5] on_state=B2#20TB#20Latent - B2 TB, LTBI Evaluation
    tb_class_b_other: str = ""         # [6] on_state=Class#20B#20Other - Class B, Other Chest Condition (Non-TB)
    tb_classification: str = ""        # Derived: which classification is checked
    tb_remarks: str = ""
    
    # Sputum Smears/Cultures (Part 8.1.A(4)) - checkboxes
    # These match the order on the actual I-693 form:
    sputum_not_indicated: str = ""       # [0] - No, not indicated
    sputum_signs_symptoms: str = ""       # [1] - Yes, indicated due to signs or symptoms of TB
    sputum_chest_xray: str = ""           # [2] - Yes, indicated due to chest X-ray suggestive of TB
    sputum_hiv_extrapulm: str = ""        # [3] - Yes, indicated due to known HIV infection or extrapulmonary TB
    sputum_end_treatment: str = ""        # [4] - Yes, indicated for end of treatment cultures
    sputum_indicated: str = ""            # Derived: "NI" (not indicated) or "IND" (indicated)
    
    # Sputum Smear Results (Part 8.1.A(5)(a)) - 3 rows
    smear_specimen_date_1: str = ""
    smear_result_date_1: str = ""
    smear_result_1: str = ""  # "POS" or "NEG"
    smear_specimen_date_2: str = ""
    smear_result_date_2: str = ""
    smear_result_2: str = ""
    smear_specimen_date_3: str = ""
    smear_result_date_3: str = ""
    smear_result_3: str = ""
    
    # Sputum Culture Results (Part 8.1.A(5)(b)) - 3 rows
    culture_specimen_date_1: str = ""
    culture_result_date_1: str = ""
    culture_result_1: str = ""  # "POS", "NEG", "NTM", or "CNTAMNTD"
    culture_specimen_date_2: str = ""
    culture_result_date_2: str = ""
    culture_result_2: str = ""
    culture_specimen_date_3: str = ""
    culture_result_date_3: str = ""
    culture_result_3: str = ""
    
    # Syphilis (Part 8 Section 1B)
    syphilis_test_name: str = ""
    syphilis_test_date: str = ""
    syphilis_titer: str = ""
    syphilis_screen_result: str = ""  # Reactive/Non-reactive
    syphilis_finding: str = ""  # No, Class A, Class B
    syphilis_remarks: str = ""
    syphilis_drug: str = ""
    syphilis_dosage: str = ""
    syphilis_start_date: str = ""
    syphilis_end_date: str = ""
    
    # Gonorrhea (Part 8 Section 1C)
    gonorrhea_test_name: str = ""
    gonorrhea_test_date: str = ""
    gonorrhea_result: str = ""  # Positive/Negative
    gonorrhea_finding: str = ""  # No, Class A, Class B
    gonorrhea_remarks: str = ""
    gonorrhea_drug: str = ""
    gonorrhea_dosage: str = ""
    gonorrhea_start_date: str = ""
    gonorrhea_end_date: str = ""
    
    # Treponemal test (confirmatory) - Page 8
    treponemal_test_name: str = ""
    treponemal_test_date: str = ""
    treponemal_titer: str = ""
    treponemal_result: str = ""  # Reactive/Non-reactive
    repeat_test_name: str = ""
    repeat_test_date: str = ""
    repeat_test_result: str = ""
    
    # Hansen's Disease - Leprosy (Part 8 Section 1D)
    hansens_disease: str = ""  # a=No, b=Class A, c=Class B
    hansens_remarks: str = ""
    hansens_checkbox_f: str = ""
    hansens_checkbox_g: str = ""
    
    # Mental/Physical Disorders (Part 8 Section 2)
    mental_physical_disorder: str = ""  # 1=No disorder
    disorder_remarks: str = ""
    
    # Drug Abuse (Part 8 Section 3)
    drug_abuse: str = ""  # 1=No
    drug_abuse_remarks: str = ""
    
    # Other conditions (Part 8 Section 4)
    other_conditions: str = ""
    
    # Vaccination Results (Page 13)
    vaccination_results: str = ""  # A, B, or C
    vaccination_remarks: str = ""
    uscis_remarks: str = ""


@dataclass
class VaccinationHistory:
    """Part 10: Vaccination records - comprehensive tracking."""
    
    # DT (Diphtheria/Tetanus - pediatric)
    dt_date_1: str = ""
    dt_date_2: str = ""
    dt_date_3: str = ""
    dt_date_4: str = ""
    dt_date_given: str = ""
    dt_complete: str = ""
    dt_not_required_age: str = ""
    dt_insufficient: str = ""
    dt_contraindicated: str = ""
    
    # Td/Tdap (adult)
    tdap_type: str = ""  # Td or Tdap
    tdap_date_1: str = ""
    tdap_date_2: str = ""
    tdap_date_3: str = ""
    tdap_date_4: str = ""
    tdap_date_given: str = ""
    tdap_complete: str = ""
    tdap_not_required_age: str = ""
    tdap_insufficient: str = ""
    tdap_contraindicated: str = ""
    
    # Polio (IPV/OPV)
    polio_type: str = ""  # IPV or OPV
    polio_date_1: str = ""
    polio_date_2: str = ""
    polio_date_3: str = ""
    polio_date_4: str = ""
    polio_date_given: str = ""
    polio_not_required_age: str = ""
    polio_insufficient: str = ""
    polio_contraindicated: str = ""
    
    # Hib (Haemophilus influenzae type B)
    hib_date_1: str = ""
    hib_date_2: str = ""
    hib_date_3: str = ""
    hib_date_4: str = ""
    hib_date_given: str = ""
    hib_not_required_age: str = ""
    hib_insufficient: str = ""
    hib_contraindicated: str = ""
    
    # Rotavirus
    rotavirus_date_1: str = ""
    rotavirus_date_2: str = ""
    rotavirus_date_3: str = ""
    rotavirus_date_4: str = ""
    rotavirus_date_given: str = ""
    rotavirus_not_required_age: str = ""
    rotavirus_insufficient: str = ""
    rotavirus_contraindicated: str = ""
    
    # Hepatitis B
    hep_b_date_1: str = ""
    hep_b_date_2: str = ""
    hep_b_date_3: str = ""
    hep_b_date_4: str = ""
    hep_b_date_given: str = ""
    hep_b_complete: str = ""
    hep_b_not_required_age: str = ""
    hep_b_insufficient: str = ""
    hep_b_contraindicated: str = ""
    
    # MMR (Measles, Mumps, Rubella)
    mmr_date_1: str = ""
    mmr_date_2: str = ""
    mmr_date_3: str = ""
    mmr_date_4: str = ""
    mmr_date_given: str = ""
    mmr_not_required_age: str = ""
    mmr_insufficient: str = ""
    mmr_contraindicated: str = ""
    
    # Varicella (Chickenpox)
    varicella_date_1: str = ""
    varicella_date_2: str = ""
    varicella_date_3: str = ""
    varicella_date_4: str = ""
    varicella_date_given: str = ""
    varicella_not_required_age: str = ""
    varicella_insufficient: str = ""
    varicella_contraindicated: str = ""
    
    # Influenza
    influenza_date_1: str = ""
    influenza_date_2: str = ""
    influenza_date_3: str = ""
    influenza_date_4: str = ""
    influenza_date_given: str = ""
    influenza_not_required_age: str = ""
    influenza_insufficient: str = ""
    influenza_contraindicated: str = ""
    
    # Pneumococcal (PCV)
    pneumo_date_1: str = ""
    pneumo_date_2: str = ""
    pneumo_date_3: str = ""
    pneumo_date_4: str = ""
    pneumo_date_given: str = ""
    pneumo_not_required_age: str = ""
    pneumo_insufficient: str = ""
    pneumo_contraindicated: str = ""
    
    # Hepatitis A
    hep_a_date_1: str = ""
    hep_a_date_2: str = ""
    hep_a_date_3: str = ""
    hep_a_date_4: str = ""
    hep_a_date_given: str = ""
    hep_a_not_required_age: str = ""
    hep_a_insufficient: str = ""
    hep_a_contraindicated: str = ""
    
    # Meningococcal
    meningo_date_1: str = ""
    meningo_date_2: str = ""
    meningo_date_3: str = ""
    meningo_date_4: str = ""
    meningo_date_given: str = ""
    meningo_not_required_age: str = ""
    meningo_insufficient: str = ""
    meningo_contraindicated: str = ""
    
    # COVID-19
    covid_date_1: str = ""
    covid_date_2: str = ""
    covid_date_3: str = ""
    covid_date_4: str = ""
    covid_date_given: str = ""
    covid_complete: str = ""
    covid_not_required_age: str = ""
    covid_insufficient: str = ""
    covid_contraindicated: str = ""


@dataclass
class CivilSurgeonInfo:
    """Part 7: Civil surgeon certification."""
    surgeon_family_name: str = ""
    surgeon_given_name: str = ""
    surgeon_middle_name: str = ""
    uscis_id: str = ""
    practice_name: str = ""
    
    # Practice address
    practice_street: str = ""
    practice_apt: str = ""
    practice_city: str = ""
    practice_state: str = ""
    practice_zip: str = ""
    
    # Mailing address
    mailing_street: str = ""
    mailing_city: str = ""
    mailing_state: str = ""
    mailing_zip: str = ""
    
    # Contact
    phone: str = ""
    mobile_phone: str = ""
    email: str = ""
    
    # Signature (Page 5)
    signature: str = ""
    signature_date: str = ""


@dataclass
class ReferralInfo:
    """Part 8 Section 5: Referral information."""
    doctor_name: str = ""
    street: str = ""
    apt: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    date: str = ""
    remarks: str = ""


@dataclass
class PanelPhysicianInfo:
    """Part 9: Panel physician information."""
    family_name: str = ""
    given_name: str = ""
    middle_name: str = ""
    organization: str = ""
    street: str = ""
    apt: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    signature: str = ""
    signature_date: str = ""
    mp_hd_name: str = ""
    phone: str = ""


@dataclass
class AdditionalInfo:
    """Part 11: Additional information."""
    line3_page: str = ""
    line3_part: str = ""
    line3_item: str = ""
    line3_info: str = ""
    line4_page: str = ""
    line4_part: str = ""
    line4_item: str = ""
    line4_info: str = ""
    line5_page: str = ""
    line5_part: str = ""
    line5_item: str = ""
    line5_info: str = ""
    line6_page: str = ""
    line6_part: str = ""
    line6_item: str = ""
    line6_info: str = ""


@dataclass
class I693Form:
    """Complete I-693 form data structure."""
    applicant: ApplicantInfo = field(default_factory=ApplicantInfo)
    interpreter: InterpreterInfo = field(default_factory=InterpreterInfo)
    examination: MedicalExamination = field(default_factory=MedicalExamination)
    vaccinations: VaccinationHistory = field(default_factory=VaccinationHistory)
    civil_surgeon: CivilSurgeonInfo = field(default_factory=CivilSurgeonInfo)
    referral: ReferralInfo = field(default_factory=ReferralInfo)
    panel_physician: PanelPhysicianInfo = field(default_factory=PanelPhysicianInfo)
    additional_info: AdditionalInfo = field(default_factory=AdditionalInfo)
    
    # Metadata
    source_file: str = ""
    extraction_date: Optional[date] = None
    extraction_errors: list[str] = field(default_factory=list)


@dataclass
class PatientFiles:
    """Collection of files for one patient."""
    patient_name: str  # Prefix used in filenames
    i693_path: Path
    lab_results_path: Path
    chest_xray_path: Path
    
    # Extracted data (populated after parsing)
    i693_data: Optional[I693Form] = None
    
    # Processing status
    is_valid: bool = False
    validation_errors: list[str] = field(default_factory=list)
    processing_status: str = "pending"  # pending, processing, ready_for_review, submitted, error
    
    def validate_files_exist(self) -> bool:
        """Check all required files exist."""
        self.validation_errors.clear()
        
        if not self.i693_path.exists():
            self.validation_errors.append(f"I-693 file not found: {self.i693_path}")
        if not self.lab_results_path.exists():
            self.validation_errors.append(f"Lab results file not found: {self.lab_results_path}")
        if not self.chest_xray_path.exists():
            self.validation_errors.append(f"Chest x-ray file not found: {self.chest_xray_path}")
        
        self.is_valid = len(self.validation_errors) == 0
        return self.is_valid
