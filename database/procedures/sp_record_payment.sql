DELIMITER $$

DROP PROCEDURE IF EXISTS sp_record_payment$$

CREATE PROCEDURE sp_record_payment(
    IN p_invoice_id INT,
    IN p_amount DECIMAL(10, 2),
    IN p_payment_method ENUM('Cash', 'Credit_Card', 'Debit_Card', 'Bank_Transfer', 'Online'),
    IN p_transaction_reference VARCHAR(100),
    OUT p_payment_id INT,
    OUT p_remaining_balance DECIMAL(10, 2),
    OUT p_new_invoice_status VARCHAR(20)
)
BEGIN
    DECLARE v_current_balance DECIMAL(10, 2);
    DECLARE v_invoice_status VARCHAR(20);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    -- 1. Validate invoice existence and lock row
    SELECT Invoice_Status
    INTO v_invoice_status
    FROM Invoice
    WHERE Invoice_ID = p_invoice_id
    FOR UPDATE;

    IF v_invoice_status IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invoice does not exist.';
    END IF;

    IF v_invoice_status = 'Cancelled' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot record payment for a cancelled invoice.';
    END IF;

    IF v_invoice_status = 'Paid' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invoice is already fully paid.';
    END IF;

    IF p_amount <= 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Payment amount must be greater than zero.';
    END IF;

    -- 2. Verify payment amount does not exceed remaining dues
    SET v_current_balance =
        fn_calculate_patient_balance(p_invoice_id);

    IF p_amount > v_current_balance THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT =
            'Payment amount exceeds outstanding patient balance.';
    END IF;

    -- 3. Record payment
    INSERT INTO Payment (
        Invoice_ID,
        Payment_Date,
        Amount,
        Payment_Method,
        Payment_Status,
        Transaction_Reference
    ) VALUES (
        p_invoice_id,
        CURRENT_DATE,
        p_amount,
        p_payment_method,
        'Completed',
        p_transaction_reference
    );

    SET p_payment_id = LAST_INSERT_ID();

    -- 4. Recalculate remaining balance
    SET p_remaining_balance =
        fn_calculate_patient_balance(p_invoice_id);

    -- 5. Update invoice status
    IF p_remaining_balance <= 0.00 THEN
        SET p_new_invoice_status = 'Paid';
    ELSE
        SET p_new_invoice_status = 'Partially_Paid';
    END IF;

    UPDATE Invoice
    SET Invoice_Status = p_new_invoice_status
    WHERE Invoice_ID = p_invoice_id;

    COMMIT;
END$$

DELIMITER ;