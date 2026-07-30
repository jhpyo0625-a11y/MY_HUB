import json
import logging

from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import settings
from .models import Analysis, ChatMessage, EvidenceRef, MetricDefinition

logger = logging.getLogger(__name__)

DISCLAIMER = "이 답변은 의학적 진단이 아닙니다. 심각하거나 지속되는 증상은 전문의와 상담하세요."


class ProposedEntry(BaseModel):
    metric_code: str
    value_num: float | None = None
    value_text: str | None = None


class ChatReply(BaseModel):
    reply: str
    proposed_entries: list[ProposedEntry] = []


def _build_system_prompt(db: Session) -> str:
    latest = db.query(Analysis).order_by(Analysis.run_at.desc()).first()
    analysis_summary = "아직 분석 기록이 없습니다."
    evidence_excerpt: list[dict] = []
    missing_data: list[dict] = []
    if latest:
        result = json.loads(latest.result)
        analysis_summary = result.get("summary", analysis_summary)
        missing_data = result.get("missing_data", [])
        ids: set[int] = set()
        for note in (*result.get("deficiencies", []), *result.get("excesses", [])):
            ids.update(note.get("evidence_ids", []))
        for entry in result.get("top3", []):
            ids.update(entry.get("evidence_ids", []))
        if ids:
            evidence_excerpt = [
                {"id": e.id, "nutrient_code": e.nutrient_code,
                 "claim_summary": e.claim_summary, "reliability_grade": e.reliability_grade}
                for e in db.query(EvidenceRef).filter(EvidenceRef.id.in_(ids)).all()
            ]
    metric_codes = [d.code for d in db.query(MetricDefinition).all()]

    return (
        "당신은 사용자의 건강 데이터를 돕는 친절한 도우미입니다. "
        "반드시 지정된 JSON 스키마로만 답하세요: "
        '{"reply": str, "proposed_entries": '
        '[{"metric_code": str, "value_num": number|null, "value_text": string|null}]}. '
        "규칙: (1) 데이터가 부족하면 한 번에 하나씩, 쉬운 한국어로 질문하세요. "
        "(2) 사용자의 답이 건강 지표 값이면 proposed_entries에 metric_code와 값을 담아 "
        "저장을 제안하세요 (metric_code는 반드시 다음 중에서만: "
        f"{', '.join(metric_codes)}). 값이 아니면 proposed_entries는 빈 배열로 두세요. "
        "(3) 아래 '참고 근거' 목록에 있는 내용만 근거로 말하고, 목록에 없는 의학 정보는 "
        "'잘 모르겠어요, 전문의와 상담해보세요'라고 답하세요. "
        "(4) 모든 텍스트는 자연스러운 한국어로만 작성하세요.\n"
        f"최근 분석 요약: {analysis_summary}\n"
        f"부족한 데이터 목록: {json.dumps(missing_data, ensure_ascii=False)}\n"
        f"참고 근거: {json.dumps(evidence_excerpt, ensure_ascii=False)}\n"
        f"{DISCLAIMER}"
    )


def _call_llm(system_prompt: str, history: list[ChatMessage], user_content: str) -> dict:
    client = OpenAI(api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url or None,
                    timeout=settings.openai_timeout)
    messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_content})
    res = client.chat.completions.create(
        model=settings.openai_model_strong,
        messages=messages,
        response_format={"type": "json_object"},
    )
    return json.loads(res.choices[0].message.content)


def send_chat_message(db: Session, user_content: str) -> tuple[ChatMessage, ChatMessage]:
    history = db.query(ChatMessage).order_by(ChatMessage.created_at).all()
    system_prompt = _build_system_prompt(db)

    user_msg = ChatMessage(role="user", content=user_content)
    db.add(user_msg)
    db.flush()

    valid_codes = {d.code for d in db.query(MetricDefinition).all()}
    try:
        raw = _call_llm(system_prompt, history, user_content)
        parsed = ChatReply.model_validate(raw)
        proposed = [e for e in parsed.proposed_entries if e.metric_code in valid_codes]
        reply_text = parsed.reply
    except Exception:
        logger.warning("chat reply failed", exc_info=True)
        proposed = []
        reply_text = "죄송해요, 지금 답변을 만들지 못했어요. 잠시 후 다시 시도해주세요."

    assistant_msg = ChatMessage(
        role="assistant", content=reply_text,
        proposed_entries=(json.dumps([e.model_dump() for e in proposed])
                          if proposed else None))
    db.add(assistant_msg)
    db.commit()
    return user_msg, assistant_msg
