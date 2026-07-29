import json


def test_parse_grams():
    from app.nutrition import _parse_grams
    assert _parse_grams("100g") == 100
    assert _parse_grams("150 g") == 150
    assert _parse_grams("0.5kg") == 500
    assert _parse_grams("1공기") is None
    assert _parse_grams("") is None


def test_mfds_lookup_scaling(monkeypatch):
    from app import nutrition
    from app.config import settings
    monkeypatch.setattr(settings, "mfds_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_api_key", "")

    canned = {"body": {"items": [
        {"FOOD_NM_KR": "김치찌개",
         "AMT_NUM1": "45.0", "AMT_NUM3": "3.5", "AMT_NUM4": "2.0",
         "AMT_NUM6": "4.0", "AMT_NUM7": "1.5", "AMT_NUM8": "1.2",
         "AMT_NUM9": "30.0", "AMT_NUM10": "0.8", "AMT_NUM12": "200.0",
         "AMT_NUM13": "500.0"}]}}

    class FakeResponse:
        status_code = 200
        def json(self):
            return canned
        def raise_for_status(self):
            pass

    monkeypatch.setattr(nutrition.httpx, "get",
                        lambda *a, **kw: FakeResponse())

    values, source = nutrition.resolve_nutrients("김치찌개", "200g")
    assert source == "mfds_db"
    assert values["kcal"] == 90.0        # 45 per 100g × 200g
    assert values["sodium_mg"] == 1000.0


def test_ai_fallback(monkeypatch):
    from app import nutrition
    from app.config import settings
    monkeypatch.setattr(settings, "mfds_api_key", "")   # no MFDS
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    ai_json = {k: 1.0 for k in nutrition.NUTRIENT_KEYS}

    class FakeMsg:
        content = json.dumps(ai_json)
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
        def __init__(self, **kw):
            self.chat = FakeChat()

    monkeypatch.setattr(nutrition, "OpenAI", FakeClient)

    values, source = nutrition.resolve_nutrients("비빔밥", "1그릇")
    assert source == "ai_estimate"
    assert values["kcal"] == 1.0


def test_no_sources_configured(monkeypatch):
    from app import nutrition
    from app.config import settings
    monkeypatch.setattr(settings, "mfds_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert nutrition.resolve_nutrients("뭔가", "100g") == (None, "none")


def test_meal_create_resolves(auth_client, monkeypatch):
    from app.routers import meals as meals_module
    monkeypatch.setattr(meals_module, "resolve_nutrients",
                        lambda name, amount: ({"kcal": 42.0}, "ai_estimate"))
    auth_client.post("/api/meals", json={
        "eaten_at": "2026-07-29T12:00:00", "dish_name": "테스트",
        "items": [{"name": "밥", "amount": "1공기"}]})
    meals = auth_client.get("/api/meals",
                            params={"start": "2026-07-29",
                                    "end": "2026-07-29"}).json()
    item = meals[0]["items"][0]
    assert item["nutrient_source"] == "ai_estimate"
    assert item["nutrients"]["kcal"] == 42.0
