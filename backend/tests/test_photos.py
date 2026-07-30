import io
import json


def _fake_client(payload):
    class FakeMsg:
        content = json.dumps(payload)
    class FakeChoice:
        message = FakeMsg()
    class FakeCompletion:
        choices = [FakeChoice()]
    class FakeCompletions:
        def create(self, **kw):
            return FakeCompletion()
    class FakeChat:
        completions = FakeCompletions()
    class FakeClient:
        def __init__(self, **kw): self.chat = FakeChat()
    return FakeClient


def test_extract_supplement_label(auth_client, monkeypatch, tmp_path):
    from app import photo_extraction
    from app.config import settings
    monkeypatch.setattr(settings, "myhub_data_dir", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    payload = {"brand": "나우푸드", "product_name": "오메가3", "serving_size": "1캡슐",
               "ingredients": [{"ingredient_code": "omega3", "amount": 1000, "unit": "mg"}]}
    monkeypatch.setattr(photo_extraction, "OpenAI", _fake_client(payload))

    res = auth_client.post("/api/photos/extract",
                           data={"kind": "supplement_label"},
                           files={"file": ("label.jpg", io.BytesIO(b"fake-bytes"), "image/jpeg")})
    assert res.status_code == 200
    body = res.json()
    assert body["extracted"]["product_name"] == "오메가3"
    assert body["error"] is None
    assert body["photo_path"].endswith(".jpg")

    photo_res = auth_client.get(f"/api/photos/{body['photo_path']}")
    assert photo_res.status_code == 200
    assert photo_res.content == b"fake-bytes"


def test_extract_unknown_kind_rejected(auth_client):
    res = auth_client.post("/api/photos/extract",
                           data={"kind": "nonsense"},
                           files={"file": ("x.jpg", io.BytesIO(b"x"), "image/jpeg")})
    assert res.status_code == 422


def test_extract_unsupported_mime_rejected(auth_client):
    res = auth_client.post("/api/photos/extract",
                           data={"kind": "meal"},
                           files={"file": ("x.gif", io.BytesIO(b"x"), "image/gif")})
    assert res.status_code == 422


def test_extract_llm_failure_still_saves_photo(auth_client, monkeypatch, tmp_path, caplog):
    from app import photo_extraction
    from app.config import settings
    monkeypatch.setattr(settings, "myhub_data_dir", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class BoomClient:
        def __init__(self, **kw):
            class C:
                def create(self, **kw): raise RuntimeError("vision API down")
            class Ch:
                completions = C()
            self.chat = Ch()
    monkeypatch.setattr(photo_extraction, "OpenAI", BoomClient)

    with caplog.at_level("WARNING"):
        res = auth_client.post("/api/photos/extract",
                               data={"kind": "meal"},
                               files={"file": ("m.jpg", io.BytesIO(b"data"), "image/jpeg")})
    assert res.status_code == 200
    body = res.json()
    assert body["extracted"] is None
    assert "vision API down" in body["error"]
    assert body["photo_path"]
    assert "photo extraction failed" in caplog.text


def test_photo_not_found(auth_client):
    assert auth_client.get("/api/photos/does-not-exist.jpg").status_code == 404


def test_photos_require_auth(client):
    assert client.get("/api/photos/x.jpg").status_code == 401
