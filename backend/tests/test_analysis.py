import json
from datetime import datetime


GOOD_RESULT = {
    "summary": "전반적으로 양호합니다",
    "deficiencies": [{"nutrient": "vitamin_d", "confidence": "med", "evidence_ids": [1]}],
    "excesses": [],
    "top3": [{
        "nutrient": "vitamin_d", "why": "일조량 부족",
        "actions": [
            {"type": "food", "text": "고등어", "portion": "100g"},
            {"type": "recipe", "text": "고등어구이"},
            {"type": "habit", "text": "산책 30분"},
        ],
        "evidence_ids": [1],
    }],
    "missing_data": [{"metric_code": "vitamin_d", "why_it_matters": "혈중 농도 확인 필요"}],
}


def _fake_client(payload_sequence):
    calls = {"n": 0}

    class FakeMsg:
        def __init__(self, content): self.content = content

    class FakeChoice:
        def __init__(self, content): self.message = FakeMsg(content)

    class FakeCompletion:
        def __init__(self, content): self.choices = [FakeChoice(content)]

    class FakeCompletions:
        def create(self, **kw):
            payload = payload_sequence[min(calls["n"], len(payload_sequence) - 1)]
            calls["n"] += 1
            return FakeCompletion(json.dumps(payload))

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kw): self.chat = FakeChat()

    return FakeClient


def _seed_evidence(db_session_factory):
    from app.models import EvidenceRef
    db = db_session_factory()
    db.add(EvidenceRef(id=1, type="KDRI", nutrient_code="vitamin_d",
                       claim_summary="비타민D 권장량", source_url="https://www.mohw.go.kr",
                       reliability_grade="A"))
    db.commit()
    return db


def test_run_analysis_success(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([GOOD_RESULT]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    result = analysis.run_analysis(db, trigger="manual")
    stored = json.loads(result.result)
    assert stored["summary"] == "전반적으로 양호합니다"
    assert result.trigger == "manual"


def test_run_analysis_retries_on_bad_citation(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)
    bad = {**GOOD_RESULT, "top3": [{**GOOD_RESULT["top3"][0], "evidence_ids": [999]}]}
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([bad, GOOD_RESULT]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    result = analysis.run_analysis(db, trigger="manual")
    stored = json.loads(result.result)
    assert stored["top3"][0]["evidence_ids"] == [1]


def test_run_analysis_fails_after_two_bad_attempts(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)
    bad = {**GOOD_RESULT, "top3": [{**GOOD_RESULT["top3"][0], "evidence_ids": [999]}]}
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([bad, bad]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    try:
        analysis.run_analysis(db, trigger="manual")
        assert False, "expected AnalysisError"
    except analysis.AnalysisError:
        pass


def test_run_analysis_network_failure(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)

    class BoomCompletions:
        def create(self, **kw):
            raise RuntimeError("network down")

    class BoomChat:
        completions = BoomCompletions()

    class BoomClient:
        def __init__(self, **kw): self.chat = BoomChat()

    monkeypatch.setattr(analysis, "OpenAI", BoomClient)
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    try:
        analysis.run_analysis(db, trigger="manual")
        assert False, "expected AnalysisError"
    except analysis.AnalysisError:
        pass


def test_run_endpoint(auth_client, db_session_factory, monkeypatch):
    from app import analysis
    _seed_evidence(db_session_factory)
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([GOOD_RESULT]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/analysis/run")
    assert res.status_code == 201
    assert res.json()["summary"] == "전반적으로 양호합니다"


def test_run_endpoint_failure_returns_502(auth_client, db_session_factory, monkeypatch):
    from app import analysis
    _seed_evidence(db_session_factory)
    bad = {**GOOD_RESULT, "top3": [{**GOOD_RESULT["top3"][0], "evidence_ids": [999]}]}
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([bad, bad]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    res = auth_client.post("/api/analysis/run")
    assert res.status_code == 502


def test_analysis_list_and_get(auth_client, db_session_factory):
    from app.models import Analysis
    db = db_session_factory()
    db.add(Analysis(trigger="manual", result=json.dumps(GOOD_RESULT),
                    run_at=datetime(2026, 7, 29, 9, 0)))
    db.commit()

    latest = auth_client.get("/api/analysis/latest").json()
    assert latest["summary"] == "전반적으로 양호합니다"

    listing = auth_client.get("/api/analysis").json()
    assert len(listing) == 1 and listing[0]["trigger"] == "manual"

    detail = auth_client.get(f"/api/analysis/{listing[0]['id']}").json()
    assert detail["top3"][0]["nutrient"] == "vitamin_d"

    assert auth_client.get("/api/analysis/9999").status_code == 404


def test_analysis_latest_is_null_when_none_exist(auth_client):
    assert auth_client.get("/api/analysis/latest").json() is None


def test_call_llm_uses_configured_base_url(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)
    captured = {}
    Base = _fake_client([GOOD_RESULT])

    class Rec(Base):
        def __init__(self, **kw):
            captured.update(kw)
            super().__init__(**kw)

    monkeypatch.setattr(analysis, "OpenAI", Rec)
    monkeypatch.setattr(analysis.settings, "openai_api_key", "nvapi-key")
    monkeypatch.setattr(analysis.settings, "openai_base_url",
                        "https://integrate.api.nvidia.com/v1")

    analysis.run_analysis(db, trigger="manual")
    assert captured["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert captured["api_key"] == "nvapi-key"
    assert captured["timeout"] == analysis.settings.openai_timeout


def test_run_endpoint_resolves_evidence(auth_client, db_session_factory, monkeypatch):
    from app import analysis
    _seed_evidence(db_session_factory)  # EvidenceRef id=1, grade A, mohw url
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([GOOD_RESULT]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "k")

    res = auth_client.post("/api/analysis/run").json()
    assert "evidence" in res
    ev = res["evidence"]["1"]  # GOOD_RESULT cites evidence_ids [1]
    assert ev["reliability_grade"] == "A"
    assert ev["source_url"].startswith("http")
    assert ev["type"] == "KDRI"


def test_analysis_requires_auth(client):
    assert client.get("/api/analysis").status_code == 401
