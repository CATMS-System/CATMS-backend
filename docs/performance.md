# Performance tuning
## Indexes (`sql/03_indexes.sql`)
| Index | Used by |
|---|---|
| `idx_appointment_date_branch` on `Appointment(Appointment_Date, Branch_ID)` | branch daily report, today's appointments |
| `idx_invoice_date` on `Invoice(Invoice_Date)` | revenue by day |
| `idx_audit_log_timestamp` on `Audit_Log(Timestamp)` | audit log screen, newest first |
| `idx_appointment_doctor_date` on `Appointment(Doctor_ID, Appointment_Date)` (in the schema) | double-booking check in the overlap trigger |
Measured on MySQL 8.0 after `python sql/run_all.py` and `python sql/seed_demo_data.py` (about 780 appointments, 520 invoices), then `ANALYZE TABLE`.
### Appointments on one day, by branch
```sql
EXPLAIN SELECT Branch_ID, COUNT(*) FROM Appointment WHERE Appointment_Date = '2026-09-14' GROUP BY Branch_ID;
```
| | type | key | rows |
|---|---|---|---|
| Before | index (full index scan) | fk_appt_branch | 783 |
| After | ref, Using index | idx_appointment_date_branch | 23 |
### Invoices on one day
```sql
EXPLAIN SELECT SUM(Billed_Consultation_Fee) FROM Invoice WHERE Invoice_Date = '2026-09-14';
```
| | type | key | rows |
|---|---|---|---|
| Before | ALL (full scan) | none | 519 |
| After | ref | idx_invoice_date | 21 |
For a whole month MySQL still chooses a full scan, because a month is a large share of this small table. The index pays off as the data grows.
### Audit log, newest first
```sql
EXPLAIN SELECT * FROM Audit_Log ORDER BY Timestamp DESC LIMIT 100;
```
With only a few rows MySQL sorts in memory (`Using filesort`). Once the log grows past the page size, the index on `Timestamp` lets it read the newest rows in order without sorting.
## Concurrency
The overlap trigger locks the doctor's row (`SELECT ... FOR UPDATE`) before checking for clashes, so two receptionists booking the same slot at once cannot both succeed.
