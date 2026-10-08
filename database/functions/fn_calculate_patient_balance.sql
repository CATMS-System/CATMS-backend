DELIMITER $$

DROP FUNCTION IF EXISTS fn_calculate_patient_balance$$

CREATE FUNCTION fn_calculate_patient_balance(p_invoice_id INT)
RETURNS DECIMAL(10, 2)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_consultation_fee DECIMAL(10, 2) DEFAULT 0.00;
    DECLARE v_treatment_total DECIMAL(10, 2) DEFAULT 0.00;
    DECLARE v_insurance_approved DECIMAL(10, 2) DEFAULT 0.00;
    DECLARE v_patient_paid DECIMAL(10, 2) DEFAULT 0.00;
    DECLARE v_balance DECIMAL(10, 2) DEFAULT 0.00;

    -- 1. Consultation fee
    SELECT COALESCE(Billed_Consultation_Fee, 0.00)
    INTO v_consultation_fee
    FROM Invoice
    WHERE Invoice_ID = p_invoice_id;

    -- 2. Prescribed treatments sum
    SELECT COALESCE(SUM(pt.Quantity * pt.Billed_Unit_Price), 0.00)
    INTO v_treatment_total
    FROM Invoice inv
    JOIN Prescribed_Treatment pt
        ON inv.Consultation_ID = pt.Consultation_ID
    WHERE inv.Invoice_ID = p_invoice_id;

    -- 3. Approved / Settled insurance claims
    SELECT COALESCE(SUM(Approved_Amount), 0.00)
    INTO v_insurance_approved
    FROM Insurance_Claim
    WHERE Invoice_ID = p_invoice_id
      AND Claim_Status IN ('Approved', 'Settled');

    -- 4. Completed patient payments
    SELECT COALESCE(SUM(Amount), 0.00)
    INTO v_patient_paid
    FROM Payment
    WHERE Invoice_ID = p_invoice_id
      AND Payment_Status = 'Completed';

    -- 5. Calculate remaining patient balance
    SET v_balance =
        (v_consultation_fee + v_treatment_total)
        - v_insurance_approved
        - v_patient_paid;

    RETURN GREATEST(0.00, v_balance);
END$$

DELIMITER ;