def test_seed_evidence_and_limits(db_session_factory):
    from app.models import EvidenceRef, InteractionRule, NutrientLimit
    from app.seed import seed_evidence_and_limits

    db = db_session_factory()
    seed_evidence_and_limits(db)

    assert db.query(EvidenceRef).count() > 0

    limits = db.query(NutrientLimit).filter_by(ingredient_code="vitamin_d").all()
    assert len(limits) == 1
    assert limits[0].ul == 100
    assert limits[0].evidence_id is not None

    rules = db.query(InteractionRule).all()
    assert any(r.ingredient_a == "calcium" and r.ingredient_b == "iron" for r in rules)


def test_seed_evidence_and_limits_idempotent(db_session_factory):
    from app import seed
    from app.models import EvidenceRef

    db = db_session_factory()
    seed.seed_evidence_and_limits(db)
    seed.seed_evidence_and_limits(db)

    assert db.query(EvidenceRef).count() == len(seed.EVIDENCE_REFS)
