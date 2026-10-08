-- ========================================================
-- Procedure: sp_force_password_reset
-- Domain: Auth, Security, Admin & Branches (Member 1)
-- Resets user password hash and logs a security event
-- ========================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_force_password_reset$$

CREATE PROCEDURE sp_force_password_reset(
    IN p_target_account_id INT,
    IN p_new_password_hash VARCHAR(255),
    IN p_performed_by_account_id INT
)
BEGIN
    -- Update user account password
    UPDATE User_Account
    SET Password_Hash = p_new_password_hash
    WHERE Account_ID = p_target_account_id;
    
    -- Log Audit Security Event
    INSERT INTO Audit_Log (Account_ID, Branch_ID, Table_Name, Record_ID, Action_Type, Old_Value, New_Value)
    VALUES (
        p_performed_by_account_id,
        NULL,
        'User_Account',
        p_target_account_id,
        'UPDATE',
        JSON_OBJECT('Action', 'Password Reset Forced'),
        JSON_OBJECT('Status', 'Success')
    );
END$$

DELIMITER ;
