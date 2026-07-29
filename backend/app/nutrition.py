import json
import re

import httpx
from openai import OpenAI

from .config import settings

NUTRIENT_KEYS = [
    "kcal", "carb_g", "protein_g", "fat_g", "fiber_g", "sugar_g",
    "sodium_mg", "potassium_mg", "calcium_mg", "iron_mg", "magnesium_mg",
    "zinc_mg", "vitamin_a_ug", "vitamin_c_mg", "vitamin_d_ug",
    "vitamin_b12_ug", "folate_ug", "omega3_g",
]

MFDS_URL = ("https://apis.data.go.kr/1471000/FoodNtrCpntDbInfo02/"
            "getFoodNtrCpntDbInq02")
# ponytail: field mapping taken from 공공데이터포털 문서 #15127578 (식약처 식품영양성분DB).
# Verify against a live response with a real serviceKey on first use; unmapped keys stay None.
MFDS_FIELD_MAP = {  # our key -> API field, values per 100g
    "kcal": "AMT_NUM1", "protein_g": "AMT_NUM3", "fat_g": "AMT_NUM4",
    "carb_g": "AMT_NUM6", "sugar_g": "AMT_NUM7", "fiber_g": "AMT_NUM8",
    "calcium_mg": "AMT_NUM9", "iron_mg": "AMT_NUM10",
    "potassium_mg": "AMT_NUM12", "sodium_mg": "AMT_NUM13",
    "vitamin_a_ug": "AMT_NUM14", "vitamin_c_mg": "AMT_NUM21",
}

_GRAMS_RE = re.compile(r"^\s*([\d.]+)\s*(g|kg)\s*$", re.IGNORECASE)


def _parse_grams(amount: str) -> float | None:
    m = _GRAMS_RE.match(amount or "")
    if not m:
        return None
    val = float(m.group(1))
    return val * 1000 if m.group(2).lower() == "kg" else val


def _mfds_lookup(name: str, grams: float) -> dict | None:
    try:
        res = httpx.get(MFDS_URL, params={
            "serviceKey": settings.mfds_api_key,
            "FOOD_NM_KR": name, "type": "json", "numOfRows": 1,
        }, timeout=10)
        res.raise_for_status()
        items = res.json().get("body", {}).get("items", [])
        if not items:
            return None
        row = items[0]
        factor = grams / 100.0
        out: dict[str, float | None] = {k: None for k in NUTRIENT_KEYS}
        for key, field in MFDS_FIELD_MAP.items():
            raw = row.get(field)
            if raw not in (None, "", "-"):
                out[key] = round(float(raw) * factor, 2)
        return out if out["kcal"] is not None else None
    except Exception:
        return None  # any failure → fall through to next source


def _ai_estimate(name: str, amount: str) -> dict | None:
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        prompt = (
            "다음 음식의 영양성분을 추정해 JSON으로만 답하세요. "
            f"음식: {name}, 양: {amount or '보통 1인분'}. "
            f"키는 정확히 다음만 사용: {', '.join(NUTRIENT_KEYS)}. "
            "값은 숫자(해당 양 전체 기준), 모르면 null."
        )
        res = client.chat.completions.create(
            model=settings.openai_model_mini,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(res.choices[0].message.content)
        return {k: (float(data[k]) if isinstance(data.get(k), (int, float))
                    else None)
                for k in NUTRIENT_KEYS}
    except Exception:
        return None


def resolve_nutrients(name: str, amount: str) -> tuple[dict | None, str]:
    grams = _parse_grams(amount)
    if settings.mfds_api_key and grams is not None:
        values = _mfds_lookup(name, grams)
        if values:
            return values, "mfds_db"
    if settings.openai_api_key:
        values = _ai_estimate(name, amount)
        if values:
            return values, "ai_estimate"
    return None, "none"
