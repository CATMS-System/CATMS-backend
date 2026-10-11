-- =====================================================================
-- CareFlow / CATMS (Clinic & Appointment Treatment Management System)
-- Production-Ready Normalized Mock Data Seed Script
-- Compatible with: MySQL 8.0+, MariaDB 10.5+, and ANSI SQL
-- Schema Reference: NORMALIZED_ERD.md
-- =====================================================================

-- Temporarily disable foreign key constraints to allow clean batch loading
SET @OLD_FOREIGN_KEY_CHECKS = @@FOREIGN_KEY_CHECKS;
SET FOREIGN_KEY_CHECKS = 0;

-- Optional: Clean up existing mock records if needed (in reverse dependency order)
-- TRUNCATE TABLE Audit_Log;
-- TRUNCATE TABLE Payment;
-- TRUNCATE TABLE Insurance_Claim;
-- TRUNCATE TABLE Invoice;
-- TRUNCATE TABLE Prescribed_Treatment;
-- TRUNCATE TABLE Consultation;
-- TRUNCATE TABLE Appointment;
-- TRUNCATE TABLE Treatment_Policy_Eligibility;
-- TRUNCATE TABLE Treatment_Catalogue;
-- TRUNCATE TABLE Treatment_Category;
-- TRUNCATE TABLE Insurance_Policy;
-- TRUNCATE TABLE Insurance_Provider;
-- TRUNCATE TABLE Emergency_Contact;
-- TRUNCATE TABLE Patient;
-- TRUNCATE TABLE Doctor_Schedule;
-- TRUNCATE TABLE Doctor_Specialty;
-- TRUNCATE TABLE Specialty;
-- TRUNCATE TABLE Doctor;
-- TRUNCATE TABLE Staff;
-- TRUNCATE TABLE Branch;
-- TRUNCATE TABLE User_Account;

-- =====================================================================
-- DOMAIN 1: SYSTEM SECURITY, AUTHENTICATION & AUDITING
-- =====================================================================

INSERT INTO User_Account (Account_ID, Username, Password_Hash, System_Role, Account_Status, Last_Login_At) VALUES
(1,  'admin_alana',     '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Admin',          'Active', '2026-08-23 08:30:00'),
(2,  'dr_bennett',      '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Doctor',         'Active', '2026-08-23 08:45:12'),
(3,  'dr_jenkins',      '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Doctor',         'Active', '2026-08-23 09:10:05'),
(4,  'dr_perera',       '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Doctor',         'Active', '2026-08-23 09:15:30'),
(5,  'nurse_chen',      '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Receptionist',   'Active', '2026-08-23 08:00:00'),
(6,  'mgr_vance',       '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Branch_Manager', 'Active', '2026-08-23 08:15:20'),
(7,  'billing_patel',   '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Billing_Staff',  'Active', '2026-08-23 08:25:40'),
(8,  'recept_shenaya',  '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Receptionist',   'Active', '2026-08-23 08:05:10'),
(9,  'mgr_silva',       '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Branch_Manager', 'Active', '2026-08-23 08:20:00'),
(10, 'mgr_desilva',     '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Branch_Manager', 'Active', '2026-08-23 08:22:15'),
(11, 'pat_johndoe',     '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Patient',        'Active', '2026-08-22 19:40:22'),
(12, 'pat_clara',       '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Patient',        'Active', '2026-08-23 07:15:45'),
(13, 'pat_david',       '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Patient',        'Active', '2026-08-21 14:10:00'),
(14, 'pat_ananya',      '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Patient',        'Active', '2026-08-20 11:30:15'),
(15, 'billing_kandy',   '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Billing_Staff',  'Active', '2026-08-23 08:25:40'),
(16, 'billing_galle',   '$2b$12$W.5CSwcAAlr6d0aUHuOaOuocGRd8j849Vtf7xO0QpAdRSmixepKAS', 'Billing_Staff',  'Active', '2026-08-23 08:25:40');

-- =====================================================================
-- DOMAIN 2: ORGANIZATION, STAFF & SCHEDULING
-- =====================================================================

-- Step 1: Insert Branches (Manager_Staff_ID initially NULL to prevent circular FK constraint violation)
INSERT INTO Branch (Branch_ID, Manager_Staff_ID, Branch_Name, Street_Address, City, State_Province, Postal_Code, Contact_Number, Email) VALUES
(1, NULL, 'Colombo Main Clinic', '100 Galle Road, Kollupitiya', 'Colombo', 'Western Province', '00300', '+94 11 234 5678', 'colombo@careflow.com'),
(2, NULL, 'Kandy Central Clinic', '25 Peradeniya Road',          'Kandy',   'Central Province', '20000', '+94 81 223 4567', 'kandy@careflow.com'),
(3, NULL, 'Galle Coastal Clinic',  '45 Wakwella Road',           'Galle',   'Southern Province', '80000', '+94 91 222 3456', 'galle@careflow.com');

-- Step 2: Insert Staff Members
INSERT INTO Staff (Staff_ID, Account_ID, Branch_ID, First_Name, Last_Name, Job_Title, Contact_Number, Email, Employment_Status) VALUES
(1,  2,  1, 'Alexander', 'Bennett',        'Consultant Cardiologist',      '+94 77 111 2222', 'bennett@careflow.com',      'Active'),
(2,  3,  2, 'Sarah',     'Jenkins',        'Senior General Practitioner',  '+94 77 333 4444', 'jenkins@careflow.com',      'Active'),
(3,  5,  1, 'Emily',     'Chen',           'Lead Triage Nurse',            '+94 77 555 6666', 'chen@careflow.com',         'Active'),
(4,  6,  1, 'Marcus',    'Vance',          'Branch General Manager',       '+94 77 777 8888', 'vance@careflow.com',        'Active'),
(5,  7,  1, 'Sophia',    'Patel',          'Lead Billing & Claims Officer','+94 77 999 0000', 'patel@careflow.com',        'Active'),
(6,  9,  2, 'Samantha',  'Silva',          'Branch Operations Manager',    '+94 81 222 3333', 'silva@careflow.com',        'Active'),
(7,  10, 3, 'Rohan',     'De Silva',       'Branch Operations Manager',    '+94 91 333 4444', 'rohan@careflow.com',        'Active'),
(8,  4,  3, 'Nimal',     'Perera',         'Consultant Dermatologist',     '+94 71 456 7890', 'nimal@careflow.com',        'Active'),
(9,  8,  1, 'Shenaya',   'Perera',         'Chief Medical Receptionist',   '+94 77 444 1122', 'receptionist@careflow.com', 'Active'),
(10, 1,  1, 'Alana',     'Smith',          'System Administrator',         '+94 77 888 9900', 'admin@careflow.com',        'Active'),
(11, 15, 2, 'Kamal',     'Perera',         'Billing & Cashier Officer',    '+94 81 223 9999', 'kperera.billing@careflow.com', 'Active'),
(12, 16, 3, 'Nirosha',   'Silva',          'Billing & Cashier Officer',    '+94 91 222 8888', 'nsilva.billing@careflow.com',  'Active');

-- Step 3: Link Branch Managers back to Branch
UPDATE Branch SET Manager_Staff_ID = 4 WHERE Branch_ID = 1;
UPDATE Branch SET Manager_Staff_ID = 6 WHERE Branch_ID = 2;
UPDATE Branch SET Manager_Staff_ID = 7 WHERE Branch_ID = 3;

-- Step 4: Insert Doctors (Table-per-Type inheritance from Staff)
INSERT INTO Doctor (Doctor_ID, License_Number, Standard_Consultation_Fee) VALUES
(1, 'SLMC-88321', 2500.00),
(2, 'SLMC-77492', 1500.00),
(8, 'SLMC-66321', 2000.00);

-- Step 5: Insert Medical Specialties
INSERT INTO Specialty (Specialty_ID, Specialty_Name, Description) VALUES
(1, 'Cardiology',        'Heart diseases, vascular conditions, ECG/Echo diagnostics, and hypertension'),
(2, 'General Medicine',  'Primary patient care, acute viral illnesses, preventive diagnostics, and wellness'),
(3, 'Dermatology',       'Skin disorders, allergic dermatitis, lesions, biopsying, and cosmetic care'),
(4, 'Pediatrics',        'Infant, child, and adolescent healthcare and developmental monitoring'),
(5, 'Orthopedics',       'Musculoskeletal conditions, joint disorders, fractures, and rehabilitation');

-- Step 6: Link Doctors to Specialties
INSERT INTO Doctor_Specialty (Doctor_ID, Specialty_ID) VALUES
(1, 1), -- Dr. Bennett -> Cardiology
(1, 2), -- Dr. Bennett -> General Medicine
(2, 2), -- Dr. Jenkins -> General Medicine
(8, 3); -- Dr. Perera  -> Dermatology

-- Step 7: Doctor Working Schedules
INSERT INTO Doctor_Schedule (Schedule_ID, Doctor_ID, Branch_ID, Day_Of_Week, Start_Time, End_Time, Availability_Status) VALUES
(1, 1, 1, 'Monday',    '08:30:00', '13:00:00', 'Active'),
(2, 1, 1, 'Wednesday', '08:30:00', '13:00:00', 'Active'),
(3, 1, 1, 'Friday',    '14:00:00', '18:30:00', 'Active'),
(4, 2, 2, 'Tuesday',   '09:00:00', '14:00:00', 'Active'),
(5, 2, 2, 'Thursday',  '09:00:00', '14:00:00', 'Active'),
(6, 2, 2, 'Saturday',  '09:00:00', '12:30:00', 'Active'),
(7, 8, 3, 'Monday',    '10:00:00', '15:00:00', 'Active'),
(8, 8, 3, 'Thursday',  '10:00:00', '15:00:00', 'Active');

-- =====================================================================
-- DOMAIN 3: PATIENT & INSURANCE MANAGEMENT
-- =====================================================================

-- Step 8: Insert Patients
INSERT INTO Patient (Patient_ID, Account_ID, First_Name, Last_Name, Date_Of_Birth, Gender, NIC, Contact_Number, Email, Street_Address, City, State_Province, Postal_Code, Registration_Date) VALUES
(1, 11,   'John',   'Doe',             '1985-05-12', 'Male',   '852140938V', '+94 77 123 4567', 'john.doe@email.com',  '12 Galle Road, Flat 4B', 'Colombo', 'Western Province',  '00300', '2026-01-10'),
(2, 12,   'Clara',  'Oswald',          '1992-11-23', 'Female', '923281029V', '+94 77 987 6543', 'clara.o@email.com',    '45 Lake Round',          'Kandy',   'Central Province',  '20000', '2026-02-15'),
(3, 13,   'David',  'Miller',          '1970-02-08', 'Male',   '700392109V', '+94 71 456 7890', 'david.m@email.com',    '78 Fort View Road',      'Galle',   'Southern Province', '80000', '2026-03-01'),
(4, 14,   'Ananya', 'Jayawardena',     '1998-07-19', 'Female', '986510442V', '+94 76 555 1234', 'ananya.j@email.com',   '88 Duplication Road',    'Colombo', 'Western Province',  '00400', '2026-04-12'),
(5, NULL, 'Kamal',  'Wickramasinghe',  '1963-09-30', 'Male',   '632740118V', '+94 70 222 9988', NULL,                  '10 Temple Road',         'Kandy',   'Central Province',  '20000', '2026-05-20');

-- Step 9: Emergency Contacts
INSERT INTO Emergency_Contact (Emergency_Contact_ID, Patient_ID, First_Name, Last_Name, Relationship_To_Patient, Contact_Number, Street_Address, City, Postal_Code) VALUES
(1, 1, 'Jane',   'Doe',          'Spouse', '+94 77 123 4568', '12 Galle Road, Flat 4B', 'Colombo', '00300'),
(2, 2, 'Danny',  'Pink',         'Friend', '+94 77 987 6544', '45 Lake Round',          'Kandy',   '20000'),
(3, 3, 'Susan',  'Miller',       'Wife',   '+94 71 456 7891', '78 Fort View Road',      'Galle',   '80000'),
(4, 4, 'Sunil',  'Jayawardena',  'Father', '+94 76 555 9988', '88 Duplication Road',    'Colombo', '00400'),
(5, 5, 'Nalani', 'Wickramasinghe','Wife',  '+94 70 222 9989', '10 Temple Road',         'Kandy',   '20000');

-- Step 10: Insurance Providers
INSERT INTO Insurance_Provider (Provider_ID, Provider_Name, Contact_Number, Email, Street_Address, City, State_Province, Postal_Code) VALUES
(1, 'Union Assurance PLC',                 '+94 11 299 0000', 'claims@unionassurance.com', '20 St. Michael Road',                'Colombo', 'Western Province', '00300'),
(2, 'Softlogic Life Insurance PLC',        '+94 11 312 4000', 'claims@softlogiclife.lk',    'Level 16, One Galle Face Tower',    'Colombo', 'Western Province', '00200'),
(3, 'Sri Lanka Insurance Corporation (SLIC)','+94 11 235 7000', 'medclaims@slic.lk',        '21 Vauxhall Street',                'Colombo', 'Western Province', '00200'),
(4, 'Ceylinco General Insurance',          '+94 11 470 2702', 'medical@ceylincoinsurance.lk','Ceylinco House, Janadhipathi Mawatha','Colombo', 'Western Province', '00100');

-- Step 11: Patient Insurance Policies
INSERT INTO Insurance_Policy (Policy_ID, Patient_ID, Provider_ID, Policy_Number, Policy_Type, Start_Date, End_Date, Default_Coverage_Percentage, Policy_Status) VALUES
(1, 1, 1, 'UA-88321-A', 'Comprehensive',  '2025-01-01', '2027-12-31', 80.00, 'Active'),
(2, 2, 2, 'SL-99321-B', 'Outpatient_Only', '2025-07-01', '2026-06-30', 70.00, 'Active'),
(3, 3, 3, 'SLIC-3341',  'Comprehensive',  '2024-08-24', '2025-08-23', 60.00, 'Expired'),
(4, 4, 4, 'CG-45211-C', 'Comprehensive',  '2026-01-01', '2026-12-31', 75.00, 'Active');

-- =====================================================================
-- DOMAIN 4: CLINICAL VISITS & TREATMENTS
-- =====================================================================

-- Step 12: Treatment Categories
INSERT INTO Treatment_Category (Category_ID, Category_Name, Description) VALUES
(1, 'Cardiovascular Diagnostics', 'Diagnostic tests, imaging, and monitoring procedures for cardiovascular health'),
(2, 'Laboratory & Pathology',     'Blood panels, urine chemistry, and microbiological diagnostic tests'),
(3, 'Dermatological Procedures',   'Skin biopsies, cryotherapy, lesion excisions, and topical therapies'),
(4, 'General Nursing & Care',     'Wound care, dressings, intravenous/intramuscular medication administration'),
(5, 'Radiology & Imaging',        'Digital X-rays, ultrasound scans, and musculoskeletal imaging');

-- Step 13: Treatment Catalogue
INSERT INTO Treatment_Catalogue (Treatment_ID, Category_ID, Service_Code, Treatment_Name, Description, Standard_Unit_Price, Treatment_Status) VALUES
(1,  1, 'CARD-ECG-01',  '12-Lead Electrocardiogram (ECG)',         'Resting 12-lead diagnostic ECG with clinical cardiologist interpretation',   5000.00, 'Active'),
(2,  1, 'CARD-ECHO-02', '2D Echocardiography & Color Doppler',     'Comprehensive ultrasound evaluation of cardiac valves, chambers, and blood flow', 12500.00, 'Active'),
(3,  2, 'LAB-BS-01',    'Blood Sugar Rapid Test',                  'Capillary glucose fingerprick evaluation with immediate digital reading',      600.00, 'Active'),
(4,  2, 'LAB-CBC-02',   'Complete Blood Count (CBC)',              'Full blood count detailing RBC, WBC differential, platelet count, and Hb',    2200.00, 'Active'),
(5,  2, 'LAB-LIPID-03', 'Lipid Profile Comprehensive Panel',       'Fasting lipid panel analyzing Total Cholesterol, Triglycerides, HDL, and LDL', 3500.00, 'Active'),
(6,  3, 'DERM-BIO-01',  'Punch Skin Biopsy (3mm)',                 'Epidermal punch excision of suspicious lesion for histopathology analysis',   6500.00, 'Active'),
(7,  3, 'DERM-CRYO-02', 'Liquid Nitrogen Cryotherapy',             'Targeted cold ablation treatment for cutaneous warts, actinic keratosis',     4200.00, 'Active'),
(8,  4, 'NURS-WND-01',  'Antiseptic Wound Debridement & Dressing', 'Sterile cleaning, debridement, and medicated dressing of wounds',            1800.00, 'Active'),
(9,  4, 'NURS-INJ-02',  'Intramuscular / IV Injection Service',    'Professional nurse administration of prescribed therapeutic injections',       850.00, 'Active'),
(10, 5, 'RAD-XRAY-01',  'Chest X-Ray Digital (PA View)',           'High-resolution digital thoracic radiograph with radiologist report',         8000.00, 'Active');

-- Step 14: Treatment Policy Eligibility (Co-pay and benefit ceilings)
INSERT INTO Treatment_Policy_Eligibility (Policy_ID, Treatment_ID, Covered_Percentage, Coverage_Limit) VALUES
(1, 1,  85.00, 10000.00), -- Policy 1 (UA): 85% on ECG (Limit 10k)
(1, 2,  80.00, 25000.00), -- Policy 1 (UA): 80% on Echo (Limit 25k)
(1, 4,  90.00,  5000.00), -- Policy 1 (UA): 90% on CBC (Limit 5k)
(1, 5,  80.00,  5000.00), -- Policy 1 (UA): 80% on Lipid (Limit 5k)
(2, 3, 100.00,  2000.00), -- Policy 2 (Softlogic): 100% on Blood Sugar
(2, 4,  75.00,  3000.00), -- Policy 2 (Softlogic): 75% on CBC
(2, 8,  80.00,  4000.00), -- Policy 2 (Softlogic): 80% on Wound Dressing
(4, 1,  75.00,  8000.00), -- Policy 4 (Ceylinco): 75% on ECG
(4, 6,  70.00, 15000.00), -- Policy 4 (Ceylinco): 70% on Biopsy
(4, 10, 80.00, 12000.00); -- Policy 4 (Ceylinco): 80% on Chest X-Ray

-- Step 15: Appointments
INSERT INTO Appointment (Appointment_ID, Patient_ID, Doctor_ID, Branch_ID, Schedule_ID, Appointment_Date, Start_Time, Duration_Minutes, Appointment_Type, Status, Cancellation_Reason, Reason_For_Visit, Created_At) VALUES
(1, 1, 1, 1, 1,    '2026-08-23', '09:00:00', 30, 'Standard',  'Completed', NULL,                                'Recurrent chest discomfort and shortness of breath upon exertion', '2026-08-20 10:15:00'),
(2, 2, 2, 2, 4,    '2026-08-23', '10:30:00', 20, 'Standard',  'Completed', NULL,                                'Severe persistent sore throat, difficulty swallowing, mild fever', '2026-08-21 14:00:00'),
(3, 3, 8, 3, 7,    '2026-08-23', '14:00:00', 30, 'Standard',  'Completed', NULL,                                'Aggravated pruritic eczema flare-up across forearm and wrists',   '2026-08-22 09:30:00'),
(4, 1, 1, 1, 2,    '2026-08-26', '11:00:00', 20, 'Follow_Up', 'Confirmed', NULL,                                'Cardiology follow-up to evaluate lipid panel & ECG waveform trend','2026-08-23 10:00:00'),
(5, 4, 1, 1, 3,    '2026-08-28', '15:00:00', 30, 'Standard',  'Scheduled', NULL,                                'Resting palpitations and occasional lightheadedness',             '2026-08-23 11:30:00'),
(6, 5, 2, 2, NULL, '2026-08-23', '11:15:00', 15, 'Walk_In',   'Completed', NULL,                                'Acute spike in blood pressure accompanied by occipital headache', '2026-08-23 11:10:00'),
(7, 2, 2, 2, 5,    '2026-08-20', '09:30:00', 15, 'Standard',  'Cancelled', 'Patient had an emergency trip to Colombo', 'General physical checkup and vitamin routine review',   '2026-08-18 16:45:00');

-- Step 16: Consultations (Completed appointments)
INSERT INTO Consultation (Consultation_ID, Appointment_ID, Consultation_Date, Diagnosis, Clinical_Notes, Doctor_Notes, Follow_Up_Date) VALUES
(1, 1, '2026-08-23', 
 'Mild mitral valve regurgitation with borderline Stage 1 Hypertension',
 'Vitals: BP 138/88 mmHg, HR 76 bpm regular, SpO2 98% on room air, Weight 74 kg. Auscultation reveals soft apical systolic murmur.',
 'Conducted resting 12-lead ECG. Ordered fasting lipid profile panel. Advised reduction in dietary sodium, moderate aerobic exercise, and hydration.',
 '2026-08-26'),

(2, 2, '2026-08-23',
 'Acute streptococcal pharyngitis',
 'Vitals: Oral Temp 100.4 F, BP 118/76 mmHg, HR 84 bpm. Posterior pharyngeal erythema with bilateral tonsillar exudate. Cervical lymphadenopathy noted.',
 'Prescribed Amoxicillin/Clavulanate 625mg BD for 7 days and Paracetamol 500mg TDS. Performed random blood sugar screening at patient request.',
 '2026-08-30'),

(3, 3, '2026-08-23',
 'Atopic dermatitis with secondary mild cutaneous bacterial superinfection',
 'Vitals: Within normal physiological parameters. Excoriated, erythematous lichenified plaques over bilateral flexor surfaces with serous oozing.',
 'Cleaned affected area and applied antiseptic barrier dressing. Prescribed topical Mometasone furoate 0.1% cream and oral Cetirizine 10mg nocte.',
 '2026-09-06'),

(4, 6, '2026-08-23',
 'Stage 2 Essential Hypertension (Acute Exacerbation)',
 'Vitals: BP 168/102 mmHg, HR 88 bpm. Cranial nerve assessment unremarkable, no signs of acute hypertensive retinopathy or stroke.',
 'Administered emergency stat parenteral dose. Monitored in day ward for 45 minutes; repeat blood pressure settled to 138/86 mmHg. Prescribed daily maintenance Amlodipine 5mg.',
 '2026-08-25');

-- Step 17: Prescribed Treatments (Historical pricing snapshot preserved)
INSERT INTO Prescribed_Treatment (Prescription_Item_ID, Consultation_ID, Treatment_ID, Quantity, Billed_Unit_Price, Instructions) VALUES
(1, 1, 1, 1, 5000.00, 'Baseline resting 12-lead ECG prior to prescribing cardiovascular medication'),
(2, 1, 5, 1, 3500.00, 'Fasting lipid profile panel; patient must fast for 12 hours prior to venous puncture'),
(3, 2, 3, 2,  600.00, 'Rapid blood sugar fingerprick test (pre-prandial and post-prandial assessment)'),
(4, 2, 4, 1, 2200.00, 'Complete Blood Count (CBC) to monitor systemic inflammatory response'),
(5, 3, 8, 1, 1800.00, 'Antiseptic debridement and zinc oxide protective dressing applied to bilateral forearms'),
(6, 4, 9, 1,  850.00, 'Immediate intramuscular emergency injection of antihypertensive therapeutic');

-- =====================================================================
-- DOMAIN 5: BILLING, CLAIMS & PAYMENTS
-- =====================================================================

-- Step 18: Invoices (Base consultation fee snapshot; item totals computed via view)
INSERT INTO Invoice (Invoice_ID, Consultation_ID, Invoice_Date, Billed_Consultation_Fee, Invoice_Status) VALUES
(1, 1, '2026-08-23', 2500.00, 'Paid'),           -- Bennett Cardiology consult ($2,500) + Treatments ($8,500) = $11,000 Total
(2, 2, '2026-08-23', 1500.00, 'Partially_Paid'), -- Jenkins GP consult ($1,500) + Treatments ($3,400) = $4,900 Total
(3, 3, '2026-08-23', 2000.00, 'Paid'),           -- Perera Derm consult ($2,000) + Treatments ($1,800) = $3,800 Total
(4, 4, '2026-08-23', 1500.00, 'Paid');           -- Jenkins Walk-In consult ($1,500) + Treatments ($850) = $2,350 Total

-- Step 19: Insurance Claims
INSERT INTO Insurance_Claim (Claim_ID, Invoice_ID, Policy_ID, Claim_Date, Claimed_Amount, Approved_Amount, Claim_Status, Settlement_Date) VALUES
(1, 1, 1, '2026-08-23', 8800.00, 8800.00, 'Settled',  '2026-08-24'), -- 80% coverage on $11,000 bill = $8,800 approved & settled
(2, 2, 2, '2026-08-23', 2550.00, 2550.00, 'Approved', NULL),         -- Softlogic covered $2,550 of treatments, awaiting settlement
(3, 3, 3, '2026-08-23', 2280.00,    0.00, 'Rejected', '2026-08-23'); -- Policy SLIC-3341 expired on 2025-08-23, claim rejected

-- Step 20: Payments (Patient Out-of-Pocket Settlements)
INSERT INTO Payment (Payment_ID, Invoice_ID, Payment_Date, Amount, Payment_Method, Payment_Status, Transaction_Reference) VALUES
(1, 1, '2026-08-23', 2200.00, 'Credit_Card',   'Completed', 'TXN-20260823-CARD-001'), -- John Doe settled $2,200 co-pay via Visa Card
(2, 2, '2026-08-23', 1000.00, 'Cash',          'Completed', 'TXN-20260823-CASH-002'), -- Clara Oswald partial cash payment of $1,000 (remains $1,350 due)
(3, 3, '2026-08-23', 3800.00, 'Online',        'Completed', 'TXN-20260823-ONL-003'),  -- David Miller settled full $3,800 after claim rejection via portal
(4, 4, '2026-08-23', 2350.00, 'Cash',          'Completed', 'TXN-20260823-CASH-004'); -- Kamal Wickramasinghe paid $2,350 total in cash

-- =====================================================================
-- SYSTEM AUDIT LOGS
-- =====================================================================

INSERT INTO Audit_Log (Audit_ID, Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Timestamp, Old_Value, New_Value) VALUES
(1, 1, 1, 'Staff',        '8', 'INSERT', '2026-08-23 09:15:32', NULL, 
 '{"Staff_ID": 8, "First_Name": "Nimal", "Last_Name": "Perera", "Job_Title": "Consultant Dermatologist", "Branch_ID": 3}'),

(2, 2, 1, 'Appointment',  '1', 'UPDATE', '2026-08-23 09:45:10', 
 '{"Status": "Confirmed"}', 
 '{"Status": "Completed"}'),

(3, 2, 1, 'Consultation', '1', 'INSERT', '2026-08-23 09:46:00', NULL, 
 '{"Consultation_ID": 1, "Appointment_ID": 1, "Diagnosis": "Mild mitral valve regurgitation with borderline Stage 1 Hypertension"}'),

(4, 7, 1, 'Invoice',      '1', 'INSERT', '2026-08-23 09:50:12', NULL, 
 '{"Invoice_ID": 1, "Consultation_ID": 1, "Billed_Consultation_Fee": 2500.00, "Invoice_Status": "Issued"}'),

(5, 7, 1, 'Insurance_Claim', '1', 'INSERT', '2026-08-23 09:52:00', NULL, 
 '{"Claim_ID": 1, "Invoice_ID": 1, "Claimed_Amount": 8800.00, "Claim_Status": "Submitted"}'),

(6, 7, 1, 'Payment',      '1', 'INSERT', '2026-08-23 09:55:40', NULL, 
 '{"Payment_ID": 1, "Invoice_ID": 1, "Amount": 2200.00, "Payment_Method": "Credit_Card", "Payment_Status": "Completed"}');

-- Re-enable foreign key constraints
SET FOREIGN_KEY_CHECKS = @OLD_FOREIGN_KEY_CHECKS;
