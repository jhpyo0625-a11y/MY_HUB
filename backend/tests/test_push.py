def test_subscribe_and_unsubscribe(auth_client):
    sub = {"endpoint": "https://push.example.com/abc",
           "keys": {"p256dh": "key1", "auth": "key2"}}
    assert auth_client.post("/api/push/subscribe", json={"subscription": sub}).status_code == 200
    assert auth_client.delete("/api/push/subscribe").status_code == 200


def test_vapid_public_key_endpoint(auth_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "vapid_public_key", "test-pub-key")
    res = auth_client.get("/api/push/vapid-public-key")
    assert res.json() == {"key": "test-pub-key"}


def test_push_requires_auth(client):
    assert client.get("/api/push/vapid-public-key").status_code == 401


def test_send_push_success(db_session_factory, monkeypatch):
    from app import push
    db = db_session_factory()
    push.subscribe(db, {"endpoint": "https://x", "keys": {"p256dh": "a", "auth": "b"}})

    calls = {}
    def fake_webpush(**kw):
        calls.update(kw)
    monkeypatch.setattr(push, "webpush", fake_webpush)

    ok = push.send_push(db, {"title": "t", "body": "b"})
    assert ok is True
    assert calls["subscription_info"]["endpoint"] == "https://x"


def test_send_push_no_subscription_returns_false(db_session_factory):
    from app import push
    db = db_session_factory()
    assert push.send_push(db, {"title": "t"}) is False


def test_send_push_gone_clears_subscription(db_session_factory, monkeypatch):
    from app import push
    from pywebpush import WebPushException
    db = db_session_factory()
    push.subscribe(db, {"endpoint": "https://x", "keys": {"p256dh": "a", "auth": "b"}})

    class FakeResponse:
        status_code = 410
    def fake_webpush(**kw):
        raise WebPushException("gone", response=FakeResponse())
    monkeypatch.setattr(push, "webpush", fake_webpush)

    assert push.send_push(db, {"title": "t"}) is False
    assert push.get_subscription(db) is None
