CREATE OR REPLACE VIEW vw_Invoice_Summary AS
SELECT 
    inv.Invoice_ID,
    inv.Consultation_ID,
    c.Appointment_ID,
    a.Patient_ID,
    CONCAT(p.First_Name, ' ', p.Last_Name) AS Patient_Name,
    p.Contact_Number AS Patient_Phone,
    a.Doctor_ID,
    CONCAT(s.First_Name, ' ', s.Last_Name) AS Doctor_Name,
    inv.Invoice_Date,
    inv.Billed_Consultation_Fee,
    COALESCE(treatments.Total_Treatments, 0.00) AS Total_Treatments_Fee,
    (inv.Billed_Consultation_Fee + COALESCE(treatments.Total_Treatments, 0.00)) AS Invoice_Total,
    COALESCE(claims.Approved_Claims, 0.00) AS Insurance_Covered,
    COALESCE(payments.Total_Paid, 0.00) AS Patient_Paid,
    ((inv.Billed_Consultation_Fee + COALESCE(treatments.Total_Treatments, 0.00))
     - COALESCE(claims.Approved_Claims, 0.00)
     - COALESCE(payments.Total_Paid, 0.00)) AS Outstanding_Balance,
    inv.Invoice_Status
FROM Invoice inv
JOIN Consultation c ON inv.Consultation_ID = c.Consultation_ID
JOIN Appointment a ON c.Appointment_ID = a.Appointment_ID
JOIN Patient p ON a.Patient_ID = p.Patient_ID
JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
JOIN Staff s ON d.Doctor_ID = s.Staff_ID
LEFT JOIN (
    SELECT Consultation_ID, SUM(Quantity * Billed_Unit_Price) AS Total_Treatments
    FROM Prescribed_Treatment
    GROUP BY Consultation_ID
) treatments ON inv.Consultation_ID = treatments.Consultation_ID
LEFT JOIN (
    SELECT Invoice_ID, SUM(Approved_Amount) AS Approved_Claims
    FROM Insurance_Claim
    WHERE Claim_Status IN ('Approved', 'Settled')
    GROUP BY Invoice_ID
) claims ON inv.Invoice_ID = claims.Invoice_ID
LEFT JOIN (
    SELECT Invoice_ID, SUM(Amount) AS Total_Paid
    FROM Payment
    WHERE Payment_Status = 'Completed'
    GROUP BY Invoice_ID
) payments ON inv.Invoice_ID = payments.Invoice_ID;