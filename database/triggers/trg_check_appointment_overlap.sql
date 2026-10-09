-- ========================================================
-- Trigger: trg_check_appointment_overlap_insert
-- Domain: Clinical Scheduling & Appointments
-- Prevents overlapping appointments for the same doctor
-- Compatible with: MySQL 8.0+ / MariaDB 10.5+
-- ========================================================

DELIMITER $$

DROP TRIGGER IF EXISTS trg_check_appointment_overlap_insert$$

CREATE TRIGGER trg_check_appointment_overlap_insert
BEFORE INSERT ON Appointment
FOR EACH ROW
BEGIN
    DECLARE overlap_count INT DEFAULT 0;
    DECLARE new_end_time TIME;
    DECLARE locked_doc_id INT;

    -- Compute end time for candidate appointment
    SET new_end_time = ADDTIME(NEW.Start_Time, SEC_TO_TIME(NEW.Duration_Minutes * 60));

    -- Only enforce check for active appointment states
    IF NEW.Status IN ('Scheduled', 'Confirmed', 'In_Progress') THEN
        -- Serialize appointments for target doctor to prevent concurrency race conditions
        SELECT Doctor_ID INTO locked_doc_id FROM Doctor WHERE Doctor_ID = NEW.Doctor_ID FOR UPDATE;

        SELECT COUNT(*)
        INTO overlap_count
        FROM Appointment
        WHERE Doctor_ID = NEW.Doctor_ID
          AND Appointment_Date = NEW.Appointment_Date
          AND Status IN ('Scheduled', 'Confirmed', 'In_Progress', 'Completed')
          AND (
              (NEW.Start_Time < ADDTIME(Start_Time, SEC_TO_TIME(Duration_Minutes * 60))) AND
              (new_end_time > Start_Time)
          );

        IF overlap_count > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Doctor already has an overlapping appointment in this time slot';
        END IF;
    END IF;
END$$

-- ========================================================
-- Trigger: trg_check_appointment_overlap_update
-- Prevents overlapping appointments during rescheduling
-- ========================================================

DROP TRIGGER IF EXISTS trg_check_appointment_overlap_update$$

CREATE TRIGGER trg_check_appointment_overlap_update
BEFORE UPDATE ON Appointment
FOR EACH ROW
BEGIN
    DECLARE overlap_count INT DEFAULT 0;
    DECLARE new_end_time TIME;
    DECLARE locked_doc_id INT;

    -- Compute updated end time
    SET new_end_time = ADDTIME(NEW.Start_Time, SEC_TO_TIME(NEW.Duration_Minutes * 60));

    -- Only enforce check for active appointment states
    IF NEW.Status IN ('Scheduled', 'Confirmed', 'In_Progress') THEN
        -- Serialize appointments for target doctor to prevent concurrency race conditions
        SELECT Doctor_ID INTO locked_doc_id FROM Doctor WHERE Doctor_ID = NEW.Doctor_ID FOR UPDATE;

        SELECT COUNT(*)
        INTO overlap_count
        FROM Appointment
        WHERE Doctor_ID = NEW.Doctor_ID
          AND Appointment_Date = NEW.Appointment_Date
          AND Appointment_ID != NEW.Appointment_ID
          AND Status IN ('Scheduled', 'Confirmed', 'In_Progress', 'Completed')
          AND (
              (NEW.Start_Time < ADDTIME(Start_Time, SEC_TO_TIME(Duration_Minutes * 60))) AND
              (new_end_time > Start_Time)
          );

        IF overlap_count > 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Doctor already has an overlapping appointment in this time slot';
        END IF;
    END IF;
END$$

DELIMITER ;
