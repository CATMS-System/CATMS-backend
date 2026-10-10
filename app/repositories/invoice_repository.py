import pymysql


class InvoiceRepository:

    def __init__(self, db: pymysql.Connection):
        self.db = db

    def get_all(self, patient_id=None, branch_id=None):
        query = """
            SELECT i.Invoice_ID, i.Consultation_ID, i.Invoice_Date,
                   i.Billed_Consultation_Fee, i.Invoice_Status,
                   b.Branch_ID, b.Branch_Name
            FROM vw_Invoice_Summary i
            JOIN Appointment a ON i.Appointment_ID = a.Appointment_ID
            JOIN Branch b ON a.Branch_ID = b.Branch_ID
        """
        conditions = []
        params = []
        if patient_id is not None:
            conditions.append("a.Patient_ID = %s")
            params.append(patient_id)
        if branch_id is not None:
            conditions.append("b.Branch_ID = %s")
            params.append(branch_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY i.Invoice_ID"

        with self.db.cursor() as cursor:
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def get_summary(self, invoice_id: int):
        with self.db.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM vw_Invoice_Summary WHERE Invoice_ID = %s",
                (invoice_id,)
            )
            return cursor.fetchone()

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
