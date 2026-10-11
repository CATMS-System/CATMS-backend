-- ========================================================
-- Triggers: insurance claim rules
-- 1. A new claim cannot be more than the unpaid balance (minus claims
-- still waiting) or more than the policy covers (fn_policy_coverage).
-- 2. A claim cannot be approved for more than the unpaid balance.
-- 3. When a claim is approved or settled, the invoice status is updated.
-- ========================================================
DELIMITER $$
DROP TRIGGER IF EXISTS trg_before_claim_insert$$
CREATE TRIGGER trg_before_claim_insert
BEFORE INSERT ON Insurance_Claim
FOR EACH ROW
BEGIN
 DECLARE v_outstanding DECIMAL(10, 2) DEFAULT 0.00;
 DECLARE v_pending DECIMAL(10, 2) DEFAULT 0.00;
 DECLARE v_policy_used DECIMAL(10, 2) DEFAULT 0.00;
 SELECT Outstanding_Balance
 INTO v_outstanding
 FROM vw_Invoice_Summary
 WHERE Invoice_ID = NEW.Invoice_ID;
 -- claims that are still waiting for a decision
 SELECT COALESCE(SUM(Claimed_Amount), 0.00)
 INTO v_pending
 FROM Insurance_Claim
 WHERE Invoice_ID = NEW.Invoice_ID
 AND Claim_Status IN ('Submitted', 'Under_Review');
 -- what this policy has already approved or has waiting on this invoice
 SELECT COALESCE(SUM(CASE
 WHEN Claim_Status IN ('Approved', 'Settled') THEN Approved_Amount
 WHEN Claim_Status IN ('Submitted', 'Under_Review') THEN Claimed_Amount
 ELSE 0.00
 END), 0.00)
 INTO v_policy_used
 FROM Insurance_Claim
 WHERE Invoice_ID = NEW.Invoice_ID
 AND Policy_ID = NEW.Policy_ID;
 IF NEW.Claimed_Amount > v_outstanding - v_pending THEN
 SIGNAL SQLSTATE '45000'
 SET MESSAGE_TEXT = 'Claimed amount is more than the unpaid balance of this invoice.';
 END IF;
 IF NEW.Claimed_Amount > fn_policy_coverage(NEW.Invoice_ID, NEW.Policy_ID) - v_policy_used THEN
 SIGNAL SQLSTATE '45000'
 SET MESSAGE_TEXT = 'Claimed amount is more than this policy covers for this invoice.';
 END IF;
END$$
DROP TRIGGER IF EXISTS trg_before_claim_update$$
CREATE TRIGGER trg_before_claim_update
BEFORE UPDATE ON Insurance_Claim
FOR EACH ROW
BEGIN
 DECLARE v_outstanding DECIMAL(10, 2) DEFAULT 0.00;
 IF NEW.Claim_Status = 'Approved' AND OLD.Claim_Status <> 'Approved' THEN
 SELECT Outstanding_Balance
 INTO v_outstanding
 FROM vw_Invoice_Summary
 WHERE Invoice_ID = NEW.Invoice_ID;
 IF NEW.Approved_Amount > v_outstanding THEN
 SIGNAL SQLSTATE '45000'
 SET MESSAGE_TEXT = 'Approved amount is more than the unpaid balance of this invoice.';
 END IF;
 END IF;
END$$
DROP TRIGGER IF EXISTS trg_after_claim_invoice_status$$
CREATE TRIGGER trg_after_claim_invoice_status
AFTER UPDATE ON Insurance_Claim
FOR EACH ROW
BEGIN
 DECLARE v_outstanding DECIMAL(10, 2) DEFAULT 0.00;
 DECLARE v_received DECIMAL(10, 2) DEFAULT 0.00;
 IF NEW.Claim_Status <> OLD.Claim_Status
 AND NEW.Claim_Status IN ('Approved', 'Settled') THEN
 SELECT Outstanding_Balance, Insurance_Covered + Patient_Paid
 INTO v_outstanding, v_received
 FROM vw_Invoice_Summary
 WHERE Invoice_ID = NEW.Invoice_ID;
 UPDATE Invoice
 SET Invoice_Status = CASE
 WHEN v_outstanding <= 0 THEN 'Paid'
 WHEN v_received > 0 THEN 'Partially_Paid'
 ELSE Invoice_Status
 END
 WHERE Invoice_ID = NEW.Invoice_ID
 AND Invoice_Status NOT IN ('Draft', 'Cancelled');
 END IF;
END$$
DELIMITER ;
