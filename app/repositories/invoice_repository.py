import pymysql


class InvoiceRepository:

    def __init__(self, db: pymysql.Connection):
        self.db = db

    def get_all(self):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM Invoice
                ORDER BY Invoice_ID
                """
            )

            return cursor.fetchall()
        
    def get_by_id(self, invoice_id: int):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM Invoice
                WHERE Invoice_ID = %s
                """,
                (invoice_id,)
            )

            return cursor.fetchone()

    def get_by_consultation_id(self, consultation_id: int):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM Invoice
                WHERE Consultation_ID = %s
                """,
                (consultation_id,)
            )

            return cursor.fetchone()

    def create(
        self,
        consultation_id: int,
        billed_consultation_fee,
        invoice_status: str = "Issued"
    ):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO Invoice
                    (
                        Consultation_ID,
                        Billed_Consultation_Fee,
                        Invoice_Status
                    )
                VALUES (%s, %s, %s)
                """,
                (
                    consultation_id,
                    billed_consultation_fee,
                    invoice_status
                )
            )

            invoice_id = cursor.lastrowid

        self.db.commit()

        return self.get_by_id(invoice_id)

    def update_status(self, invoice_id: int, status: str):
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                UPDATE Invoice
                SET Invoice_Status = %s
                WHERE Invoice_ID = %s
                """,
                (status, invoice_id)
            )

        

        return self.get_by_id(invoice_id)