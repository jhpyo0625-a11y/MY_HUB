from sqlalchemy.orm import Session

from .models import MetricDefinition

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
