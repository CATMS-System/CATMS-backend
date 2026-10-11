-- ========================================================
-- Procedure: sp_transfer_branch_manager
-- Domain: Auth, Security, Admin & Branches (Member 1)
-- Safely assigns a new Branch Manager and logs the action
-- ========================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_transfer_branch_manager$$

CREATE PROCEDURE sp_transfer_branch_manager(
    IN p_branch_id INT,
    IN p_new_manager_staff_id INT,
    IN p_performed_by_account_id INT
)
BEGIN
    DECLARE v_old_manager_id INT;
    
    -- Get current manager
    SELECT Manager_Staff_ID INTO v_old_manager_id 
    FROM Branch 
    WHERE Branch_ID = p_branch_id;
    
    -- Update branch
    UPDATE Branch 
    SET Manager_Staff_ID = p_new_manager_staff_id
    WHERE Branch_ID = p_branch_id;
    
    -- Log Audit
    INSERT INTO Audit_Log (Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value)
    VALUES (
        p_performed_by_account_id,
        p_branch_id,
        'Branch',
        p_branch_id,
        'UPDATE',
        JSON_OBJECT('Manager_Staff_ID', v_old_manager_id),
        JSON_OBJECT('Manager_Staff_ID', p_new_manager_staff_id)
    );
END$$

DELIMITER ;
