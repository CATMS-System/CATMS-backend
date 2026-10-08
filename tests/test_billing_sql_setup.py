from pathlib import Path
from unittest.mock import MagicMock

from sql import run_all


def test_billing_only_installs_objects_in_dependency_order(monkeypatch):
    db = MagicMock()
    cursor = db.cursor.return_value.__enter__.return_value
    monkeypatch.setattr(run_all, "get_db_connection", lambda **kwargs: db)

    run_all.run_all(billing_only=True)

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert len(statements) == 5
    assert statements[0].startswith("DROP FUNCTION IF EXISTS")
    assert statements[1].startswith("CREATE FUNCTION fn_calculate_patient_balance")
    assert statements[2].startswith("CREATE OR REPLACE VIEW vw_Invoice_Summary")
    assert statements[3].startswith("DROP PROCEDURE IF EXISTS")
    assert statements[4].startswith("CREATE PROCEDURE sp_record_payment")
    assert not any("DROP TABLE" in stmt or "INSERT INTO" in stmt.split("BEGIN")[0]
                   for stmt in statements)
    db.close.assert_called_once()


def test_full_setup_includes_billing_objects_after_schema_and_seed(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(run_all, "get_db_connection", lambda **kwargs: db)
    seen_files = []
    original = Path.read_text

    def record_file(path, *args, **kwargs):
        seen_files.append(path.name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", record_file)
    run_all.run_all()

    assert seen_files == [
        "01_schema.sql", "02_seed_data.sql", "fn_calculate_patient_balance.sql",
        "vw_Invoice_Summary.sql", "sp_record_payment.sql",
    ]
