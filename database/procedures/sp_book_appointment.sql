-- ========================================================
-- Stored Procedure: sp_book_appointment
-- Domain: Clinical Scheduling & Appointments
-- Atomically books an appointment with ACID transaction safety
-- Compatible with: MySQL 8.0+ / MariaDB 10.5+
-- ========================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_book_appointment$$

CREATE PROCEDURE sp_book_appointment(
    IN p_patient_id INT,
    IN p_doctor_id INT,
    IN p_branch_id INT,
    IN p_schedule_id INT,
    IN p_appointment_date DATE,
    IN p_start_time TIME,
    IN p_duration_minutes INT,
    IN p_appointment_type VARCHAR(20),
    IN p_reason_for_visit VARCHAR(255),
    OUT p_appointment_id INT
)
BEGIN
    DECLARE v_overlap_count INT DEFAULT 0;
    DECLARE v_end_time TIME;
    DECLARE v_patient_exists INT DEFAULT 0;
    DECLARE v_doctor_exists INT DEFAULT 0;
    DECLARE v_branch_exists INT DEFAULT 0;

    -- Error handler to rollback on SQLEXCEPTION
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    -- 1. Input Validation
    IF p_patient_id IS NULL OR p_doctor_id IS NULL OR p_branch_id IS NULL OR p_appointment_date IS NULL OR p_start_time IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Required booking fields (patient_id, doctor_id, branch_id, date, start_time) cannot be null';
    END IF;

    -- Set default duration if not specified
    IF p_duration_minutes IS NULL OR p_duration_minutes <= 0 THEN
        SET p_duration_minutes = 15;
    END IF;

    -- Set default appointment type if not specified
    IF p_appointment_type IS NULL OR p_appointment_type = '' THEN
        SET p_appointment_type = 'Standard';
    END IF;

    -- 2. Verify Patient Exists
    SELECT COUNT(*) INTO v_patient_exists FROM Patient WHERE Patient_ID = p_patient_id;
    IF v_patient_exists = 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Patient record does not exist';
    END IF;

    -- 3. Verify Doctor Exists
    SELECT COUNT(*) INTO v_doctor_exists FROM Doctor WHERE Doctor_ID = p_doctor_id;
    IF v_doctor_exists = 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Doctor record does not exist';
    END IF;

    -- 4. Verify Branch Exists
    SELECT COUNT(*) INTO v_branch_exists FROM Branch WHERE Branch_ID = p_branch_id;
    IF v_branch_exists = 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Branch record does not exist';
    END IF;

    -- Compute candidate end time
    SET v_end_time = ADDTIME(p_start_time, SEC_TO_TIME(p_duration_minutes * 60));

    -- 5. Collision Check (Doctor Slot Overlap)
    SELECT COUNT(*)
    INTO v_overlap_count
    FROM Appointment
    WHERE Doctor_ID = p_doctor_id
      AND Appointment_Date = p_appointment_date
      AND Status IN ('Scheduled', 'Confirmed', 'Completed')
      AND (
          (p_start_time < ADDTIME(Start_Time, SEC_TO_TIME(Duration_Minutes * 60))) AND
          (v_end_time > Start_Time)
      );

    IF v_overlap_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Doctor already has an overlapping appointment in this time slot';
    END IF;

    -- 6. Atomic Transaction Insert
    START TRANSACTION;

    INSERT INTO Appointment (
        Patient_ID,
        Doctor_ID,
        Branch_ID,
        Schedule_ID,
        Appointment_Date,
        Start_Time,
        Duration_Minutes,
        Appointment_Type,
        Status,
        Reason_For_Visit
    ) VALUES (
        p_patient_id,
        p_doctor_id,
        p_branch_id,
        p_schedule_id,
        p_appointment_date,
        p_start_time,
        p_duration_minutes,
        p_appointment_type,
        'Scheduled',
        p_reason_for_visit
    );

    SET p_appointment_id = LAST_INSERT_ID();

    COMMIT;
END$$

DELIMITER ;
