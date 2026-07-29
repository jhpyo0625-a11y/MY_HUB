from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def test_spa_serves_real_file_and_falls_back_to_index(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>index</html>")
    (tmp_path / "favicon.svg").write_text("<svg>fav</svg>")
    monkeypatch.setattr(settings, "myhub_static_dir", tmp_path)

    app = create_app()
    client = TestClient(app)

    res = client.get("/favicon.svg")
    assert res.status_code == 200
    assert res.text == "<svg>fav</svg>"

    res = client.get("/somepage")
    assert res.status_code == 200
    assert res.text == "<html>index</html>"
