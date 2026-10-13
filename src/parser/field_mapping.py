"""
I-693 PDF field name to data model mapping.

Field names discovered from actual I-693 PDF form (unlocked_i-693 MA AVILA.pdf).
The I-693 has fields repeated across pages (with index suffixes like [0], [1], etc.)
We use the first occurrence (page 1) for most fields.

Pages breakdown:
- Page 1: Applicant info (Part 1)
- Page 2: Applicant signature, interpreter info (Parts 2-3)
- Page 3: Preparer info, applicant ID (Parts 4-5)
- Page 4: Civil Surgeon info, exam date (Parts 6-7)
- Page 5: Civil Surgeon signature
- Page 6: TB Screening (Part 8 Section 1A - TST/IGRA, X-ray)
- Page 7: TB Classification, Syphilis (Part 8 Sections 1A6, 1B)
- Page 8: Syphilis continued, Gonorrhea (Part 8 Sections 1B, 1C)
- Page 9: Mental/Physical Disorders (Part 8 Section 2)
- Page 10: Other medical conditions (Part 8 Sections 3-4)
- Page 11: Referrals (Part 9)
- Page 12: Vaccination Records (Part 10) - 131 fields!
- Page 13: Vaccination Results/Remarks
- Page 14: Additional Information (Part 11)
"""

# Map from PDF field name -> data model path
# Using actual field names discovered from test PDF

I693_FIELD_MAP = {
    # ========================================================================
    # Page 1: Part 1 - Applicant Information (24 fields)
    # ========================================================================
    "form1[0].#subform[0].Pt1Line1a_FamilyName[0]": "applicant.family_name",
    "form1[0].#subform[0].Pt1Line1b_GivenName[0]": "applicant.given_name",
    "form1[0].#subform[0].Pt1Line1c_MiddleName[0]": "applicant.middle_name",
    
    # Address (US)
    "form1[0].#subform[0].Pt1Line2_StreetNumberName[0]": "applicant.street_address",
    "form1[0].#subform[0].Pt1Line2_AptSteFlrNumber[0]": "applicant.apt_number",
    # Pt1Line2_Unit[0..2] (Apt./Ste./Flr.) is a checkbox group where every widget
    # reports the same field_value, so it cannot be read from this map.
    # It is derived by position in pdf_reader._detect_unit_type().
    "form1[0].#subform[0].P1Line2_CityOrTown[0]": "applicant.city",
    "form1[0].#subform[0].P1Line2_State[0]": "applicant.state",
    "form1[0].#subform[0].P1Line2_ZipCode[0]": "applicant.zip_code",
    "form1[0].#subform[0].P1Line2_Country[0]": "applicant.country",
    "form1[0].#subform[0].P1Line2_Province[0]": "applicant.province",
    "form1[0].#subform[0].P1Line2_PostalCode[0]": "applicant.postal_code",
    
    # Personal info
    "form1[0].#subform[0].Pt1Line3_Gender[0]": "applicant.sex",  # M or F
    "form1[0].#subform[0].Pt1Line3_DateOfBirth[0]": "applicant.date_of_birth",
    "form1[0].#subform[0].Pt1Line3_CountryofBirth[0]": "applicant.country_of_birth",
    "form1[0].#subform[0].Pt1Line3_CityTownVillageofBirth[0]": "applicant.city_of_birth",
    "form1[0].#subform[0].#area[0].Pt1Line3e_AlienNumber[0]": "applicant.a_number",
    "form1[0].#subform[0].Pt1Line3f_USCISOnlineAcctNumber[0]": "applicant.uscis_account",
    
    # ========================================================================
    # Page 2: Parts 2-3 - Applicant Signature & Interpreter (16 fields)
    # ========================================================================
    "form1[0].#subform[1].Pt2Line6_DateofSignature[0]": "applicant.signature_date",
    "form1[0].#subform[1].Pt2Line3_DaytimePhone[0]": "applicant.phone",
    "form1[0].#subform[1].Pt2Line4_Mobilephone[0]": "applicant.mobile_phone",
    "form1[0].#subform[1].Pt2Line5_EmailAddress[0]": "applicant.email",
    
    # Interpreter (Part 3)
    "form1[0].#subform[1].Pt3Line1_InterpreterFamilyName[0]": "interpreter.family_name",
    "form1[0].#subform[1].Pt3Line1_InterpreterGivenName[0]": "interpreter.given_name",
    "form1[0].#subform[1].Pt3Line2_NameofBusinessorOrgName[0]": "interpreter.organization",
    "form1[0].#subform[1].Pt3Line4_DaytimePhone[0]": "interpreter.phone",
    "form1[0].#subform[1].Pt3Line5_MobilePhone[0]": "interpreter.mobile_phone",
    "form1[0].#subform[1].Pt3Line6_EmailAddress[0]": "interpreter.email",
    
    # ========================================================================
    # Page 3: Parts 4-5 - Preparer & Applicant ID (18 fields)
    # ========================================================================
    "form1[0].#subform[2].Pt5Line1_ApplicantFormOfID[0]": "applicant.id_type",
    "form1[0].#subform[2].Pt5Line2_IDNumber[0]": "applicant.id_number",
    "form1[0].#subform[2].Pt3Line_NameOfLanguage[0]": "interpreter.language",
    
    # ========================================================================
    # Page 4: Parts 6-7 - Overall Finding & Civil Surgeon Info (36 fields)
    # ========================================================================
    # Overall finding
    "form1[0].#subform[3].Pt6Line1_OverallFinding[0]": "examination.overall_finding",  # A, B, or (blank)
    "form1[0].#subform[3].Pt6Line2_DateoExam[0]": "examination.exam_date",
    
    # Civil Surgeon info (Part 7)
    "form1[0].#subform[3].Pt7Line1_FamilyName[0]": "civil_surgeon.surgeon_family_name",
    "form1[0].#subform[3].Pt7Line1_GivenName[0]": "civil_surgeon.surgeon_given_name",
    "form1[0].#subform[3].Pt7Line1_MiddleName[0]": "civil_surgeon.surgeon_middle_name",
    "form1[0].#subform[3].Pt7Line1_CivilSurgeonID[0]": "civil_surgeon.uscis_id",
    "form1[0].#subform[3].Pt7Line2_MedPracticeName[0]": "civil_surgeon.practice_name",
    
    # Civil Surgeon Practice Address
    "form1[0].#subform[3].Pt7Line3_StreetNumberName[0]": "civil_surgeon.practice_street",
    "form1[0].#subform[3].Pt7Line3_AptSteFlrNumber[0]": "civil_surgeon.practice_apt",
    "form1[0].#subform[3].Pt7Line3_CityOrTown[0]": "civil_surgeon.practice_city",
    "form1[0].#subform[3].Pt7Line3_State[0]": "civil_surgeon.practice_state",
    "form1[0].#subform[3].Pt7Line3_ZipCode[0]": "civil_surgeon.practice_zip",
    
    # Civil Surgeon Mailing Address
    "form1[0].#subform[3].Pt7Line4_StreetNumberName[0]": "civil_surgeon.mailing_street",
    "form1[0].#subform[3].Pt7Line4_CityOrTown[0]": "civil_surgeon.mailing_city",
    "form1[0].#subform[3].Pt7Line4_State[0]": "civil_surgeon.mailing_state",
    "form1[0].#subform[3].Pt7Line4_ZipCode[0]": "civil_surgeon.mailing_zip",
    
    # Civil Surgeon Contact
    "form1[0].#subform[3].Pt7Line5_DaytimePhone[0]": "civil_surgeon.phone",
    "form1[0].#subform[3].Pt7Line6_MobilePhone[0]": "civil_surgeon.mobile_phone",
    "form1[0].#subform[3].Pt7Line7_EmailAddress[0]": "civil_surgeon.email",
    
    # ========================================================================
    # Page 6: Part 8 Section 1A - TB Screening (33 fields)
    # ========================================================================
    # TB Test Type (TST or IGRA)
    "form1[0].#subform[5].Pt8Line1A_GammarRelease[0]": "examination.tb_test_type",  # TST or QF (QuantiFERON)
    
    # TST (Tuberculin Skin Test)
    "form1[0].#subform[5].Pt8Line1A1_TSDate[0]": "examination.tb_skin_test_date",
    
    # TB Result checkboxes (shared for TST and IGRA)
    # When checked, value is "Yes"; when unchecked, value is "Off"
    # Based on I-693 form layout:
    "form1[0].#subform[5].Pt8Line1A1_Result[0]": "examination.tb_result_negative",  # Negative checkbox
    "form1[0].#subform[5].Pt8Line1A1_Result[1]": "examination.tb_result_positive",  # Positive checkbox
    "form1[0].#subform[5].Pt8Line1A1_Result[2]": "examination.tb_result_indeterminate",  # Indeterminate checkbox
    
    # IGRA (QuantiFERON)
    "form1[0].#subform[5].Pt8Line1A1_QFDate[0]": "examination.igra_test_date",
    
    # Initial TB Screening Result
    "form1[0].#subform[5].Pt8Line1A2_InitialScreening[0]": "examination.initial_tb_screening",  # A, B, C options
    
    # Chest X-ray Results (checkboxes - Results[0]=Normal, Results[1]=Abnormal)
    "form1[0].#subform[5].Pt8Line1A3_Results[0]": "examination.chest_xray_normal",  # Yes=Normal checked
    "form1[0].#subform[5].Pt8Line1A3_Results[1]": "examination.chest_xray_abnormal",  # Yes=Abnormal checked
    "form1[0].#subform[5].Pt8Line1A3_XrayTakenDate[0]": "examination.chest_xray_date",
    "form1[0].#subform[5].Pt8Line1A3_XrayReadDate[0]": "examination.chest_xray_read_date",
    
    # X-ray Abnormality Checkboxes
    "form1[0].#subform[5].Pt8Line1A3_Infiltrate[0]": "examination.xray_infiltrate",
    "form1[0].#subform[5].Pt8Line1A3_Reticular[0]": "examination.xray_reticular",
    "form1[0].#subform[5].Pt8Line1A3_Miliary[0]": "examination.xray_miliary",
    "form1[0].#subform[5].Pt8Line1A3_NodulesorMass[0]": "examination.xray_nodules",
    "form1[0].#subform[5].Pt8Line1A3_Cavitylesion[0]": "examination.xray_cavity",
    "form1[0].#subform[5].Pt8Line1A3_Hilar[0]": "examination.xray_hilar",
    "form1[0].#subform[5].Pt8Line1A3_Pleuraleffusion[0]": "examination.xray_pleural",
    "form1[0].#subform[5].Pt8Line1A3_DiscretelinearOpac[0]": "examination.xray_linear",
    "form1[0].#subform[5].Pt8Line1A3_Irregularthickpleural[0]": "examination.xray_thick_pleural",
    "form1[0].#subform[5].Pt8Line1A3_Volumeloss[0]": "examination.xray_volume_loss",
    "form1[0].#subform[5].Pt8Line1A3_DiscreteNodule[0]": "examination.xray_discrete_nodule",
    "form1[0].#subform[5].Pt8Line1A3_Other[0]": "examination.xray_other",
    
    # ========================================================================
    # Page 7: Part 8 Section 1A6 - TB Classification & Syphilis (54 fields)
    # ========================================================================
    # TB Classification checkboxes (Part 8.1.A(6))
    # NOTE: PDF field indices do NOT follow visual layout order!
    # Verified on_state values: [0]=NOClassA, [1]=CA, [2]=B1Pul, [3]=B0, [4]=B1Extrapul, [5]=B2, [6]=B_Other
    "form1[0].#subform[6].Pt8Line1A6_TBClassification[0]": "examination.tb_class_no_tb",        # on_state=NOClassA - No Class A or Class B TB
    "form1[0].#subform[6].Pt8Line1A6_TBClassification[1]": "examination.tb_class_a",            # on_state=CA - Class A Tuberculosis disease
    "form1[0].#subform[6].Pt8Line1A6_TBClassification[2]": "examination.tb_class_b1_pulm",      # on_state=B1Pul - B1 TB, Pulmonary (NOT B0!)
    "form1[0].#subform[6].Pt8Line1A6_TBClassification[3]": "examination.tb_class_b0",           # on_state=B0 - B0 TB, Pulmonary (NOT B1!)
    "form1[0].#subform[6].Pt8Line1A6_TBClassification[4]": "examination.tb_class_b1_extrapulm", # on_state=B1Extrapul - B1 TB, Extrapulmonary
    "form1[0].#subform[6].Pt8Line1A6_TBClassification[5]": "examination.tb_class_b2_ltbi",      # on_state=B2#20TB#20Latent - B2 TB, LTBI Evaluation
    "form1[0].#subform[6].Pt8Line1A6_TBClassification[6]": "examination.tb_class_b_other",      # on_state=Class#20B#20Other - Class B, Other Chest Condition (Non-TB)
    "form1[0].#subform[6].Pt8Line1A7_Remarks[0]": "examination.tb_remarks",
    
    # Sputum Smears/Cultures (Part 8.1.A(4)) - matches actual I-693 form order
    "form1[0].#subform[6].Pt8Line1A4_SputumSmearsCultures[0]": "examination.sputum_not_indicated",   # No, not indicated
    "form1[0].#subform[6].Pt8Line1A4_SputumSmearsCultures[1]": "examination.sputum_signs_symptoms", # Yes, indicated due to signs or symptoms of TB
    "form1[0].#subform[6].Pt8Line1A4_SputumSmearsCultures[2]": "examination.sputum_chest_xray",     # Yes, indicated due to chest X-ray suggestive of TB
    "form1[0].#subform[6].Pt8Line1A4_SputumSmearsCultures[3]": "examination.sputum_hiv_extrapulm",  # Yes, indicated due to known HIV infection or extrapulmonary TB
    "form1[0].#subform[6].Pt8Line1A4_SputumSmearsCultures[4]": "examination.sputum_end_treatment",  # Yes, indicated for end of treatment cultures
    
    # Syphilis Screening (Part 8 Section 1B)
    "form1[0].#subform[6].Pt8Line1B1a_name[0]": "examination.syphilis_test_name",
    "form1[0].#subform[6].Pt8Line1B1b_DateNontrepoemaltest[0]": "examination.syphilis_test_date",
    "form1[0].#subform[6].Pt7Line1B1c_TiterOne[0]": "examination.syphilis_titer",
    "form1[0].#subform[6].Pt8Line1B1c_SyphilisScreen[0]": "examination.syphilis_screen_result",  # Reactive/Non-reactive
    
    # ========================================================================
    # Page 8: Part 8 Sections 1B-1C - Syphilis continued & Gonorrhea (34 fields)
    # ========================================================================
    "form1[0].#subform[7].Pt8Line1B2_Findings[0]": "examination.syphilis_finding",  # No, Class A, Class B
    "form1[0].#subform[7].Pt8Line1B3_Remarks[0]": "examination.syphilis_remarks",
    "form1[0].#subform[7].Pt8Line1B3_Drug[0]": "examination.syphilis_drug",
    "form1[0].#subform[7].Pt8Line1B3_Dosage[0]": "examination.syphilis_dosage",
    "form1[0].#subform[7].Pt8Line1B3_startDate[0]": "examination.syphilis_start_date",
    "form1[0].#subform[7].Pt8Line1B3_endDate[0]": "examination.syphilis_end_date",
    
    # Gonorrhea (Part 8 Section 1C)
    "form1[0].#subform[7].Pt8Line1C1a_name[0]": "examination.gonorrhea_test_name",
    "form1[0].#subform[7].Pt7Line1C1b_DateScreeningNucleicAcid[0]": "examination.gonorrhea_test_date",
    "form1[0].#subform[7].Pt8Line1C1c[0]": "examination.gonorrhea_result",  # Positive/Negative
    "form1[0].#subform[7].Pt8Line1c2_Findings[0]": "examination.gonorrhea_finding",  # No, Class A, Class B
    "form1[0].#subform[7].Pt8Line1c3_Remarks[0]": "examination.gonorrhea_remarks",
    
    # ========================================================================
    # Page 9: Part 8 Section 2 - Mental/Physical Disorders (19 fields)
    # ========================================================================
    "form1[0].#subform[8].Pt8Line2A_Disorders[0]": "examination.mental_physical_disorder",  # 1=No disorder
    "form1[0].#subform[8].Pt8Line2B_Remarks[0]": "examination.disorder_remarks",
    
    # Section 1D - Hansen's Disease (Leprosy)
    "form1[0].#subform[8].Pt8Line1D1_Findings[0]": "examination.hansens_disease",  # a=No, b=Class A, c=Class B
    
    # ========================================================================
    # Page 10: Part 8 Sections 3-4 - Other Conditions (11 fields)
    # ========================================================================
    "form1[0].#subform[9].Pt8Line3A_Findings[0]": "examination.drug_abuse",  # 1=No
    "form1[0].#subform[9].Pt8Line3B_Remarks[0]": "examination.drug_abuse_remarks",
    "form1[0].#subform[9].Pt8Line4_ListOtherMedConditions[0]": "examination.other_conditions",
    
    # ========================================================================
    # Page 12: Part 10 - Vaccination Records (131 fields!)
    # ========================================================================
    # DT (Diphtheria/Tetanus - pediatric)
    "form1[0].P13[0].sfTable[0].Pt10Line1_DTDateReceived1[0]": "vaccinations.dt_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line1_DTDateReceived2[0]": "vaccinations.dt_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line1_DTDateReceived3[0]": "vaccinations.dt_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line1_DTDateReceived4[0]": "vaccinations.dt_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line1_DTDateGiven[0]": "vaccinations.dt_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line1_DTCompleteSeries[0]": "vaccinations.dt_complete",
    "form1[0].P13[0].sfTable[0].Pt10Line1_NotAge1[0]": "vaccinations.dt_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line1_InsufficientCheckBox1[0]": "vaccinations.dt_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line1_ContraCheckBox1[0]": "vaccinations.dt_contraindicated",
    
    # Td/Tdap (Tetanus/Diphtheria/Pertussis - adult)
    "form1[0].P13[0].sfTable[0].P9_TDVaccineCheckBox[0]": "vaccinations.tdap_type",  # Td or Tdap
    "form1[0].P13[0].sfTable[0].Pt10Line2_TdDateReceived1[0]": "vaccinations.tdap_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line2_TdDateReceived2[0]": "vaccinations.tdap_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line2_TdDateReceived3[0]": "vaccinations.tdap_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line2_TdDateReceived4[0]": "vaccinations.tdap_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line2_TdDateGiven[0]": "vaccinations.tdap_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line2_TdCompleteSeries[0]": "vaccinations.tdap_complete",
    "form1[0].P13[0].sfTable[0].Pt10Line2_NotAge2[0]": "vaccinations.tdap_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line2_InsufficientCheckBox2[0]": "vaccinations.tdap_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line2_TdContra[0]": "vaccinations.tdap_contraindicated",
    
    # Polio (IPV/OPV)
    "form1[0].P13[0].sfTable[0].Pt10_PVVaccineCheckBox[0]": "vaccinations.polio_type",  # IPV or OPV
    "form1[0].P13[0].sfTable[0].Pt10Line3a_DateReceived_1[0]": "vaccinations.polio_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line3b_DateReceived_2[0]": "vaccinations.polio_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line3c_DateReceived_3[0]": "vaccinations.polio_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line3d_DateReceived_4[0]": "vaccinations.polio_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line3_DateGiven_1[0]": "vaccinations.polio_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line3_NotAge3[0]": "vaccinations.polio_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line3_InsufficientCheckBox3[0]": "vaccinations.polio_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line3_ContraCheckBox3[0]": "vaccinations.polio_contraindicated",
    
    # Haemophilus influenzae type B (Hib)
    "form1[0].P13[0].sfTable[0].Pt10Line4a_DateReceived_1[0]": "vaccinations.hib_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line4b_DateReceived_2[0]": "vaccinations.hib_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line4c_DateReceived_3[0]": "vaccinations.hib_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line4d_DateReceived_4[0]": "vaccinations.hib_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line4_DateGiven_1[0]": "vaccinations.hib_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line4_NotAge4[0]": "vaccinations.hib_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line4_InsufficientCheckBox4[0]": "vaccinations.hib_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line4_ContraCheckBox4[0]": "vaccinations.hib_contraindicated",
    
    # Rotavirus
    "form1[0].P13[0].sfTable[0].Pt10Line5a_DateReceived_1[0]": "vaccinations.rotavirus_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line5b_DateReceived_2[0]": "vaccinations.rotavirus_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line5c_DateReceived_3[0]": "vaccinations.rotavirus_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line5d_DateReceived_4[0]": "vaccinations.rotavirus_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line5_DateGiven_1[0]": "vaccinations.rotavirus_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line5_NotAge5[0]": "vaccinations.rotavirus_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line5_InsufficientCheckBox5[0]": "vaccinations.rotavirus_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line5_ContraCheckBox5[0]": "vaccinations.rotavirus_contraindicated",
    
    # Hepatitis B
    "form1[0].P13[0].sfTable[0].Pt10Line6_HBDateReceived1[0]": "vaccinations.hep_b_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line6_HBDateReceived2[0]": "vaccinations.hep_b_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line6_HBDateReceived3[0]": "vaccinations.hep_b_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line6_HBDateReceived4[0]": "vaccinations.hep_b_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line6_HBDateGiven[0]": "vaccinations.hep_b_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line1_HBCompleteSeries[0]": "vaccinations.hep_b_complete",
    "form1[0].P13[0].sfTable[0].Pt10Line6_NotAge6[0]": "vaccinations.hep_b_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line6_InsufficientCheckBox6[0]": "vaccinations.hep_b_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line6_ContraCheckBox6[0]": "vaccinations.hep_b_contraindicated",
    
    # MMR (Measles, Mumps, Rubella)
    "form1[0].P13[0].sfTable[0].Pt10Line7a_DateReceived_1[0]": "vaccinations.mmr_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line7b_DateReceived_2[0]": "vaccinations.mmr_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line7c_DateReceived_3[0]": "vaccinations.mmr_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line7d_DateReceived_4[0]": "vaccinations.mmr_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line7_DateGiven_1[0]": "vaccinations.mmr_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line7_NotAge7[0]": "vaccinations.mmr_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line7_InsufficientCheckBox7[0]": "vaccinations.mmr_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line7_ContraCheckBox7[0]": "vaccinations.mmr_contraindicated",
    
    # Varicella (Chickenpox)
    "form1[0].P13[0].sfTable[0].Pt10Line8a_DateReceived_1[0]": "vaccinations.varicella_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line8b_DateReceived_2[0]": "vaccinations.varicella_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line8c_DateReceived_3[0]": "vaccinations.varicella_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line8d_DateReceived_4[0]": "vaccinations.varicella_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line8_DateGiven_1[0]": "vaccinations.varicella_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line8_NotAge8[0]": "vaccinations.varicella_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line8_InsufficientCheckBox8[0]": "vaccinations.varicella_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line8_ContraCheckBox8[0]": "vaccinations.varicella_contraindicated",
    
    # Influenza
    "form1[0].P13[0].sfTable[0].Pt10Line9a_DateReceived_1[0]": "vaccinations.influenza_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line9b_DateReceived_2[0]": "vaccinations.influenza_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line9c_DateReceived_3[0]": "vaccinations.influenza_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line9d_DateReceived_4[0]": "vaccinations.influenza_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line9_DateGiven_1[0]": "vaccinations.influenza_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line9_NotAge9[0]": "vaccinations.influenza_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line9_InfluVaccineInsufficient9[0]": "vaccinations.influenza_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line9_ContraCheckBox9[0]": "vaccinations.influenza_contraindicated",
    
    # Pneumococcal (PCV)
    "form1[0].P13[0].sfTable[0].Pt10Line10a_DateReceived_1[0]": "vaccinations.pneumo_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line10b_DateReceived_2[0]": "vaccinations.pneumo_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line10c_DateReceived_3[0]": "vaccinations.pneumo_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line10d_DateReceived_4[0]": "vaccinations.pneumo_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line10_DateGiven_1[0]": "vaccinations.pneumo_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line10_NotAge10[0]": "vaccinations.pneumo_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line10_InsufficientCheckBox10[0]": "vaccinations.pneumo_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line10_ContraCheckBox10[0]": "vaccinations.pneumo_contraindicated",
    
    # Hepatitis A
    "form1[0].P13[0].sfTable[0].Pt10Line11a_DateReceived_1[0]": "vaccinations.hep_a_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line11b_DateReceived_2[0]": "vaccinations.hep_a_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line11c_DateReceived_3[0]": "vaccinations.hep_a_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line11d_DateReceived_4[0]": "vaccinations.hep_a_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line11_DateGiven_1[0]": "vaccinations.hep_a_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line11_NotAge11[0]": "vaccinations.hep_a_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line11_InsufficientCheckBox11[0]": "vaccinations.hep_a_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line11_ContraCheckBox11[0]": "vaccinations.hep_a_contraindicated",
    
    # Meningococcal
    "form1[0].P13[0].sfTable[0].Pt10Line12a_DateReceived_1[0]": "vaccinations.meningo_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line12b_DateReceived_2[0]": "vaccinations.meningo_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line12c_DateReceived_3[0]": "vaccinations.meningo_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line12d_DateReceived_4[0]": "vaccinations.meningo_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line12_DateGiven_1[0]": "vaccinations.meningo_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line12_NotAge12[0]": "vaccinations.meningo_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line12_InsufficientCheckBox12[0]": "vaccinations.meningo_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line12_ContraCheckBox12[0]": "vaccinations.meningo_contraindicated",
    
    # COVID-19
    "form1[0].P13[0].sfTable[0].Pt10Line13a_DateReceived_1[0]": "vaccinations.covid_date_1",
    "form1[0].P13[0].sfTable[0].Pt10Line13b_DateReceived_2[0]": "vaccinations.covid_date_2",
    "form1[0].P13[0].sfTable[0].Pt10Line13c_DateReceived_3[0]": "vaccinations.covid_date_3",
    "form1[0].P13[0].sfTable[0].Pt10Line13d_DateReceived_4[0]": "vaccinations.covid_date_4",
    "form1[0].P13[0].sfTable[0].Pt10Line13_DateGiven_1[0]": "vaccinations.covid_date_given",
    "form1[0].P13[0].sfTable[0].Pt10Line13_CompleteSeries[0]": "vaccinations.covid_complete",
    "form1[0].P13[0].sfTable[0].Pt10Line13_NotAge12[0]": "vaccinations.covid_not_required_age",
    "form1[0].P13[0].sfTable[0].Pt10Line13_InsufficientCheckBox12[0]": "vaccinations.covid_insufficient",
    "form1[0].P13[0].sfTable[0].Pt10Line13_ContraCheckBox12[0]": "vaccinations.covid_contraindicated",
    
    # ========================================================================
    # Page 13: Vaccination Results/Remarks
    # ========================================================================
    "form1[0].#subform[12].P10_Results[0]": "examination.vaccination_results",  # A, B, or C checkbox
    "form1[0].#subform[12].P10_Remarks[0]": "examination.vaccination_remarks",
    "form1[0].#subform[12].P10_USCIS_Remarks[0]": "examination.uscis_remarks",
    
    # ========================================================================
    # Page 5: Civil Surgeon Signature (7 fields)
    # ========================================================================
    "form1[0].#subform[4].Pt7Line7_CivilSurgeonSignature[0]": "civil_surgeon.signature",
    "form1[0].#subform[4].Pt7Line8_DateofSignature[0]": "civil_surgeon.signature_date",
    
    # ========================================================================
    # Page 8: Additional Syphilis/Treponemal Testing (34 fields)
    # ========================================================================
    # Treponemal test (confirmatory)
    "form1[0].#subform[7].Pt8Line1B1d_name[0]": "examination.treponemal_test_name",
    "form1[0].#subform[7].Pt8Line1B1e_DateScreeningRun[0]": "examination.treponemal_test_date",
    "form1[0].#subform[7].Pt8Line1B1f_TiterOne[0]": "examination.treponemal_titer",
    "form1[0].#subform[7].Pt8Line1B1d_TreponemalReactiveNon[0]": "examination.treponemal_result",  # Reactive/Non-reactive
    
    # Repeat test
    "form1[0].#subform[7].Pt8Line1B1g_nameOfrepeat[0]": "examination.repeat_test_name",
    "form1[0].#subform[7].Pt7Line1B1h_DateOfrepeatTest[0]": "examination.repeat_test_date",
    "form1[0].#subform[7].Pt8Line1B1i_RepeatReativeNon[0]": "examination.repeat_test_result",
    
    # Gonorrhea treatment
    "form1[0].#subform[7].Pt8Line1C3_Drug[0]": "examination.gonorrhea_drug",
    "form1[0].#subform[7].Pt8Line1C3_Dosage[0]": "examination.gonorrhea_dosage",
    "form1[0].#subform[7].Pt8Line1C3_startDate[0]": "examination.gonorrhea_start_date",
    "form1[0].#subform[7].Pt8Line1C3_endDate[0]": "examination.gonorrhea_end_date",
    
    # ========================================================================
    # Page 9: Additional Hansen's/Leprosy fields (19 fields)
    # ========================================================================
    "form1[0].#subform[8].Pt8Line1C2_Remarks[0]": "examination.hansens_remarks",
    "form1[0].#subform[8].Pt8Line1D1b_Checkboxf[0]": "examination.hansens_checkbox_f",
    "form1[0].#subform[8].Pt8Line1C1c_Checkboxg[0]": "examination.hansens_checkbox_g",
    
    # ========================================================================
    # Page 11: Referrals (Part 9) - 32 fields
    # ========================================================================
    # Referral info (Part 8 Section 5)
    "form1[0].#subform[10].Pt8Line5A_DoctorOrHDptName[0]": "referral.doctor_name",
    "form1[0].#subform[10].Pt8Line5B_StreetNumberName[0]": "referral.street",
    "form1[0].#subform[10].Pt8Line5B_AptSteFlrNumber[0]": "referral.apt",
    "form1[0].#subform[10].Pt8Line5B_CityOrTown[0]": "referral.city",
    "form1[0].#subform[10].Pt8Line5B_State[0]": "referral.state",
    "form1[0].#subform[10].Pt8Line5B_ZipCode[0]": "referral.zip",
    "form1[0].#subform[10].Pt8Line5C_DateOfReferral[0]": "referral.date",
    "form1[0].#subform[10].Pt8Line5D_Remarks[0]": "referral.remarks",
    
    # Part 9: Panel physician signature
    "form1[0].#subform[10].Pt9Line1_FamilyName[0]": "panel_physician.family_name",
    "form1[0].#subform[10].Pt9Line1_GivenName[0]": "panel_physician.given_name",
    "form1[0].#subform[10].Pt9Line1_MiddleName[0]": "panel_physician.middle_name",
    "form1[0].#subform[10].Pt9Line1_NameOfMPorHD[0]": "panel_physician.organization",
    "form1[0].#subform[10].Pt9Line2_StreetNumberName[0]": "panel_physician.street",
    "form1[0].#subform[10].Pt9Line2_AptSteFlrNumber[0]": "panel_physician.apt",
    "form1[0].#subform[10].Pt9Line2_CityOrTown[0]": "panel_physician.city",
    "form1[0].#subform[10].Pt9Line2_State[0]": "panel_physician.state",
    "form1[0].#subform[10].Pt9Line2_ZipCode[0]": "panel_physician.zip",
    "form1[0].#subform[10].Pt9Line3_Signature[0]": "panel_physician.signature",
    "form1[0].#subform[10].Pt9Line3_DateSigned[0]": "panel_physician.signature_date",
    "form1[0].#subform[10].Pt9Line4_NameOfMPorHD[0]": "panel_physician.mp_hd_name",
    "form1[0].#subform[10].Pt9Line5_DaytimePhone[0]": "panel_physician.phone",
    
    # ========================================================================
    # Page 14: Additional Information (Part 11) - 21 fields
    # ========================================================================
    "form1[0].#subform[13].Pt11Line3a_PageNumber[0]": "additional_info.line3_page",
    "form1[0].#subform[13].Pt11Line3b_PartNumber[0]": "additional_info.line3_part",
    "form1[0].#subform[13].Pt11Line3c_ItemNumber[0]": "additional_info.line3_item",
    "form1[0].#subform[13].Pt11Line3d_AdditionalInfo[0]": "additional_info.line3_info",
    "form1[0].#subform[13].Pt11Line4a_PageNumber[0]": "additional_info.line4_page",
    "form1[0].#subform[13].Pt11Line4b_PartNumber[0]": "additional_info.line4_part",
    "form1[0].#subform[13].Pt11Line4c_ItemNumber[0]": "additional_info.line4_item",
    "form1[0].#subform[13].Pt11Line4d_AdditionalInfo[0]": "additional_info.line4_info",
    "form1[0].#subform[13].Pt11Line5a_PageNumber[0]": "additional_info.line5_page",
    "form1[0].#subform[13].Pt11Line5b_PartNumber[0]": "additional_info.line5_part",
    "form1[0].#subform[13].Pt11Line5c_ItemNumber[0]": "additional_info.line5_item",
    "form1[0].#subform[13].Pt11Line5d_AdditionalInfo[0]": "additional_info.line5_info",
    "form1[0].#subform[13].Pt11Line6a_PageNumber[0]": "additional_info.line6_page",
    "form1[0].#subform[13].Pt11Line6b_PartNumber[0]": "additional_info.line6_part",
    "form1[0].#subform[13].Pt11Line6c_ItemNumber[0]": "additional_info.line6_item",
    "form1[0].#subform[13].Pt11Line6d_AdditionalInfo[0]": "additional_info.line6_info",
}


# Checkbox field values that indicate "checked" or "yes"
# Note: PDF radio groups may return the same export value (like 'D') for ALL fields in the group
# when any option is selected. The actual selected option is determined by which field has the value.
# The 'D' value appears to be an export value used by some I-693 PDF versions.
CHECKBOX_TRUE_VALUES = {"Yes", "On", "1", "True", "X", "Checked", "P", "A", "Tdap", "Td", "IPV", "OPV", "QF", "TST", "F", "M", "N", "B", "a", "D"}


def get_model_path(pdf_field_name: str) -> str | None:
    """Get the data model path for a PDF field name."""
    return I693_FIELD_MAP.get(pdf_field_name)


def is_checkbox_checked(value: str) -> bool:
    """Determine if a checkbox field value indicates checked/true."""
    return value in CHECKBOX_TRUE_VALUES


def get_checkbox_value(value: str) -> str:
    """Get the actual checkbox value (for radio button groups)."""
    if value and value.strip():
        return value.strip()
    return ""
