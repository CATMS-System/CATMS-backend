import pymysql


class PaymentRepository:

    def __init__(self, db: pymysql.Connection):
        self.db = db

    def create(
        self,
        invoice_id: int,
        amount,
        payment_method: str,
        transaction_reference: str,
        payment_status: str = "Completed"
    ):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO Payment
                    (
                        Invoice_ID,
                        Amount,
                        Payment_Method,
                        Payment_Status,
                        Transaction_Reference
                    )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    invoice_id,
                    amount,
                    payment_method,
                    payment_status,
                    transaction_reference
                )
            )

            payment_id = cursor.lastrowid

        return self.get_by_id(payment_id)

    def get_by_id(self, payment_id: int):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM Payment
                WHERE Payment_ID = %s
                """,
                (payment_id,)
            )

            return cursor.fetchone()

    def get_completed_for_invoice(self, invoice_id: int):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM Payment
                WHERE Invoice_ID = %s
                  AND Payment_Status = 'Completed'
                """,
                (invoice_id,)
            )

            return cursor.fetchall()

    def get_total_completed_for_invoice(self, invoice_id: int):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(Amount), 0) AS Total_Paid
                FROM Payment
                WHERE Invoice_ID = %s
                  AND Payment_Status = 'Completed'
                """,
                (invoice_id,)
            )

            result = cursor.fetchone()

        return result["Total_Paid"]