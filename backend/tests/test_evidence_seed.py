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


def test_interaction_rules_cite_interaction_evidence(db_session_factory):
    from app.models import EvidenceRef, InteractionRule
    from app.seed import seed_evidence_and_limits

    db = db_session_factory()
    seed_evidence_and_limits(db)

    rules = db.query(InteractionRule).all()
    assert len(rules) == 2

    # expected interaction-evidence nutrient_code per rule, keyed by ingredient_a
    expected_nutrient_code = {"calcium": "calcium", "vitamin_e": "omega3"}

    referenced_evidence_ids = set()
    for rule in rules:
        assert rule.evidence_id is not None
        ev = db.get(EvidenceRef, rule.evidence_id)
        assert ev is not None
        assert ev.type == "interaction_rule"
        assert ev.nutrient_code == expected_nutrient_code[rule.ingredient_a]
        referenced_evidence_ids.add(ev.id)

    # every interaction_rule EvidenceRef must be referenced by some rule (no orphans)
    interaction_evidence = db.query(EvidenceRef).filter_by(type="interaction_rule").all()
    assert len(interaction_evidence) == 2
    for ev in interaction_evidence:
        assert ev.id in referenced_evidence_ids
