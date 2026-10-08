DELIMITER $$

DROP PROCEDURE IF EXISTS sp_record_payment$$

CREATE PROCEDURE sp_record_payment(
    IN p_invoice_id INT,
    -- Plain decimal text avoids rounding before precision validation executes.
    IN p_amount LONGTEXT,
    IN p_payment_method ENUM('Cash', 'Credit_Card', 'Debit_Card', 'Bank_Transfer', 'Online'),
    IN p_transaction_reference VARCHAR(100),
    OUT p_payment_id INT,
    OUT p_remaining_balance DECIMAL(10, 2),
    OUT p_new_invoice_status VARCHAR(20)
)
BEGIN
    DECLARE v_current_balance DECIMAL(10, 2);
    DECLARE v_invoice_status VARCHAR(20);
    DECLARE v_error_message VARCHAR(128);
    DECLARE v_amount_text LONGTEXT;
    DECLARE v_amount DECIMAL(10, 2);

    -- The caller owns BEGIN/COMMIT/ROLLBACK. Keep the invoice lock until
    -- the caller has fetched the payment and prepared its response.
    SET v_amount_text = TRIM(p_amount);
    IF p_amount IS NULL OR NOT REGEXP_LIKE(
        v_amount_text, '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$', 'c'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Payment amount must be a valid decimal number.';
    END IF;

    IF LEFT(v_amount_text, 1) = '-' OR NOT REGEXP_LIKE(v_amount_text, '[1-9]', 'c') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Payment amount must be greater than zero.';
    END IF;

    IF INSTR(v_amount_text, '.') > 0 AND REGEXP_LIKE(
        SUBSTRING_INDEX(v_amount_text, '.', -1), '^.{2}.*[1-9]', 'c'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Payment amount must have at most two decimal places.';
    END IF;

    IF LEFT(v_amount_text, 1) = '+' THEN
        SET v_amount_text = SUBSTRING(v_amount_text, 2);
    END IF;
    IF CHAR_LENGTH(TRIM(LEADING '0' FROM SUBSTRING_INDEX(v_amount_text, '.', 1))) > 8 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Payment amount exceeds the database monetary limit.';
    END IF;
    SET v_amount = CAST(v_amount_text AS DECIMAL(10, 2));

    -- 1. Validate invoice existence and lock row
    SELECT Invoice_Status
    INTO v_invoice_status
    FROM Invoice
    WHERE Invoice_ID = p_invoice_id
    FOR UPDATE;

    IF v_invoice_status IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invoice not found.';
    END IF;

    IF v_invoice_status = 'Cancelled' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot make a payment for a cancelled invoice.';
    END IF;

    -- 2. Verify payment amount does not exceed remaining dues
    SET v_current_balance =
        fn_calculate_patient_balance(p_invoice_id);

    IF v_current_balance <= 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'This invoice has already been fully paid.';
    END IF;

    IF v_amount > v_current_balance THEN
        SET v_error_message = CONCAT(
            'Payment exceeds outstanding balance of ', v_current_balance, '.'
        );
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = v_error_message;
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
        v_amount,
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

END$$

DELIMITER ;
