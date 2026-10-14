-- View: vw_patient_active_policy
-- Domain: Patients, Emergency Contacts & Insurance (Member 2)
-- One row per usable policy: status Active and today between
-- Start_Date and End_Date (the same rule as get_policies(only_active=True)).
-- Joins Patient, Insurance_Policy and Insurance_Provider.
CREATE OR REPLACE VIEW vw_patient_active_policy AS
SELECT
    p.Patient_ID,
    CONCAT(p.First_Name, ' ', p.Last_Name) AS Patient_Name,
    p.NIC,
    ip.Policy_ID,
    ip.Policy_Number,
    ip.Policy_Type,
    pr.Provider_ID,
    pr.Provider_Name,
    ip.Start_Date,
    ip.End_Date,
    DATEDIFF(ip.End_Date, CURDATE()) AS Days_Remaining,
    ip.Default_Coverage_Percentage
FROM Patient p
JOIN Insurance_Policy ip ON ip.Patient_ID = p.Patient_ID
JOIN Insurance_Provider pr ON pr.Provider_ID = ip.Provider_ID
WHERE ip.Policy_Status = 'Active'
  AND ip.Start_Date <= CURDATE()
  AND ip.End_Date >= CURDATE();
