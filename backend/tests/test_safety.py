def _make_supplement(db, product_name, ingredient_code, amount, unit, days="0123456"):
    from app.models import Supplement, SupplementIngredient, SupplementSchedule
    s = Supplement(product_name=product_name)
    s.ingredients.append(SupplementIngredient(
        ingredient_code=ingredient_code, amount=amount, unit=unit))
    s.schedules.append(SupplementSchedule(
        days_of_week=days, time_of_day="09:00", servings=1))
    db.add(s)
    db.commit()
    return s


def test_worst_day_servings_sums_same_day_schedules():
    from app.routers.safety import _worst_day_servings

    class FakeSchedule:
        def __init__(self, days, servings):
            self.days_of_week, self.servings = days, servings

    schedules = [FakeSchedule("0", 1), FakeSchedule("0", 1), FakeSchedule("3", 2)]
    assert _worst_day_servings(schedules) == 2  # Mon: 1+1=2, Thu: 2 -> max is 2


def test_duplication_detected(db_session_factory):
    from app.routers.safety import compute_safety_warnings
    db = db_session_factory()
    s1 = _make_supplement(db, "A", "vitamin_c", 500, "mg")
    s2 = _make_supplement(db, "B", "vitamin_c", 500, "mg")

    warnings = compute_safety_warnings([s1, s2], [], [], "F")
    assert {"type": "duplication", "ingredient_code": "vitamin_c",
           "message": "vitamin_c 성분이 2개 제품에 중복되어 있습니다"} in warnings


def test_overdose_detected_at_or_above_ul(db_session_factory):
    from app.models import NutrientLimit
    from app.routers.safety import compute_safety_warnings
    db = db_session_factory()
    s1 = _make_supplement(db, "고용량C", "vitamin_c", 1500, "mg")
    # ul == total intake (1500) so this pins the ">=" boundary, not just "above"
    lim = NutrientLimit(ingredient_code="vitamin_c", unit="mg", rda=100, ul=1500, sex="ALL")
    db.add(lim)
    db.commit()

    warnings = compute_safety_warnings([s1], [lim], [], "F")
    assert any(w["type"] == "overdose" and w["ingredient_code"] == "vitamin_c"
              for w in warnings)


def test_no_overdose_under_ul(db_session_factory):
    from app.models import NutrientLimit
    from app.routers.safety import compute_safety_warnings
    db = db_session_factory()
    s1 = _make_supplement(db, "저용량C", "vitamin_c", 100, "mg")
    lim = NutrientLimit(ingredient_code="vitamin_c", unit="mg", rda=100, ul=2000, sex="ALL")
    db.add(lim)
    db.commit()

    warnings = compute_safety_warnings([s1], [lim], [], "F")
    assert not any(w["type"] == "overdose" for w in warnings)


def test_sex_specific_limit_overrides_all(db_session_factory):
    from app.models import NutrientLimit
    from app.routers.safety import compute_safety_warnings
    db = db_session_factory()
    s1 = _make_supplement(db, "철분", "iron", 40, "mg")
    lim_all = NutrientLimit(ingredient_code="iron", unit="mg", rda=10, ul=45, sex="ALL")
    lim_f = NutrientLimit(ingredient_code="iron", unit="mg", rda=14, ul=45, sex="F")
    db.add_all([lim_all, lim_f])
    db.commit()

    warnings = compute_safety_warnings([s1], [lim_all, lim_f], [], "F")
    assert not any(w["type"] == "overdose" for w in warnings)  # 40mg < 45mg UL


def test_interaction_flagged_when_both_present(db_session_factory):
    from app.models import InteractionRule
    from app.routers.safety import compute_safety_warnings
    db = db_session_factory()
    s1 = _make_supplement(db, "칼슘제", "calcium", 500, "mg")
    s2 = _make_supplement(db, "철분제", "iron", 20, "mg")
    rule = InteractionRule(ingredient_a="calcium", ingredient_b="iron", reason="흡수 저해")
    db.add(rule)
    db.commit()

    warnings = compute_safety_warnings([s1, s2], [], [rule], "F")
    assert {"type": "interaction", "ingredient_codes": ["calcium", "iron"],
           "message": "흡수 저해"} in warnings


def test_safety_endpoint_requires_auth(client):
    assert client.get("/api/safety/warnings").status_code == 401


def test_safety_endpoint_returns_warnings(auth_client, db_session_factory):
    from app.models import Profile
    db = db_session_factory()
    db.add(Profile(id=1, sex="F"))
    _make_supplement(db, "A", "vitamin_c", 500, "mg")
    _make_supplement(db, "B", "vitamin_c", 500, "mg")

    res = auth_client.get("/api/safety/warnings")
    assert res.status_code == 200
    assert any(w["type"] == "duplication" for w in res.json())
