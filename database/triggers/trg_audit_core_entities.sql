-- ========================================================
-- Trigger: trg_audit_core_entities
-- Domain: Cross-domain Audit Logging (REQ-PAT-10, NFR-SEC-03)
-- Automatically records persistent Audit_Log rows for changes to
-- Patient, Appointment, Consultation, Invoice, Payment, and Insurance_Claim.
-- Reads session variables @app_account_id (or @current_account_id)
-- and @app_branch_id (or @current_branch_id), falling back to 1 (Admin).
-- ========================================================

DELIMITER $$

-- --------------------------------------------------------
-- Patient Triggers (Clean up if previously defined; handled by patient_service)
-- --------------------------------------------------------

DROP TRIGGER IF EXISTS trg_after_patient_insert$$
DROP TRIGGER IF EXISTS trg_after_patient_update$$

-- --------------------------------------------------------
-- Appointment Triggers
-- --------------------------------------------------------

DROP TRIGGER IF EXISTS trg_after_appointment_insert$$

CREATE TRIGGER trg_after_appointment_insert
AFTER INSERT ON Appointment
FOR EACH ROW
BEGIN
    DECLARE v_account_id INT DEFAULT 1;
    DECLARE v_branch_id INT DEFAULT NULL;

    IF @audit_bypass IS NULL OR @audit_bypass != 1 THEN
        IF @app_account_id IS NOT NULL THEN
            SET v_account_id = @app_account_id;
        ELSEIF @current_account_id IS NOT NULL THEN
            SET v_account_id = @current_account_id;
        END IF;

        SET v_branch_id = NEW.Branch_ID;

        INSERT INTO Audit_Log (
            Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value
        ) VALUES (
            v_account_id,
            v_branch_id,
            'Appointment',
            CAST(NEW.Appointment_ID AS CHAR),
            'INSERT',
            NULL,
            JSON_OBJECT(
                'Appointment_ID', NEW.Appointment_ID,
                'Patient_ID', NEW.Patient_ID,
                'Doctor_ID', NEW.Doctor_ID,
                'Branch_ID', NEW.Branch_ID,
                'Appointment_Date', NEW.Appointment_Date,
                'Start_Time', CAST(NEW.Start_Time AS CHAR),
                'Duration_Minutes', NEW.Duration_Minutes,
                'Appointment_Type', NEW.Appointment_Type,
                'Status', NEW.Status,
                'Reason_For_Visit', NEW.Reason_For_Visit
            )
        );
    END IF;
END$$

DROP TRIGGER IF EXISTS trg_after_appointment_update$$

CREATE TRIGGER trg_after_appointment_update
AFTER UPDATE ON Appointment
FOR EACH ROW
BEGIN
    DECLARE v_account_id INT DEFAULT 1;
    DECLARE v_branch_id INT DEFAULT NULL;

    IF @audit_bypass IS NULL OR @audit_bypass != 1 THEN
        IF @app_account_id IS NOT NULL THEN
            SET v_account_id = @app_account_id;
        ELSEIF @current_account_id IS NOT NULL THEN
            SET v_account_id = @current_account_id;
        END IF;

        SET v_branch_id = NEW.Branch_ID;

        INSERT INTO Audit_Log (
            Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value
        ) VALUES (
            v_account_id,
            v_branch_id,
            'Appointment',
            CAST(NEW.Appointment_ID AS CHAR),
            'UPDATE',
            JSON_OBJECT(
                'Appointment_ID', OLD.Appointment_ID,
                'Patient_ID', OLD.Patient_ID,
                'Doctor_ID', OLD.Doctor_ID,
                'Branch_ID', OLD.Branch_ID,
                'Appointment_Date', OLD.Appointment_Date,
                'Start_Time', CAST(OLD.Start_Time AS CHAR),
                'Duration_Minutes', OLD.Duration_Minutes,
                'Appointment_Type', OLD.Appointment_Type,
                'Status', OLD.Status,
                'Cancellation_Reason', OLD.Cancellation_Reason,
                'Reason_For_Visit', OLD.Reason_For_Visit
            ),
            JSON_OBJECT(
                'Appointment_ID', NEW.Appointment_ID,
                'Patient_ID', NEW.Patient_ID,
                'Doctor_ID', NEW.Doctor_ID,
                'Branch_ID', NEW.Branch_ID,
                'Appointment_Date', NEW.Appointment_Date,
                'Start_Time', CAST(NEW.Start_Time AS CHAR),
                'Duration_Minutes', NEW.Duration_Minutes,
                'Appointment_Type', NEW.Appointment_Type,
                'Status', NEW.Status,
                'Cancellation_Reason', NEW.Cancellation_Reason,
                'Reason_For_Visit', NEW.Reason_For_Visit
            )
        );
    END IF;
END$$

-- --------------------------------------------------------
-- Consultation Triggers
-- --------------------------------------------------------

DROP TRIGGER IF EXISTS trg_after_consultation_insert$$

CREATE TRIGGER trg_after_consultation_insert
AFTER INSERT ON Consultation
FOR EACH ROW
BEGIN
    DECLARE v_account_id INT DEFAULT 1;
    DECLARE v_branch_id INT DEFAULT NULL;

    IF @audit_bypass IS NULL OR @audit_bypass != 1 THEN
        IF @app_account_id IS NOT NULL THEN
            SET v_account_id = @app_account_id;
        ELSEIF @current_account_id IS NOT NULL THEN
            SET v_account_id = @current_account_id;
        END IF;

        IF @app_branch_id IS NOT NULL THEN
            SET v_branch_id = @app_branch_id;
        ELSEIF @current_branch_id IS NOT NULL THEN
            SET v_branch_id = @current_branch_id;
        END IF;

        INSERT INTO Audit_Log (
            Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value
        ) VALUES (
            v_account_id,
            v_branch_id,
            'Consultation',
            CAST(NEW.Consultation_ID AS CHAR),
            'INSERT',
            NULL,
            JSON_OBJECT(
                'Consultation_ID', NEW.Consultation_ID,
                'Appointment_ID', NEW.Appointment_ID,
                'Consultation_Date', NEW.Consultation_Date,
                'Diagnosis', NEW.Diagnosis,
                'Follow_Up_Date', NEW.Follow_Up_Date
            )
        );
    END IF;
END$$

DROP TRIGGER IF EXISTS trg_after_consultation_update$$

CREATE TRIGGER trg_after_consultation_update
AFTER UPDATE ON Consultation
FOR EACH ROW
BEGIN
    DECLARE v_account_id INT DEFAULT 1;
    DECLARE v_branch_id INT DEFAULT NULL;

    IF @audit_bypass IS NULL OR @audit_bypass != 1 THEN
        IF @app_account_id IS NOT NULL THEN
            SET v_account_id = @app_account_id;
        ELSEIF @current_account_id IS NOT NULL THEN
            SET v_account_id = @current_account_id;
        END IF;

        IF @app_branch_id IS NOT NULL THEN
            SET v_branch_id = @app_branch_id;
        ELSEIF @current_branch_id IS NOT NULL THEN
            SET v_branch_id = @current_branch_id;
        END IF;

        INSERT INTO Audit_Log (
            Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value
        ) VALUES (
            v_account_id,
            v_branch_id,
            'Consultation',
            CAST(NEW.Consultation_ID AS CHAR),
            'UPDATE',
            JSON_OBJECT(
                'Consultation_ID', OLD.Consultation_ID,
                'Appointment_ID', OLD.Appointment_ID,
                'Consultation_Date', OLD.Consultation_Date,
                'Diagnosis', OLD.Diagnosis,
                'Follow_Up_Date', OLD.Follow_Up_Date
            ),
            JSON_OBJECT(
                'Consultation_ID', NEW.Consultation_ID,
                'Appointment_ID', NEW.Appointment_ID,
                'Consultation_Date', NEW.Consultation_Date,
                'Diagnosis', NEW.Diagnosis,
                'Follow_Up_Date', NEW.Follow_Up_Date
            )
        );
    END IF;
END$$

-- --------------------------------------------------------
-- Invoice Triggers
-- --------------------------------------------------------

DROP TRIGGER IF EXISTS trg_after_invoice_insert$$

CREATE TRIGGER trg_after_invoice_insert
AFTER INSERT ON Invoice
FOR EACH ROW
BEGIN
    DECLARE v_account_id INT DEFAULT 1;
    DECLARE v_branch_id INT DEFAULT NULL;

    IF @audit_bypass IS NULL OR @audit_bypass != 1 THEN
        IF @app_account_id IS NOT NULL THEN
            SET v_account_id = @app_account_id;
        ELSEIF @current_account_id IS NOT NULL THEN
            SET v_account_id = @current_account_id;
        END IF;

        IF @app_branch_id IS NOT NULL THEN
            SET v_branch_id = @app_branch_id;
        ELSEIF @current_branch_id IS NOT NULL THEN
            SET v_branch_id = @current_branch_id;
        END IF;

        INSERT INTO Audit_Log (
            Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value
        ) VALUES (
            v_account_id,
            v_branch_id,
            'Invoice',
            CAST(NEW.Invoice_ID AS CHAR),
            'INSERT',
            NULL,
            JSON_OBJECT(
                'Invoice_ID', NEW.Invoice_ID,
                'Consultation_ID', NEW.Consultation_ID,
                'Invoice_Date', NEW.Invoice_Date,
                'Billed_Consultation_Fee', NEW.Billed_Consultation_Fee,
                'Invoice_Status', NEW.Invoice_Status
            )
        );
    END IF;
END$$

DROP TRIGGER IF EXISTS trg_after_invoice_update$$

CREATE TRIGGER trg_after_invoice_update
AFTER UPDATE ON Invoice
FOR EACH ROW
BEGIN
    DECLARE v_account_id INT DEFAULT 1;
    DECLARE v_branch_id INT DEFAULT NULL;

    IF @audit_bypass IS NULL OR @audit_bypass != 1 THEN
        IF @app_account_id IS NOT NULL THEN
            SET v_account_id = @app_account_id;
        ELSEIF @current_account_id IS NOT NULL THEN
            SET v_account_id = @current_account_id;
        END IF;

        IF @app_branch_id IS NOT NULL THEN
            SET v_branch_id = @app_branch_id;
        ELSEIF @current_branch_id IS NOT NULL THEN
            SET v_branch_id = @current_branch_id;
        END IF;

        INSERT INTO Audit_Log (
            Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value
        ) VALUES (
            v_account_id,
            v_branch_id,
            'Invoice',
            CAST(NEW.Invoice_ID AS CHAR),
            'UPDATE',
            JSON_OBJECT(
                'Invoice_ID', OLD.Invoice_ID,
                'Consultation_ID', OLD.Consultation_ID,
                'Invoice_Date', OLD.Invoice_Date,
                'Billed_Consultation_Fee', OLD.Billed_Consultation_Fee,
                'Invoice_Status', OLD.Invoice_Status
            ),
            JSON_OBJECT(
                'Invoice_ID', NEW.Invoice_ID,
                'Consultation_ID', NEW.Consultation_ID,
                'Invoice_Date', NEW.Invoice_Date,
                'Billed_Consultation_Fee', NEW.Billed_Consultation_Fee,
                'Invoice_Status', NEW.Invoice_Status
            )
        );
    END IF;
END$$

-- --------------------------------------------------------
-- Payment Triggers
-- --------------------------------------------------------

DROP TRIGGER IF EXISTS trg_after_payment_insert$$

CREATE TRIGGER trg_after_payment_insert
AFTER INSERT ON Payment
FOR EACH ROW
BEGIN
    DECLARE v_account_id INT DEFAULT 1;
    DECLARE v_branch_id INT DEFAULT NULL;

    IF @audit_bypass IS NULL OR @audit_bypass != 1 THEN
        IF @app_account_id IS NOT NULL THEN
            SET v_account_id = @app_account_id;
        ELSEIF @current_account_id IS NOT NULL THEN
            SET v_account_id = @current_account_id;
        END IF;

        IF @app_branch_id IS NOT NULL THEN
            SET v_branch_id = @app_branch_id;
        ELSEIF @current_branch_id IS NOT NULL THEN
            SET v_branch_id = @current_branch_id;
        END IF;

        INSERT INTO Audit_Log (
            Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value
        ) VALUES (
            v_account_id,
            v_branch_id,
            'Payment',
            CAST(NEW.Payment_ID AS CHAR),
            'INSERT',
            NULL,
            JSON_OBJECT(
                'Payment_ID', NEW.Payment_ID,
                'Invoice_ID', NEW.Invoice_ID,
                'Payment_Date', NEW.Payment_Date,
                'Amount', NEW.Amount,
                'Payment_Method', NEW.Payment_Method,
                'Payment_Status', NEW.Payment_Status
            )
        );
    END IF;
END$$

-- --------------------------------------------------------
-- Insurance Claim Triggers
-- --------------------------------------------------------

DROP TRIGGER IF EXISTS trg_after_claim_insert$$

CREATE TRIGGER trg_after_claim_insert
AFTER INSERT ON Insurance_Claim
FOR EACH ROW
BEGIN
    DECLARE v_account_id INT DEFAULT 1;
    DECLARE v_branch_id INT DEFAULT NULL;

    IF @audit_bypass IS NULL OR @audit_bypass != 1 THEN
        IF @app_account_id IS NOT NULL THEN
            SET v_account_id = @app_account_id;
        ELSEIF @current_account_id IS NOT NULL THEN
            SET v_account_id = @current_account_id;
        END IF;

        IF @app_branch_id IS NOT NULL THEN
            SET v_branch_id = @app_branch_id;
        ELSEIF @current_branch_id IS NOT NULL THEN
            SET v_branch_id = @current_branch_id;
        END IF;

        INSERT INTO Audit_Log (
            Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value
        ) VALUES (
            v_account_id,
            v_branch_id,
            'Insurance_Claim',
            CAST(NEW.Claim_ID AS CHAR),
            'INSERT',
            NULL,
            JSON_OBJECT(
                'Claim_ID', NEW.Claim_ID,
                'Invoice_ID', NEW.Invoice_ID,
                'Policy_ID', NEW.Policy_ID,
                'Claim_Date', NEW.Claim_Date,
                'Claimed_Amount', NEW.Claimed_Amount,
                'Approved_Amount', NEW.Approved_Amount,
                'Claim_Status', NEW.Claim_Status,
                'Settlement_Date', NEW.Settlement_Date
            )
        );
    END IF;
END$$

DROP TRIGGER IF EXISTS trg_after_claim_update$$

CREATE TRIGGER trg_after_claim_update
AFTER UPDATE ON Insurance_Claim
FOR EACH ROW
BEGIN
    DECLARE v_account_id INT DEFAULT 1;
    DECLARE v_branch_id INT DEFAULT NULL;

    IF @audit_bypass IS NULL OR @audit_bypass != 1 THEN
        IF @app_account_id IS NOT NULL THEN
            SET v_account_id = @app_account_id;
        ELSEIF @current_account_id IS NOT NULL THEN
            SET v_account_id = @current_account_id;
        END IF;

        IF @app_branch_id IS NOT NULL THEN
            SET v_branch_id = @app_branch_id;
        ELSEIF @current_branch_id IS NOT NULL THEN
            SET v_branch_id = @current_branch_id;
        END IF;

        INSERT INTO Audit_Log (
            Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value
        ) VALUES (
            v_account_id,
            v_branch_id,
            'Insurance_Claim',
            CAST(NEW.Claim_ID AS CHAR),
            'UPDATE',
            JSON_OBJECT(
                'Claim_ID', OLD.Claim_ID,
                'Invoice_ID', OLD.Invoice_ID,
                'Policy_ID', OLD.Policy_ID,
                'Claim_Date', OLD.Claim_Date,
                'Claimed_Amount', OLD.Claimed_Amount,
                'Approved_Amount', OLD.Approved_Amount,
                'Claim_Status', OLD.Claim_Status,
                'Settlement_Date', OLD.Settlement_Date
            ),
            JSON_OBJECT(
                'Claim_ID', NEW.Claim_ID,
                'Invoice_ID', NEW.Invoice_ID,
                'Policy_ID', NEW.Policy_ID,
                'Claim_Date', NEW.Claim_Date,
                'Claimed_Amount', NEW.Claimed_Amount,
                'Approved_Amount', NEW.Approved_Amount,
                'Claim_Status', NEW.Claim_Status,
                'Settlement_Date', NEW.Settlement_Date
            )
        );
    END IF;
END$$

DELIMITER ;
