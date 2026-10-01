CREATE DATABASE IF NOT EXISTS CatMS;
USE CatMS;

-- ========================================================
-- Disable foreign key checks for safe re-runs
-- ========================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ========================================================
-- Drop existing tables if they exist
-- Drop child/dependent tables first
-- ========================================================

DROP TABLE IF EXISTS Audit_Log;
DROP TABLE IF EXISTS Payment;
DROP TABLE IF EXISTS Insurance_Claim;
DROP TABLE IF EXISTS Invoice;
DROP TABLE IF EXISTS Prescribed_Treatment;
DROP TABLE IF EXISTS Consultation;
DROP TABLE IF EXISTS Appointment;
DROP TABLE IF EXISTS Treatment_Policy_Eligibility;
DROP TABLE IF EXISTS Treatment_Catalogue;
DROP TABLE IF EXISTS Treatment_Category;
DROP TABLE IF EXISTS Insurance_Policy;
DROP TABLE IF EXISTS Insurance_Provider;
DROP TABLE IF EXISTS Emergency_Contact;
DROP TABLE IF EXISTS Patient;
DROP TABLE IF EXISTS Doctor_Schedule;
DROP TABLE IF EXISTS Doctor_Specialty;
DROP TABLE IF EXISTS Specialty;
DROP TABLE IF EXISTS Doctor;
DROP TABLE IF EXISTS Staff;
DROP TABLE IF EXISTS Branch;
DROP TABLE IF EXISTS User_Account;

SET FOREIGN_KEY_CHECKS = 1;


-- ========================================================
-- DOMAIN 1: SYSTEM SECURITY, AUTHENTICATION & AUDITING
-- ========================================================

CREATE TABLE User_Account (
    Account_ID INT PRIMARY KEY AUTO_INCREMENT,
    Username VARCHAR(50) UNIQUE NOT NULL,
    Password_Hash VARCHAR(255) NOT NULL,

    System_Role ENUM(
        'Admin',
        'Branch_Manager',
        'Doctor',
        'Receptionist',
        'Billing_Staff',
        'Patient'
    ) NOT NULL,

    Account_Status ENUM(
        'Active',
        'Suspended',
        'Deactivated'
    ) NOT NULL DEFAULT 'Active',

    Last_Login_At TIMESTAMP NULL
);


-- ========================================================
-- DOMAIN 2: ORGANIZATION, STAFF & SCHEDULING
-- ========================================================

CREATE TABLE Branch (
    Branch_ID INT PRIMARY KEY AUTO_INCREMENT,

    Manager_Staff_ID INT NULL,

    Branch_Name VARCHAR(100) UNIQUE NOT NULL,
    Street_Address VARCHAR(150) NOT NULL,
    City VARCHAR(50) NOT NULL,
    State_Province VARCHAR(50) NOT NULL,
    Postal_Code VARCHAR(20) NOT NULL,

    Contact_Number VARCHAR(20) NOT NULL,
    Email VARCHAR(100) NOT NULL
);


CREATE TABLE Audit_Log (
    Audit_ID BIGINT PRIMARY KEY AUTO_INCREMENT,

    Account_ID INT NOT NULL,
    Branch_ID INT NULL,

    Table_Name VARCHAR(64) NOT NULL,
    Record_ID VARCHAR(64) NOT NULL,

    Action_Type ENUM(
        'INSERT',
        'UPDATE',
        'DELETE'
    ) NOT NULL,

    Timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    Old_Value JSON NULL,
    New_Value JSON NULL,

    CONSTRAINT fk_audit_account
        FOREIGN KEY (Account_ID)
        REFERENCES User_Account(Account_ID),

    CONSTRAINT fk_audit_branch
        FOREIGN KEY (Branch_ID)
        REFERENCES Branch(Branch_ID)
);


CREATE TABLE Staff (
    Staff_ID INT PRIMARY KEY AUTO_INCREMENT,

    Account_ID INT UNIQUE NOT NULL,
    Branch_ID INT NOT NULL,

    First_Name VARCHAR(50) NOT NULL,
    Last_Name VARCHAR(50) NOT NULL,

    Job_Title VARCHAR(100) NOT NULL,

    Contact_Number VARCHAR(20) NOT NULL,
    Email VARCHAR(100) NOT NULL,

    Employment_Status ENUM(
        'Active',
        'On_Leave',
        'Terminated'
    ) NOT NULL DEFAULT 'Active',

    CONSTRAINT fk_staff_account
        FOREIGN KEY (Account_ID)
        REFERENCES User_Account(Account_ID),

    CONSTRAINT fk_staff_branch
        FOREIGN KEY (Branch_ID)
        REFERENCES Branch(Branch_ID)
);


-- Add Branch Manager FK after Staff table exists

ALTER TABLE Branch
ADD CONSTRAINT fk_branch_manager
    FOREIGN KEY (Manager_Staff_ID)
    REFERENCES Staff(Staff_ID);


-- ========================================================
-- DOCTOR
-- Table-per-Type Inheritance
-- Doctor_ID matches Staff_ID
-- ========================================================

CREATE TABLE Doctor (
    Doctor_ID INT PRIMARY KEY,

    License_Number VARCHAR(50) UNIQUE NOT NULL,

    Standard_Consultation_Fee DECIMAL(10, 2) NOT NULL CHECK (Standard_Consultation_Fee > 0),

    CONSTRAINT fk_doctor_staff
        FOREIGN KEY (Doctor_ID)
        REFERENCES Staff(Staff_ID)
        ON DELETE CASCADE
);


CREATE TABLE Specialty (
    Specialty_ID INT PRIMARY KEY AUTO_INCREMENT,

    Specialty_Name VARCHAR(100) UNIQUE NOT NULL,

    Description TEXT NULL
);


CREATE TABLE Doctor_Specialty (
    Doctor_ID INT NOT NULL,
    Specialty_ID INT NOT NULL,

    PRIMARY KEY (Doctor_ID, Specialty_ID),

    CONSTRAINT fk_ds_doctor
        FOREIGN KEY (Doctor_ID)
        REFERENCES Doctor(Doctor_ID)
        ON DELETE CASCADE,

    CONSTRAINT fk_ds_specialty
        FOREIGN KEY (Specialty_ID)
        REFERENCES Specialty(Specialty_ID)
        ON DELETE CASCADE
);


CREATE TABLE Doctor_Schedule (
    Schedule_ID INT PRIMARY KEY AUTO_INCREMENT,

    Doctor_ID INT NOT NULL,
    Branch_ID INT NOT NULL,

    Day_Of_Week ENUM(
        'Monday',
        'Tuesday',
        'Wednesday',
        'Thursday',
        'Friday',
        'Saturday',
        'Sunday'
    ) NOT NULL,

    Start_Time TIME NOT NULL,
    End_Time TIME NOT NULL,

    Availability_Status ENUM(
        'Active',
        'Suspended',
        'On_Call'
    ) NOT NULL DEFAULT 'Active',

    CONSTRAINT chk_schedule_time
        CHECK (Start_Time < End_Time),

    CONSTRAINT fk_sched_doctor
        FOREIGN KEY (Doctor_ID)
        REFERENCES Doctor(Doctor_ID),

    CONSTRAINT fk_sched_branch
        FOREIGN KEY (Branch_ID)
        REFERENCES Branch(Branch_ID)
);


-- ========================================================
-- DOMAIN 3: PATIENT & INSURANCE MANAGEMENT
-- ========================================================

CREATE TABLE Patient (
    Patient_ID INT PRIMARY KEY AUTO_INCREMENT,

    Account_ID INT UNIQUE NULL,

    First_Name VARCHAR(50) NOT NULL,
    Last_Name VARCHAR(50) NOT NULL,

    Date_Of_Birth DATE NOT NULL,

    Gender ENUM(
        'Male',
        'Female',
        'Other'
    ) NOT NULL,

    NIC VARCHAR(20) UNIQUE NOT NULL,

    Contact_Number VARCHAR(20) NOT NULL,

    Email VARCHAR(100) NULL,

    Street_Address VARCHAR(150) NOT NULL,
    City VARCHAR(50) NOT NULL,
    State_Province VARCHAR(50) NOT NULL,
    Postal_Code VARCHAR(20) NOT NULL,

    Registration_Date DATE NOT NULL DEFAULT (CURRENT_DATE),

    CONSTRAINT fk_patient_account
        FOREIGN KEY (Account_ID)
        REFERENCES User_Account(Account_ID)
);


CREATE TABLE Emergency_Contact (
    Emergency_Contact_ID INT PRIMARY KEY AUTO_INCREMENT,

    Patient_ID INT NOT NULL,

    First_Name VARCHAR(50) NOT NULL,
    Last_Name VARCHAR(50) NOT NULL,

    Relationship_To_Patient VARCHAR(50) NOT NULL,

    Contact_Number VARCHAR(20) NOT NULL,

    Street_Address VARCHAR(150) NULL,
    City VARCHAR(50) NULL,
    Postal_Code VARCHAR(20) NULL,

    CONSTRAINT fk_ec_patient
        FOREIGN KEY (Patient_ID)
        REFERENCES Patient(Patient_ID)
        ON DELETE CASCADE
);


CREATE TABLE Insurance_Provider (
    Provider_ID INT PRIMARY KEY AUTO_INCREMENT,

    Provider_Name VARCHAR(100) UNIQUE NOT NULL,

    Contact_Number VARCHAR(20) NOT NULL,
    Email VARCHAR(100) NOT NULL,

    Street_Address VARCHAR(150) NOT NULL,
    City VARCHAR(50) NOT NULL,
    State_Province VARCHAR(50) NOT NULL,
    Postal_Code VARCHAR(20) NOT NULL
);


CREATE TABLE Insurance_Policy (
    Policy_ID INT PRIMARY KEY AUTO_INCREMENT,

    Patient_ID INT NOT NULL,
    Provider_ID INT NOT NULL,

    Policy_Number VARCHAR(50) NOT NULL,

    Policy_Type ENUM(
        'Comprehensive',
        'Outpatient_Only',
        'Catastrophic'
    ) NOT NULL,

    Start_Date DATE NOT NULL,
    End_Date DATE NOT NULL,

    Default_Coverage_Percentage DECIMAL(5, 2) NOT NULL,

    Policy_Status ENUM(
        'Active',
        'Expired',
        'Terminated'
    ) NOT NULL DEFAULT 'Active',

    CONSTRAINT chk_policy_dates
        CHECK (Start_Date <= End_Date),

    CONSTRAINT fk_policy_patient
        FOREIGN KEY (Patient_ID)
        REFERENCES Patient(Patient_ID),

    CONSTRAINT fk_policy_provider
        FOREIGN KEY (Provider_ID)
        REFERENCES Insurance_Provider(Provider_ID),

    CONSTRAINT uq_policy_provider_number
        UNIQUE (Provider_ID, Policy_Number)
);


-- ========================================================
-- DOMAIN 4: CLINICAL VISITS & TREATMENTS
-- ========================================================

CREATE TABLE Treatment_Category (
    Category_ID INT PRIMARY KEY AUTO_INCREMENT,

    Category_Name VARCHAR(100) UNIQUE NOT NULL,

    Description TEXT NULL
);


CREATE TABLE Treatment_Catalogue (
    Treatment_ID INT PRIMARY KEY AUTO_INCREMENT,

    Category_ID INT NOT NULL,

    Service_Code VARCHAR(30) UNIQUE NOT NULL,

    Treatment_Name VARCHAR(100) NOT NULL,

    Description TEXT NULL,

    Standard_Unit_Price DECIMAL(10, 2) NOT NULL,

    Treatment_Status ENUM(
        'Active',
        'Discontinued'
    ) NOT NULL DEFAULT 'Active',

    CONSTRAINT fk_tc_category
        FOREIGN KEY (Category_ID)
        REFERENCES Treatment_Category(Category_ID)
);


CREATE TABLE Treatment_Policy_Eligibility (
    Policy_ID INT NOT NULL,
    Treatment_ID INT NOT NULL,

    Covered_Percentage DECIMAL(5, 2) NOT NULL,

    Coverage_Limit DECIMAL(10, 2) NOT NULL,

    PRIMARY KEY (Policy_ID, Treatment_ID),

    CONSTRAINT fk_tpe_policy
        FOREIGN KEY (Policy_ID)
        REFERENCES Insurance_Policy(Policy_ID)
        ON DELETE CASCADE,

    CONSTRAINT fk_tpe_treatment
        FOREIGN KEY (Treatment_ID)
        REFERENCES Treatment_Catalogue(Treatment_ID)
);


CREATE TABLE Appointment (
    Appointment_ID INT PRIMARY KEY AUTO_INCREMENT,

    Patient_ID INT NOT NULL,
    Doctor_ID INT NOT NULL,
    Branch_ID INT NOT NULL,

    Schedule_ID INT NULL,

    Appointment_Date DATE NOT NULL,

    Start_Time TIME NOT NULL,

    Duration_Minutes INT NOT NULL DEFAULT 15 CHECK (Duration_Minutes > 0),

    Appointment_Type ENUM(
        'Standard',
        'Follow_Up',
        'Emergency',
        'Walk_In'
    ) NOT NULL,

    Status ENUM(
        'Scheduled',
        'Confirmed',
        'Completed',
        'Cancelled',
        'No_Show'
    ) NOT NULL DEFAULT 'Scheduled',

    Cancellation_Reason VARCHAR(255) NULL,

    Reason_For_Visit VARCHAR(255) NOT NULL,

    Created_At TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_appt_patient
        FOREIGN KEY (Patient_ID)
        REFERENCES Patient(Patient_ID),

    CONSTRAINT fk_appt_doctor
        FOREIGN KEY (Doctor_ID)
        REFERENCES Doctor(Doctor_ID),

    CONSTRAINT fk_appt_branch
        FOREIGN KEY (Branch_ID)
        REFERENCES Branch(Branch_ID),

    CONSTRAINT fk_appt_schedule
        FOREIGN KEY (Schedule_ID)
        REFERENCES Doctor_Schedule(Schedule_ID)
);

CREATE INDEX idx_appointment_doctor_date ON Appointment(Doctor_ID, Appointment_Date);

CREATE TABLE Consultation (
    Consultation_ID INT PRIMARY KEY AUTO_INCREMENT,

    Appointment_ID INT UNIQUE NOT NULL,

    Consultation_Date DATE NOT NULL DEFAULT (CURRENT_DATE),

    Diagnosis TEXT NOT NULL,

    Clinical_Notes TEXT NULL,

    Doctor_Notes TEXT NULL,

    Follow_Up_Date DATE NULL,

    CONSTRAINT fk_consult_appt
        FOREIGN KEY (Appointment_ID)
        REFERENCES Appointment(Appointment_ID)
);


CREATE TABLE Prescribed_Treatment (
    Prescription_Item_ID INT PRIMARY KEY AUTO_INCREMENT,

    Consultation_ID INT NOT NULL,
    Treatment_ID INT NOT NULL,

    Quantity INT NOT NULL DEFAULT 1,

    Billed_Unit_Price DECIMAL(10, 2) NOT NULL,

    Instructions TEXT NULL,

    CONSTRAINT chk_qty
        CHECK (Quantity > 0),

    CONSTRAINT fk_pt_consultation
        FOREIGN KEY (Consultation_ID)
        REFERENCES Consultation(Consultation_ID),

    CONSTRAINT fk_pt_treatment
        FOREIGN KEY (Treatment_ID)
        REFERENCES Treatment_Catalogue(Treatment_ID)
);


-- ========================================================
-- DOMAIN 5: BILLING, CLAIMS & PAYMENTS
-- ========================================================

CREATE TABLE Invoice (
    Invoice_ID INT PRIMARY KEY AUTO_INCREMENT,

    Consultation_ID INT UNIQUE NOT NULL,

    Invoice_Date DATE NOT NULL DEFAULT (CURRENT_DATE),

    Billed_Consultation_Fee DECIMAL(10, 2) NOT NULL,

    Invoice_Status ENUM(
        'Draft',
        'Issued',
        'Partially_Paid',
        'Paid',
        'Cancelled'
    ) NOT NULL DEFAULT 'Issued',

    CONSTRAINT fk_invoice_consultation
        FOREIGN KEY (Consultation_ID)
        REFERENCES Consultation(Consultation_ID)
);


CREATE TABLE Insurance_Claim (
    Claim_ID INT PRIMARY KEY AUTO_INCREMENT,

    Invoice_ID INT NOT NULL,
    Policy_ID INT NOT NULL,

    Claim_Date DATE NOT NULL DEFAULT (CURRENT_DATE),

    Claimed_Amount DECIMAL(10, 2) NOT NULL,

    Approved_Amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,

    Claim_Status ENUM(
        'Submitted',
        'Under_Review',
        'Approved',
        'Rejected',
        'Settled'
    ) NOT NULL DEFAULT 'Submitted',

    Settlement_Date DATE NULL,

    CONSTRAINT fk_claim_invoice
        FOREIGN KEY (Invoice_ID)
        REFERENCES Invoice(Invoice_ID),

    CONSTRAINT fk_claim_policy
        FOREIGN KEY (Policy_ID)
        REFERENCES Insurance_Policy(Policy_ID),
    
    CONSTRAINT chk_claim_amount
        CHECK (Claimed_Amount > 0),

    CONSTRAINT chk_approved_not_exceed_claimed
        CHECK (Approved_Amount <= Claimed_Amount),

    CONSTRAINT chk_settlement_date
        CHECK (Claim_Status != 'Settled' OR Settlement_Date IS NOT NULL)
);


CREATE TABLE Payment (
    Payment_ID INT PRIMARY KEY AUTO_INCREMENT,

    Invoice_ID INT NOT NULL,

    Payment_Date DATE NOT NULL DEFAULT (CURRENT_DATE),

    Amount DECIMAL(10, 2) NOT NULL,

    Payment_Method ENUM(
        'Cash',
        'Credit_Card',
        'Debit_Card',
        'Bank_Transfer',
        'Online'
    ) NOT NULL,

    Payment_Status ENUM(
        'Pending',
        'Completed',
        'Failed',
        'Refunded'
    ) NOT NULL DEFAULT 'Completed',

    Transaction_Reference VARCHAR(100) UNIQUE NOT NULL,

    CONSTRAINT chk_payment_amount
        CHECK (Amount > 0),

    CONSTRAINT fk_payment_invoice
        FOREIGN KEY (Invoice_ID)
        REFERENCES Invoice(Invoice_ID)
);