import sqlite3


def test_backup_db_copies_data(tmp_path, monkeypatch):
    from app.config import settings
    from app import backup
    monkeypatch.setattr(settings, "myhub_data_dir", tmp_path)

    src = sqlite3.connect(settings.db_path)
    src.execute("CREATE TABLE t (id INTEGER)")
    src.execute("INSERT INTO t VALUES (1)")
    src.commit()
    src.close()

    result = backup.backup_db()
    assert result == tmp_path / "myhub_backup.db"
    assert result.is_file()

    check = sqlite3.connect(result)
    assert check.execute("SELECT id FROM t").fetchone() == (1,)
    check.close()


def test_backup_db_missing_source_returns_none(tmp_path, monkeypatch):
    from app.config import settings
    from app import backup
    monkeypatch.setattr(settings, "myhub_data_dir", tmp_path)

    assert backup.backup_db() is None
