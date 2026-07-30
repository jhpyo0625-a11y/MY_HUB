def test_meal_crud(auth_client):
    res = auth_client.post("/api/meals", json={
        "eaten_at": "2026-07-29T12:00:00",
        "dish_name": "김치찌개",
        "items": [{"name": "돼지고기", "amount": "100g"},
                  {"name": "두부", "amount": "반 모"}]})
    assert res.status_code == 201
    meal_id = res.json()["id"]

    res = auth_client.get("/api/meals",
                          params={"start": "2026-07-29", "end": "2026-07-29"})
    meals = res.json()
    assert len(meals) == 1
    assert meals[0]["dish_name"] == "김치찌개"
    assert [i["name"] for i in meals[0]["items"]] == ["돼지고기", "두부"]
    assert meals[0]["items"][0]["nutrient_source"] == "none"

    # outside range → empty
    assert auth_client.get("/api/meals",
                           params={"start": "2026-07-30", "end": "2026-07-31"}).json() == []

    assert auth_client.delete(f"/api/meals/{meal_id}").status_code == 204
    assert auth_client.get("/api/meals",
                           params={"start": "2026-07-29", "end": "2026-07-29"}).json() == []


def test_meals_require_auth(client):
    assert client.get("/api/meals",
                      params={"start": "2026-07-29", "end": "2026-07-29"}).status_code == 401


def test_meal_with_photo_and_prefilled_nutrients(auth_client):
    res = auth_client.post("/api/meals", json={
        "eaten_at": "2026-07-29T12:00:00", "dish_name": "컵라면",
        "photo_path": "abc123.jpg",
        "items": [{"name": "컵라면", "amount": "1개",
                   "nutrients": {"kcal": 500, "sodium_mg": 1200}}]})
    assert res.status_code == 201
    meal = auth_client.get("/api/meals",
                           params={"start": "2026-07-29", "end": "2026-07-29"}).json()[0]
    assert meal["photo_path"] == "abc123.jpg"
    assert meal["items"][0]["nutrient_source"] == "photo"
    assert meal["items"][0]["nutrients"]["kcal"] == 500
