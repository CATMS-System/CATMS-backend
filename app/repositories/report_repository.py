import pymysql


class ReportRepository:

    def __init__(self, db: pymysql.Connection):
        self.db = db

    def get_branch_daily_summary(
        self,
        report_date,
        branch_id=None
    ):
        sql = """
            SELECT
                b.Branch_ID,
                b.Branch_Name,
                a.Appointment_Date,

                COUNT(a.Appointment_ID) AS Total_Appointments,

                SUM(
                    CASE
                        WHEN a.Status = 'Completed' THEN 1
                        ELSE 0
                    END
                ) AS Completed_Appointments,

                SUM(
                    CASE
                        WHEN a.Status = 'Cancelled' THEN 1
                        ELSE 0
                    END
                ) AS Cancelled_Appointments,

                SUM(
                    CASE
                        WHEN a.Status = 'No_Show' THEN 1
                        ELSE 0
                    END
                ) AS No_Show_Appointments

            FROM Appointment a

            JOIN Branch b
                ON a.Branch_ID = b.Branch_ID

            WHERE a.Appointment_Date = %s
        """

        parameters = [report_date]

        if branch_id is not None:
            sql += """
                AND b.Branch_ID = %s
            """
            parameters.append(branch_id)

        sql += """
            GROUP BY
                b.Branch_ID,
                b.Branch_Name,
                a.Appointment_Date

            ORDER BY b.Branch_ID
        """

        with self.db.cursor() as cursor:
            cursor.execute(sql, tuple(parameters))
            return cursor.fetchall()

    def get_doctor_revenue(
        self,
        start_date,
        end_date,
        branch_id=None
    ):
        sql = """
            SELECT
                d.Doctor_ID,
                CONCAT(s.First_Name, ' ', s.Last_Name) AS Doctor_Name,
                b.Branch_ID,
                b.Branch_Name,

                COUNT(i.Invoice_ID) AS Total_Invoices,

                COALESCE(
                    SUM(
                        i.Billed_Consultation_Fee
                        + COALESCE(t.Treatment_Total, 0)
                    ),
                    0
                ) AS Gross_Revenue,

                COALESCE(
                    SUM(COALESCE(p.Total_Paid, 0)),
                    0
                ) AS Collected_Revenue

            FROM Invoice i

            JOIN Consultation c
                ON i.Consultation_ID = c.Consultation_ID

            JOIN Appointment a
                ON c.Appointment_ID = a.Appointment_ID

            JOIN Doctor d
                ON a.Doctor_ID = d.Doctor_ID

            JOIN Staff s
                ON d.Doctor_ID = s.Staff_ID

            JOIN Branch b
                ON a.Branch_ID = b.Branch_ID

            LEFT JOIN (
                SELECT
                    Consultation_ID,
                    SUM(
                        Quantity * Billed_Unit_Price
                    ) AS Treatment_Total
                FROM Prescribed_Treatment
                GROUP BY Consultation_ID
            ) t
                ON c.Consultation_ID = t.Consultation_ID

            LEFT JOIN (
                SELECT
                    Invoice_ID,
                    SUM(Amount) AS Total_Paid
                FROM Payment
                WHERE Payment_Status = 'Completed'
                GROUP BY Invoice_ID
            ) p
                ON i.Invoice_ID = p.Invoice_ID

            WHERE i.Invoice_Date BETWEEN %s AND %s
        """

        parameters = [start_date, end_date]

        if branch_id is not None:
            sql += """
                AND b.Branch_ID = %s
            """
            parameters.append(branch_id)

        sql += """
            GROUP BY
                d.Doctor_ID,
                s.First_Name,
                s.Last_Name,
                b.Branch_ID,
                b.Branch_Name

            ORDER BY d.Doctor_ID
        """

        with self.db.cursor() as cursor:
            cursor.execute(sql, tuple(parameters))
            return cursor.fetchall()

    def get_outstanding_balances(
        self,
        branch_id=None
    ):
        sql = """
            SELECT
                pat.Patient_ID,
                CONCAT(
                    pat.First_Name,
                    ' ',
                    pat.Last_Name
                ) AS Patient_Name,

                b.Branch_ID,
                b.Branch_Name,

                COUNT(i.Invoice_ID) AS Total_Invoices,

                COALESCE(
                    SUM(
                        i.Billed_Consultation_Fee
                        + COALESCE(t.Treatment_Total, 0)
                    ),
                    0
                ) AS Total_Billed,

                COALESCE(
                    SUM(COALESCE(p.Total_Paid, 0)),
                    0
                ) AS Total_Paid,

                COALESCE(
                    SUM(COALESCE(ic.Insurance_Covered, 0)),
                    0
                ) AS Insurance_Covered,

                COALESCE(
                    SUM(
                        (
                            i.Billed_Consultation_Fee
                            + COALESCE(t.Treatment_Total, 0)
                        )
                        - COALESCE(p.Total_Paid, 0)
                        - COALESCE(ic.Insurance_Covered, 0)
                    ),
                    0
                ) AS Outstanding_Balance

            FROM Invoice i

            JOIN Consultation c
                ON i.Consultation_ID = c.Consultation_ID

            JOIN Appointment a
                ON c.Appointment_ID = a.Appointment_ID

            JOIN Patient pat
                ON a.Patient_ID = pat.Patient_ID

            JOIN Branch b
                ON a.Branch_ID = b.Branch_ID

            LEFT JOIN (
                SELECT
                    Consultation_ID,
                    SUM(
                        Quantity * Billed_Unit_Price
                    ) AS Treatment_Total
                FROM Prescribed_Treatment
                GROUP BY Consultation_ID
            ) t
                ON c.Consultation_ID = t.Consultation_ID

            LEFT JOIN (
                SELECT
                    Invoice_ID,
                    SUM(Amount) AS Total_Paid
                FROM Payment
                WHERE Payment_Status = 'Completed'
                GROUP BY Invoice_ID
            ) p
                ON i.Invoice_ID = p.Invoice_ID

            LEFT JOIN (
                SELECT
                    Invoice_ID,
                    SUM(Approved_Amount) AS Insurance_Covered
                FROM Insurance_Claim
                WHERE Claim_Status IN ('Approved', 'Settled')
                GROUP BY Invoice_ID
            ) ic
                ON i.Invoice_ID = ic.Invoice_ID

            WHERE i.Invoice_Status != 'Cancelled'
        """

        parameters = []

        if branch_id is not None:
            sql += """
                AND b.Branch_ID = %s
            """
            parameters.append(branch_id)

        sql += """
            GROUP BY
                pat.Patient_ID,
                pat.First_Name,
                pat.Last_Name,
                b.Branch_ID,
                b.Branch_Name

            HAVING Outstanding_Balance > 0

            ORDER BY Outstanding_Balance DESC
        """

        with self.db.cursor() as cursor:
            cursor.execute(sql, tuple(parameters))
            return cursor.fetchall()

    def get_treatment_usage(
        self,
        start_date,
        end_date,
        branch_id=None
    ):
        sql = """
            SELECT
                tc.Category_ID,
                tc.Category_Name,

                SUM(pt.Quantity) AS Total_Quantity,

                COUNT(DISTINCT pt.Consultation_ID)
                    AS Consultations_Using_Treatment,

                COALESCE(
                    SUM(
                        pt.Quantity * pt.Billed_Unit_Price
                    ),
                    0
                ) AS Treatment_Revenue

            FROM Prescribed_Treatment pt

            JOIN Treatment_Catalogue t
                ON pt.Treatment_ID = t.Treatment_ID

            JOIN Treatment_Category tc
                ON t.Category_ID = tc.Category_ID

            JOIN Consultation c
                ON pt.Consultation_ID = c.Consultation_ID

            JOIN Appointment a
                ON c.Appointment_ID = a.Appointment_ID

            WHERE c.Consultation_Date BETWEEN %s AND %s
        """

        parameters = [start_date, end_date]

        if branch_id is not None:
            sql += """
                AND a.Branch_ID = %s
            """
            parameters.append(branch_id)

        sql += """
            GROUP BY
                tc.Category_ID,
                tc.Category_Name

            ORDER BY Treatment_Revenue DESC
        """

        with self.db.cursor() as cursor:
            cursor.execute(sql, tuple(parameters))
            return cursor.fetchall()

    def get_insurance_vs_out_of_pocket(
        self,
        start_date,
        end_date,
        branch_id=None
    ):
        sql = """
            SELECT
                b.Branch_ID,
                b.Branch_Name,

                COUNT(i.Invoice_ID) AS Total_Invoices,

                COALESCE(
                    SUM(
                        i.Billed_Consultation_Fee
                        + COALESCE(t.Treatment_Total, 0)
                    ),
                    0
                ) AS Total_Billed,

                COALESCE(
                    SUM(COALESCE(ic.Insurance_Covered, 0)),
                    0
                ) AS Insurance_Covered,

                COALESCE(
                    SUM(COALESCE(p.Total_Paid, 0)),
                    0
                ) AS Out_Of_Pocket,

                COALESCE(
                    SUM(
                        (
                            i.Billed_Consultation_Fee
                            + COALESCE(t.Treatment_Total, 0)
                        )
                        - COALESCE(ic.Insurance_Covered, 0)
                        - COALESCE(p.Total_Paid, 0)
                    ),
                    0
                ) AS Outstanding_Balance

            FROM Invoice i

            JOIN Consultation c
                ON i.Consultation_ID = c.Consultation_ID

            JOIN Appointment a
                ON c.Appointment_ID = a.Appointment_ID

            JOIN Branch b
                ON a.Branch_ID = b.Branch_ID

            LEFT JOIN (
                SELECT
                    Consultation_ID,
                    SUM(
                        Quantity * Billed_Unit_Price
                    ) AS Treatment_Total
                FROM Prescribed_Treatment
                GROUP BY Consultation_ID
            ) t
                ON c.Consultation_ID = t.Consultation_ID

            LEFT JOIN (
                SELECT
                    Invoice_ID,
                    SUM(Approved_Amount) AS Insurance_Covered
                FROM Insurance_Claim
                WHERE Claim_Status IN ('Approved', 'Settled')
                GROUP BY Invoice_ID
            ) ic
                ON i.Invoice_ID = ic.Invoice_ID

            LEFT JOIN (
                SELECT
                    Invoice_ID,
                    SUM(Amount) AS Total_Paid
                FROM Payment
                WHERE Payment_Status = 'Completed'
                GROUP BY Invoice_ID
            ) p
                ON i.Invoice_ID = p.Invoice_ID

            WHERE i.Invoice_Date BETWEEN %s AND %s
              AND i.Invoice_Status != 'Cancelled'
        """

        parameters = [start_date, end_date]

        if branch_id is not None:
            sql += """
                AND b.Branch_ID = %s
            """
            parameters.append(branch_id)

        sql += """
            GROUP BY
                b.Branch_ID,
                b.Branch_Name

            ORDER BY b.Branch_ID
        """

        with self.db.cursor() as cursor:
            cursor.execute(sql, tuple(parameters))
            return cursor.fetchall()