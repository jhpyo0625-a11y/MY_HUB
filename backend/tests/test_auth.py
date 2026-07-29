def test_login_wrong_password(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "myhub_password", "changeme")
    res = client.post("/api/auth/login", json={"password": "nope"})
    assert res.status_code == 401


def test_login_and_me(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "myhub_password", "changeme")
    assert client.get("/api/auth/me").status_code == 401
    res = client.post("/api/auth/login", json={"password": "changeme"})
    assert res.status_code == 200
    assert "myhub_session" in client.cookies
    assert client.get("/api/auth/me").status_code == 200


def test_login_non_ascii_password(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "myhub_password", "비밀번호123")
    res = client.post("/api/auth/login", json={"password": "비밀번호123"})
    assert res.status_code == 200
    res = client.post("/api/auth/login", json={"password": "wrong"})
    assert res.status_code == 401


def test_login_rate_limited_after_repeated_failures(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "myhub_password", "changeme")
    for _ in range(5):
        res = client.post("/api/auth/login", json={"password": "wrong"})
        assert res.status_code == 401
    res = client.post("/api/auth/login", json={"password": "changeme"})
    assert res.status_code == 429


def test_profile_upsert(auth_client):
    assert auth_client.get("/api/profile").json() == {
        "name": "", "sex": None, "birth_date": None}
    res = auth_client.put("/api/profile", json={
        "name": "길섭", "sex": "M", "birth_date": "1990-06-25"})
    assert res.status_code == 200
    assert auth_client.get("/api/profile").json() == {
        "name": "길섭", "sex": "M", "birth_date": "1990-06-25"}
