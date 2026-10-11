-- ========================================================
-- View: vw_staff_directory
-- Domain: Auth, Security, Admin & Branches (Member 1)
-- Joins Staff, Branch, and User_Account for a complete profile
-- ========================================================

CREATE OR REPLACE VIEW vw_staff_directory AS
SELECT 
    s.Staff_ID,
    s.First_Name,
    s.Last_Name,
    CONCAT(s.First_Name, ' ', s.Last_Name) AS Full_Name,
    s.Job_Title,
    s.Employment_Status,
    s.Contact_Number,
    s.Email,
    s.Branch_ID,
    b.Branch_Name,
    b.City AS Branch_City,
    s.Account_ID,
    u.Username,
    u.System_Role
FROM Staff s
LEFT JOIN Branch b ON s.Branch_ID = b.Branch_ID
LEFT JOIN User_Account u ON s.Account_ID = u.Account_ID;
