-- ========================================================
-- Indexes for the busiest lookups that had no usable index
-- Loaded by run_all.py after the schema and seed data.
-- Check with EXPLAIN before and after (see docs/performance.md).
-- ========================================================
-- daily and date-range reports filter appointments by date, then group by branch
CREATE INDEX idx_appointment_date_branch ON Appointment(Appointment_Date, Branch_ID);
-- revenue reports filter invoices by date
CREATE INDEX idx_invoice_date ON Invoice(Invoice_Date);
-- the audit log screen shows the newest entries first
CREATE INDEX idx_audit_log_timestamp ON Audit_Log(Timestamp);
