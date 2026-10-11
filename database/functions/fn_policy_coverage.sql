-- ========================================================
-- Function: fn_policy_coverage
-- How much an insurance policy covers for one invoice:
-- consultation fee x the policy's default percentage
-- + each listed treatment x its covered percentage, capped at its limit
-- Treatments not listed in Treatment_Policy_Eligibility are not covered.
-- ========================================================
DELIMITER $$
DROP FUNCTION IF EXISTS fn_policy_coverage$$
CREATE FUNCTION fn_policy_coverage(p_invoice_id INT, p_policy_id INT)
RETURNS DECIMAL(10, 2)
DETERMINISTIC
READS SQL DATA
BEGIN
 DECLARE v_fee_cover DECIMAL(10, 2) DEFAULT 0.00;
 DECLARE v_treatment_cover DECIMAL(10, 2) DEFAULT 0.00;
 -- 1. Consultation fee at the policy's default percentage
 SELECT COALESCE(inv.Billed_Consultation_Fee * ip.Default_Coverage_Percentage / 100, 0.00)
 INTO v_fee_cover
 FROM Invoice inv
 JOIN Insurance_Policy ip ON ip.Policy_ID = p_policy_id
 WHERE inv.Invoice_ID = p_invoice_id;
 -- 2. Listed treatments, each capped at its coverage limit
 SELECT COALESCE(SUM(LEAST(
 pt.Quantity * pt.Billed_Unit_Price * tpe.Covered_Percentage / 100,
 tpe.Coverage_Limit
 )), 0.00)
 INTO v_treatment_cover
 FROM Invoice inv
 JOIN Prescribed_Treatment pt
 ON pt.Consultation_ID = inv.Consultation_ID
 JOIN Treatment_Policy_Eligibility tpe
 ON tpe.Treatment_ID = pt.Treatment_ID
 AND tpe.Policy_ID = p_policy_id
 WHERE inv.Invoice_ID = p_invoice_id;
 RETURN ROUND(v_fee_cover + v_treatment_cover, 2);
END$$
DELIMITER ;
