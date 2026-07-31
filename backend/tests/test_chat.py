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


def test_chat_roundtrip(auth_client, monkeypatch):
    from app import chat
    monkeypatch.setattr(chat, "OpenAI",
                        _fake_client({"reply": "네, 알려주셔서 감사해요.",
                                     "proposed_entries": []}))
    monkeypatch.setattr(chat.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/chat/messages", json={"content": "안녕하세요"})
    assert res.status_code == 201
    body = res.json()
    assert body["user_message"]["content"] == "안녕하세요"
    assert body["assistant_message"]["content"] == "네, 알려주셔서 감사해요."

    listing = auth_client.get("/api/chat/messages").json()
    assert len(listing) == 2
    assert listing[0]["role"] == "user"
    assert listing[1]["role"] == "assistant"


def test_chat_proposes_metric_save(auth_client, db_session_factory, monkeypatch):
    from app import chat
    from app.seed import seed_metric_definitions
    db = db_session_factory()
    seed_metric_definitions(db)
    db.close()

    monkeypatch.setattr(chat, "OpenAI",
                        _fake_client({"reply": "몸무게 72.5kg으로 저장할까요?",
                                     "proposed_entries": [
                                         {"metric_code": "weight_kg", "value_num": 72.5}]}))
    monkeypatch.setattr(chat.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/chat/messages", json={"content": "몸무게 72.5"})
    proposed = res.json()["assistant_message"]["proposed_entries"]
    assert proposed == [{"metric_code": "weight_kg", "value_num": 72.5, "value_text": None}]


def test_chat_drops_unknown_metric_code(auth_client, monkeypatch):
    from app import chat
    monkeypatch.setattr(chat, "OpenAI",
                        _fake_client({"reply": "저장할게요",
                                     "proposed_entries": [
                                         {"metric_code": "not_real", "value_num": 1}]}))
    monkeypatch.setattr(chat.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/chat/messages", json={"content": "hi"})
    assert res.json()["assistant_message"]["proposed_entries"] == []


def test_chat_llm_failure_returns_friendly_message(auth_client, monkeypatch):
    from app import chat
    class BoomClient:
        def __init__(self, **kw):
            class C:
                def create(self, **kw): raise RuntimeError("down")
            class Ch: completions = C()
            self.chat = Ch()
    monkeypatch.setattr(chat, "OpenAI", BoomClient)
    monkeypatch.setattr(chat.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/chat/messages", json={"content": "hi"})
    assert res.status_code == 201
    assert "죄송" in res.json()["assistant_message"]["content"]


def test_chat_requires_auth(client):
    assert client.get("/api/chat/messages").status_code == 401
