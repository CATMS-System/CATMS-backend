# patients do not get a login, the client dropped the patient portal


def test_register_patient_creates_no_login(make_patient, db):
    patient = make_patient()
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT Account_ID FROM Patient WHERE Patient_ID = %s",
            (patient["patient_id"],),
        )
        assert cursor.fetchone()["Account_ID"] is None
        cursor.execute(
            "SELECT COUNT(*) AS n FROM User_Account WHERE Username = %s",
            ("pat_" + patient["nic"].lower(),),
        )
        assert cursor.fetchone()["n"] == 0
