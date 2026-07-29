import pytest


@pytest.fixture()
def seeded_client(auth_client, db_session_factory):
    from app.seed import seed_metric_definitions
    db = db_session_factory()
    seed_metric_definitions(db)
    db.close()
    return auth_client


def test_definitions_seeded(seeded_client):
    res = seeded_client.get("/api/metrics/definitions")
    assert res.status_code == 200
    defs = res.json()
    codes = {d["code"] for d in defs}
    assert {"weight_kg", "bp_systolic", "vitamin_d", "sleep_hours", "fatigue"} <= codes
    assert all(d["domain"] in {"body", "lab", "lifestyle", "symptom"} for d in defs)


def test_requires_auth(client):
    assert client.get("/api/metrics/definitions").status_code == 401


def test_entry_roundtrip_and_latest(seeded_client):
    res = seeded_client.post("/api/metrics/entries", json={
        "metric_code": "weight_kg", "value_num": 72.5,
        "measured_at": "2026-07-28T08:00:00"})
    assert res.status_code == 201
    res = seeded_client.post("/api/metrics/entries", json={
        "metric_code": "weight_kg", "value_num": 72.0,
        "measured_at": "2026-07-29T08:00:00"})
    assert res.status_code == 201

    latest = seeded_client.get("/api/metrics/latest").json()
    assert latest["weight_kg"]["value_num"] == 72.0

    entries = seeded_client.get("/api/metrics/entries",
                                params={"code": "weight_kg"}).json()
    assert [e["value_num"] for e in entries] == [72.0, 72.5]  # newest first


def test_entry_validation(seeded_client):
    # unknown code
    assert seeded_client.post("/api/metrics/entries", json={
        "metric_code": "nope", "value_num": 1}).status_code == 404
    # number metric without value_num
    assert seeded_client.post("/api/metrics/entries", json={
        "metric_code": "weight_kg", "value_text": "hi"}).status_code == 422
    # scale out of range
    assert seeded_client.post("/api/metrics/entries", json={
        "metric_code": "fatigue", "value_num": 9}).status_code == 422
    # text metric works
    assert seeded_client.post("/api/metrics/entries", json={
        "metric_code": "medications", "value_text": "혈압약"}).status_code == 201
