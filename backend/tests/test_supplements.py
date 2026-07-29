SUPP = {
    "brand": "나우푸드", "product_name": "오메가3", "serving_size": "1캡슐",
    "ingredients": [{"ingredient_code": "omega3", "amount": 1000, "unit": "mg"}],
    "schedules": [{"days_of_week": "0123456", "time_of_day": "09:00", "servings": 1}],
}


def test_supplement_crud(auth_client):
    res = auth_client.post("/api/supplements", json=SUPP)
    assert res.status_code == 201
    sid = res.json()["id"]

    supps = auth_client.get("/api/supplements").json()
    assert len(supps) == 1
    assert supps[0]["ingredients"][0]["ingredient_code"] == "omega3"

    # replace wholesale
    updated = dict(SUPP, product_name="오메가3 골드",
                   schedules=[{"days_of_week": "024", "time_of_day": "21:00",
                               "servings": 2}])
    assert auth_client.put(f"/api/supplements/{sid}", json=updated).status_code == 200
    supps = auth_client.get("/api/supplements").json()
    assert supps[0]["product_name"] == "오메가3 골드"
    assert supps[0]["schedules"][0]["time_of_day"] == "21:00"

    # intake upsert
    new_schedule_id = supps[0]["schedules"][0]["id"]
    for status in ("taken", "skipped"):
        res = auth_client.post("/api/intake", json={
            "schedule_id": new_schedule_id, "date": "2026-07-29",
            "status": status})
        assert res.status_code == 200

    # soft delete
    assert auth_client.delete(f"/api/supplements/{sid}").status_code == 204
    assert auth_client.get("/api/supplements").json() == []


def test_intake_validation(auth_client):
    res = auth_client.post("/api/supplements", json=SUPP)
    assert res.status_code == 201

    supps = auth_client.get("/api/supplements").json()
    schedule_id = supps[0]["schedules"][0]["id"]

    # invalid status returns 422
    res = auth_client.post("/api/intake", json={
        "schedule_id": schedule_id, "date": "2026-07-29",
        "status": "invalid"})
    assert res.status_code == 422

    # non-existent schedule_id returns 404
    res = auth_client.post("/api/intake", json={
        "schedule_id": 999999, "date": "2026-07-29",
        "status": "taken"})
    assert res.status_code == 404


def test_put_missing_supplement_404(auth_client):
    res = auth_client.put("/api/supplements/999999", json=SUPP)
    assert res.status_code == 404


def test_supplements_require_auth(client):
    assert client.get("/api/supplements").status_code == 401
