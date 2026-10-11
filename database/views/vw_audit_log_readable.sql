-- ========================================================
-- View: vw_audit_log_readable
-- Domain: Auth, Security, Admin & Branches (Member 1)
-- Formats Audit_Log with usernames and branch names
-- ========================================================

CREATE OR REPLACE VIEW vw_audit_log_readable AS
SELECT 
    a.Audit_ID,
    a.Timestamp,
    a.Account_ID,
    u.Username AS Performed_By,
    a.Branch_ID,
    b.Branch_Name AS Affected_Branch,
    a.Table_Name,
    a.Record_ID,
    a.Action_Type,
    a.Old_Value,
    a.New_Value
FROM Audit_Log a
LEFT JOIN User_Account u ON a.Account_ID = u.Account_ID
LEFT JOIN Branch b ON a.Branch_ID = b.Branch_ID;
