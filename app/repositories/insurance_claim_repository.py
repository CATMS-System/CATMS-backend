import pymysql
from datetime import date


class InsuranceClaimRepository:

    def __init__(self, db: pymysql.Connection):
        self.db = db

    def create(
        self,
        invoice_id: int,
        policy_id: int,
        claimed_amount,
        approved_amount=0.00,
        claim_status: str = "Submitted"
    ):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO Insurance_Claim
                    (
                        Invoice_ID,
                        Policy_ID,
                        Claimed_Amount,
                        Approved_Amount,
                        Claim_Status
                    )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    invoice_id,
                    policy_id,
                    claimed_amount,
                    approved_amount,
                    claim_status
                )
            )

            claim_id = cursor.lastrowid

        

        return self.get_by_id(claim_id)

    def get_by_id(self, claim_id: int):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM Insurance_Claim
                WHERE Claim_ID = %s
                """,
                (claim_id,)
            )

            return cursor.fetchone()

    def update_status(
        self,
        claim_id: int,
        status: str,
        approved_amount=None
    ):
        with self.db.cursor() as cursor:

            if status == "Settled":
                cursor.execute(
                    """
                    UPDATE Insurance_Claim
                    SET Claim_Status = %s,
                        Settlement_Date = %s
                    WHERE Claim_ID = %s
                    """,
                    (status, date.today(), claim_id)
                )

            elif approved_amount is not None:
                cursor.execute(
                    """
                    UPDATE Insurance_Claim
                    SET Claim_Status = %s,
                        Approved_Amount = %s
                    WHERE Claim_ID = %s
                    """,
                    (status, approved_amount, claim_id)
                )

            else:
                cursor.execute(
                    """
                    UPDATE Insurance_Claim
                    SET Claim_Status = %s
                    WHERE Claim_ID = %s
                    """,
                    (status, claim_id)
                )

        

        return self.get_by_id(claim_id)