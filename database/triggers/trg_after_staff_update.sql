-- ========================================================
-- Trigger: trg_after_staff_update
-- Domain: Auth, Security, Admin & Branches (Member 1)
-- Automatically inserts an audit log when Staff is updated
-- ========================================================

DELIMITER $$

DROP TRIGGER IF EXISTS trg_after_staff_update$$

CREATE TRIGGER trg_after_staff_update
AFTER UPDATE ON Staff
FOR EACH ROW
BEGIN
    DECLARE v_account_id INT DEFAULT 1;
    
    -- Check if session variable is set, otherwise default to 1 (System)
    IF @current_account_id IS NOT NULL THEN
        SET v_account_id = @current_account_id;
    END IF;

    -- Only log meaningful changes like role, branch, or status
    IF OLD.Employment_Status != NEW.Employment_Status 
       OR OLD.Job_Title != NEW.Job_Title 
       OR OLD.Branch_ID != NEW.Branch_ID THEN
       
        INSERT INTO Audit_Log (
            Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value
        ) VALUES (
            v_account_id,
            NEW.Branch_ID,
            'Staff',
            NEW.Staff_ID,
            'UPDATE',
            JSON_OBJECT(
                'Employment_Status', OLD.Employment_Status,
                'Job_Title', OLD.Job_Title,
                'Branch_ID', OLD.Branch_ID
            ),
            JSON_OBJECT(
                'Employment_Status', NEW.Employment_Status,
                'Job_Title', NEW.Job_Title,
                'Branch_ID', NEW.Branch_ID
            )
        );
    END IF;
END$$

DELIMITER ;
