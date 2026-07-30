import base64
import json
import logging

from openai import OpenAI

from .config import settings
from .nutrition import NUTRIENT_KEYS
from .seed import METRIC_DEFINITIONS

logger = logging.getLogger(__name__)

PHOTO_KINDS = {"supplement_label", "meal", "lab_result", "nutrition_label"}

# Kept in sync with SupplementsPage.tsx's INGREDIENT_SUGGESTIONS by hand —
# small fixed vocabulary, not worth a shared-codegen step.
INGREDIENT_CODE_HINTS = [
    "vitamin_a", "vitamin_b1", "vitamin_b2", "vitamin_b6", "vitamin_b12",
    "vitamin_c", "vitamin_d", "vitamin_e", "vitamin_k", "folate", "niacin",
    "biotin", "calcium", "magnesium", "zinc", "iron", "selenium", "potassium",
    "omega3", "lutein", "probiotics", "coenzyme_q10", "milk_thistle",
]

_LAB_METRIC_CODES = [
    (code, name_ko) for code, name_ko, _unit, domain, _input_type, _lo, _hi
    in METRIC_DEFINITIONS if domain in ("body", "lab")
]


def _prompt_for(kind: str) -> str:
    if kind == "supplement_label":
        return (
            "이 영양제 라벨 사진에서 정보를 추출해 JSON으로만 답하세요. "
            'JSON 형식: {"brand": str, "product_name": str, "serving_size": str, '
            '"ingredients": [{"ingredient_code": str, "amount": number, "unit": str}]}. '
            f"ingredient_code는 가능하면 다음 중에서 고르세요: {', '.join(INGREDIENT_CODE_HINTS)}. "
            "일치하는 항목이 없으면 영문 소문자 스네이크케이스로 새로 만드세요. "
            "읽을 수 없는 값은 생략하세요."
        )
    if kind == "meal":
        return (
            "이 음식 사진에서 요리 이름과 재료를 추출해 JSON으로만 답하세요. "
            'JSON 형식: {"dish_name": str, "items": [{"name": str, "amount": str}]}. '
            "amount는 '100g', '반 공기'처럼 짧은 한국어 표현으로 추정하세요."
        )
    if kind == "lab_result":
        codes = ", ".join(f"{c}({n})" for c, n in _LAB_METRIC_CODES)
        return (
            "이 건강검진 결과지 사진에서 수치를 추출해 JSON으로만 답하세요. "
            'JSON 형식: {"entries": [{"metric_code": str, "value_num": number, '
            '"measured_at": str}]}. '
            f"metric_code는 반드시 다음 중에서만 고르세요: {codes}. "
            "measured_at은 검사일이 보이면 YYYY-MM-DD, 없으면 빈 문자열. "
            "표에 없는 항목은 결과에 포함하지 마세요."
        )
    if kind == "nutrition_label":
        return (
            "이 영양정보표 사진에서 정보를 추출해 JSON으로만 답하세요. "
            'JSON 형식: {"name": str, "amount": str, "nutrients": {키: number}}. '
            f"nutrients의 키는 정확히 다음만 사용: {', '.join(NUTRIENT_KEYS)}. "
            "amount는 1회 제공량 기준(예: '100g'). 읽을 수 없는 값은 생략하세요."
        )
    raise ValueError(f"알 수 없는 사진 종류: {kind}")


def extract_from_photo(kind: str, image_bytes: bytes, mime: str) -> dict:
    if kind not in PHOTO_KINDS:
        raise ValueError(f"알 수 없는 사진 종류: {kind}")
    prompt = _prompt_for(kind)
    b64 = base64.b64encode(image_bytes).decode()
    client = OpenAI(api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url or None,
                    timeout=settings.openai_timeout)
    res = client.chat.completions.create(
        model=settings.openai_model_mini,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
        response_format={"type": "json_object"},
    )
    return json.loads(res.choices[0].message.content)
