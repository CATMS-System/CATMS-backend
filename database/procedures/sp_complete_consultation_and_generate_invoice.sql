-- ==============================================================================
-- Stored Procedure: sp_complete_consultation_and_generate_invoice
-- Description:
--   Marks the appointment associated with a consultation as 'Completed',
--   retrieves the attending doctor's Standard_Consultation_Fee, and generates
--   an 'Issued' invoice for the consultation.
--
--   Designed to participate in the caller's active database transaction.
--   Does not commit or rollback internally.
--
-- Parameters:
--   IN  p_consultation_id INT: ID of the newly created Consultation.
--   OUT p_invoice_id      INT: Generated Invoice_ID from the Invoice table.
-- ==============================================================================

DROP PROCEDURE IF EXISTS sp_complete_consultation_and_generate_invoice;

DELIMITER //

CREATE PROCEDURE sp_complete_consultation_and_generate_invoice(
    IN p_consultation_id INT,
    OUT p_invoice_id INT
)
BEGIN
    DECLARE v_appointment_id INT;
    DECLARE v_doctor_id INT;
    DECLARE v_consultation_fee DECIMAL(10, 2);

    -- 1. Identify associated Appointment_ID from Consultation
    SELECT Appointment_ID
    INTO v_appointment_id
    FROM Consultation
    WHERE Consultation_ID = p_consultation_id;

    IF v_appointment_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Consultation not found.';
    END IF;

    -- 2. Mark Appointment as Completed
    UPDATE Appointment
    SET Status = 'Completed'
    WHERE Appointment_ID = v_appointment_id;

    -- 3. Retrieve attending doctor's Standard_Consultation_Fee
    SELECT a.Doctor_ID, d.Standard_Consultation_Fee
    INTO v_doctor_id, v_consultation_fee
    FROM Appointment a
    JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
    WHERE a.Appointment_ID = v_appointment_id;

    IF v_consultation_fee IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Doctor or Standard Consultation Fee not found for appointment.';
    END IF;

    -- 4. Create Invoice for the consultation
    INSERT INTO Invoice (
        Consultation_ID,
        Invoice_Date,
        Billed_Consultation_Fee,
        Invoice_Status
    ) VALUES (
        p_consultation_id,
        CURRENT_DATE,
        v_consultation_fee,
        'Issued'
    );

    SET p_invoice_id = LAST_INSERT_ID();
END //

DELIMITER ;
