-- Procedure: sp_expire_policies
-- Domain: Patients, Emergency Contacts & Insurance
-- Marks every Active policy whose End_Date has passed as Expired.
-- Policy_Status is not changed automatically by MySQL, so this is run on demand (CALL sp_expire_policies(@n); SELECT @n;) or from a scheduler.
-- Returns the number of policies changed in p_expired_count
DELIMITER $$

DROP PROCEDURE IF EXISTS sp_expire_policies$$

CREATE PROCEDURE sp_expire_policies(OUT p_expired_count INT)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    UPDATE Insurance_Policy
    SET Policy_Status = 'Expired'
    WHERE Policy_Status = 'Active'
      AND End_Date < CURDATE();

    SET p_expired_count = ROW_COUNT();

    COMMIT;
END$$

DELIMITER ;
