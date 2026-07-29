from sqlalchemy.orm import Session

from .models import EvidenceRef, InteractionRule, MetricDefinition, NutrientLimit

# (code, name_ko, unit, domain, input_type, range_low, range_high)
# ranges = general adult reference ranges; None = no range. scale = 0 없음 / 1 가끔 / 2 자주 / 3 심함
METRIC_DEFINITIONS = [
    # 신체 기본
    ("height_cm",       "키",                "cm",    "body", "number", 100, 220),
    ("weight_kg",       "몸무게",            "kg",    "body", "number", 30, 200),
    ("body_fat_pct",    "체지방률",          "%",     "body", "number", 10, 25),
    ("waist_cm",        "허리둘레",          "cm",    "body", "number", None, 90),
    ("bp_systolic",     "수축기 혈압",       "mmHg",  "body", "number", 90, 120),
    ("bp_diastolic",    "이완기 혈압",       "mmHg",  "body", "number", 60, 80),
    ("heart_rate",      "안정시 심박수",     "bpm",   "body", "number", 60, 100),
    # 혈액검사
    ("fasting_glucose", "공복혈당",          "mg/dL", "lab", "number", 70, 100),
    ("hba1c",           "당화혈색소",        "%",     "lab", "number", 4.0, 5.6),
    ("total_chol",      "총콜레스테롤",      "mg/dL", "lab", "number", None, 200),
    ("ldl",             "LDL 콜레스테롤",    "mg/dL", "lab", "number", None, 130),
    ("hdl",             "HDL 콜레스테롤",    "mg/dL", "lab", "number", 40, None),
    ("triglycerides",   "중성지방",          "mg/dL", "lab", "number", None, 150),
    ("vitamin_d",       "비타민D (25-OH)",   "ng/mL", "lab", "number", 30, 100),
    ("ferritin",        "페리틴",            "ng/mL", "lab", "number", 24, 336),
    ("hemoglobin",      "혈색소",            "g/dL",  "lab", "number", 12, 17),
    ("ast",             "AST (GOT)",         "U/L",   "lab", "number", None, 40),
    ("alt",             "ALT (GPT)",         "U/L",   "lab", "number", None, 40),
    ("creatinine",      "크레아티닌",        "mg/dL", "lab", "number", 0.5, 1.2),
    ("tsh",             "갑상선자극호르몬",  "mIU/L", "lab", "number", 0.4, 4.0),
    # 생활습관
    ("sleep_hours",     "수면시간",          "시간",  "lifestyle", "number", 6, 9),
    ("exercise_min",    "운동시간",          "분/일", "lifestyle", "number", 30, None),
    ("water_ml",        "물 섭취량",         "mL",    "lifestyle", "number", 1500, 2500),
    ("caffeine_cups",   "카페인",            "잔",    "lifestyle", "number", None, 3),
    ("alcohol_drinks",  "음주",              "잔",    "lifestyle", "number", None, 2),
    ("smoking",         "흡연",              "개비",  "lifestyle", "number", None, 0),
    ("stress_level",    "스트레스",          "",      "lifestyle", "scale", 0, 3),
    # 증상
    ("fatigue",         "피로감",            "",      "symptom", "scale", 0, 3),
    ("hair_loss",       "탈모",              "",      "symptom", "scale", 0, 3),
    ("digestion_issue", "소화불량",          "",      "symptom", "scale", 0, 3),
    ("headache",        "두통",              "",      "symptom", "scale", 0, 3),
    ("skin_trouble",    "피부 트러블",       "",      "symptom", "scale", 0, 3),
    ("sleep_quality_low", "수면의 질 저하",  "",      "symptom", "scale", 0, 3),
    ("conditions",      "진단받은 질환",     "",      "symptom", "text", None, None),
    ("medications",     "복용 중인 약",      "",      "symptom", "text", None, None),
    ("allergies",       "알레르기",          "",      "symptom", "text", None, None),
]


def seed_metric_definitions(db: Session) -> None:
    existing = {code for (code,) in db.query(MetricDefinition.code).all()}
    for code, name_ko, unit, domain, input_type, lo, hi in METRIC_DEFINITIONS:
        if code not in existing:
            db.add(MetricDefinition(code=code, name_ko=name_ko, unit=unit,
                                    domain=domain, input_type=input_type,
                                    range_low=lo, range_high=hi))
    db.commit()


# ponytail: values below are standard adult (19-64) DRI figures included for
# structural completeness. Verify each row against the official KDRIs 2020
# tables before relying on them for real dosing decisions — this seed is a
# starting skeleton, not a certified dataset.
EVIDENCE_REFS = [
    # (type, nutrient_code, claim_summary, source_url, reliability_grade)
    ("KDRI", "vitamin_a", "비타민A 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "vitamin_b6", "비타민B6 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "vitamin_b12", "비타민B12 권장 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "vitamin_c", "비타민C 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "vitamin_d", "비타민D 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "vitamin_e", "비타민E 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "folate", "엽산 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "niacin", "나이아신 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "calcium", "칼슘 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "magnesium", "마그네슘 상한 섭취량(보충제 기준) (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "zinc", "아연 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "iron", "철분 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("KDRI", "selenium", "셀레늄 권장/상한 섭취량 (KDRIs 2020)", "https://www.mohw.go.kr", "A"),
    ("NIH_ODS", "potassium", "칼륨 권장 섭취량 (NIH ODS)", "https://ods.od.nih.gov", "A"),
    ("NIH_ODS", "omega3", "오메가3 적정 섭취량 (NIH ODS)", "https://ods.od.nih.gov", "B"),
    ("interaction_rule", "calcium", "칼슘-철분 동시 복용 시 철분 흡수 저해", "https://ods.od.nih.gov", "B"),
    ("interaction_rule", "omega3", "비타민E-오메가3 고용량 병용 시 출혈 위험 증가", "https://ods.od.nih.gov", "C"),
]

NUTRIENT_LIMITS = [
    # (ingredient_code, unit, rda, ul, sex, evidence_nutrient_code)
    ("vitamin_a", "ug", 800, 3000, "M", "vitamin_a"),
    ("vitamin_a", "ug", 650, 3000, "F", "vitamin_a"),
    ("vitamin_b6", "mg", 1.5, 100, "ALL", "vitamin_b6"),
    ("vitamin_b12", "ug", 2.4, None, "ALL", "vitamin_b12"),
    ("vitamin_c", "mg", 100, 2000, "ALL", "vitamin_c"),
    ("vitamin_d", "ug", 10, 100, "ALL", "vitamin_d"),
    ("vitamin_e", "mg", 12, 540, "ALL", "vitamin_e"),
    ("folate", "ug", 400, 1000, "ALL", "folate"),
    ("niacin", "mg", 16, 35, "M", "niacin"),
    ("niacin", "mg", 14, 35, "F", "niacin"),
    ("calcium", "mg", 800, 2500, "M", "calcium"),
    ("calcium", "mg", 700, 2500, "F", "calcium"),
    ("magnesium", "mg", 340, 350, "M", "magnesium"),
    ("magnesium", "mg", 280, 350, "F", "magnesium"),
    ("zinc", "mg", 10, 35, "M", "zinc"),
    ("zinc", "mg", 8, 35, "F", "zinc"),
    ("iron", "mg", 10, 45, "M", "iron"),
    ("iron", "mg", 14, 45, "F", "iron"),
    ("selenium", "ug", 60, 400, "ALL", "selenium"),
    ("potassium", "mg", 3500, None, "ALL", "potassium"),
    ("omega3", "g", 1.3, None, "ALL", "omega3"),
]

INTERACTION_RULES = [
    # (ingredient_a, ingredient_b, reason, evidence_nutrient_code)
    ("calcium", "iron", "칼슘과 철분을 함께 복용하면 철분 흡수가 저해될 수 있어요. "
                        "2시간 이상 간격을 두고 복용하세요.", "calcium"),
    ("vitamin_e", "omega3", "비타민E와 오메가3를 고용량으로 함께 복용하면 출혈 위험이 "
                           "증가할 수 있어요. 항응고제 복용 중이면 의사와 상의하세요.", "omega3"),
]


def seed_evidence_and_limits(db: Session) -> None:
    if db.query(EvidenceRef).count() > 0:
        return  # static seed set — whole-function idempotency is enough here

    by_nutrient: dict[str, int] = {}
    by_interaction: dict[str, int] = {}
    for type_, nutrient_code, claim, url, grade in EVIDENCE_REFS:
        ev = EvidenceRef(type=type_, nutrient_code=nutrient_code,
                         claim_summary=claim, source_url=url,
                         reliability_grade=grade)
        db.add(ev)
        db.flush()
        if type_ == "interaction_rule":
            by_interaction.setdefault(nutrient_code, ev.id)
        else:
            by_nutrient.setdefault(nutrient_code, ev.id)

    for code, unit, rda, ul, sex, ev_code in NUTRIENT_LIMITS:
        db.add(NutrientLimit(ingredient_code=code, unit=unit, rda=rda, ul=ul,
                             sex=sex, evidence_id=by_nutrient.get(ev_code)))

    for a, b, reason, ev_code in INTERACTION_RULES:
        db.add(InteractionRule(ingredient_a=a, ingredient_b=b, reason=reason,
                               evidence_id=by_interaction.get(ev_code)))
    db.commit()
