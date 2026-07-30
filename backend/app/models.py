from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Profile(Base):
    __tablename__ = "profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    sex: Mapped[str | None] = mapped_column(String)          # "M" | "F"
    birth_date: Mapped[date | None] = mapped_column(Date)
    push_subscription: Mapped[str | None] = mapped_column(Text)  # JSON, Phase 3


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    name_ko: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String, default="")
    domain: Mapped[str] = mapped_column(String)      # body | lab | lifestyle | symptom
    input_type: Mapped[str] = mapped_column(String)  # number | scale | text
    range_low: Mapped[float | None] = mapped_column(Float)
    range_high: Mapped[float | None] = mapped_column(Float)


class MetricEntry(Base):
    __tablename__ = "metric_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    metric_code: Mapped[str] = mapped_column(ForeignKey("metric_definitions.code"))
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(Text)
    measured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    source: Mapped[str] = mapped_column(String, default="manual")  # manual | photo


class Meal(Base):
    __tablename__ = "meals"
    id: Mapped[int] = mapped_column(primary_key=True)
    eaten_at: Mapped[datetime] = mapped_column(DateTime)
    dish_name: Mapped[str] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(Text)
    photo_path: Mapped[str | None] = mapped_column(String)  # Phase 3
    items: Mapped[list["MealItem"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan")


class MealItem(Base):
    __tablename__ = "meal_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id"))
    name: Mapped[str] = mapped_column(String)
    amount: Mapped[str] = mapped_column(String, default="")  # free text: "100g", "1공기"
    nutrients: Mapped[str | None] = mapped_column(Text)      # JSON {kcal, protein_g, ...}
    nutrient_source: Mapped[str] = mapped_column(String, default="none")  # mfds_db | ai_estimate | photo | none
    meal: Mapped["Meal"] = relationship(back_populates="items")


class Supplement(Base):
    __tablename__ = "supplements"
    id: Mapped[int] = mapped_column(primary_key=True)
    brand: Mapped[str] = mapped_column(String, default="")
    product_name: Mapped[str] = mapped_column(String)
    serving_size: Mapped[str] = mapped_column(String, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    photo_path: Mapped[str | None] = mapped_column(String)  # Phase 3
    ingredients: Mapped[list["SupplementIngredient"]] = relationship(
        back_populates="supplement", cascade="all, delete-orphan")
    schedules: Mapped[list["SupplementSchedule"]] = relationship(
        back_populates="supplement", cascade="all, delete-orphan")


class SupplementIngredient(Base):
    __tablename__ = "supplement_ingredients"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplement_id: Mapped[int] = mapped_column(ForeignKey("supplements.id"))
    ingredient_code: Mapped[str] = mapped_column(String)  # snake_case, e.g. vitamin_d
    amount: Mapped[float] = mapped_column(Float)          # per serving
    unit: Mapped[str] = mapped_column(String)             # mg | ug | IU | g
    supplement: Mapped["Supplement"] = relationship(back_populates="ingredients")


class SupplementSchedule(Base):
    __tablename__ = "supplement_schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplement_id: Mapped[int] = mapped_column(ForeignKey("supplements.id"))
    days_of_week: Mapped[str] = mapped_column(String)  # digits, 0=Mon … 6=Sun, e.g. "024"
    time_of_day: Mapped[str] = mapped_column(String)   # "HH:MM"
    servings: Mapped[float] = mapped_column(Float, default=1)
    supplement: Mapped["Supplement"] = relationship(back_populates="schedules")


class IntakeLog(Base):
    __tablename__ = "intake_logs"
    __table_args__ = (UniqueConstraint("schedule_id", "date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("supplement_schedules.id"))
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String)  # taken | skipped


class EvidenceRef(Base):
    __tablename__ = "evidence_refs"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String)             # KDRI | NIH_ODS | UL | interaction_rule
    nutrient_code: Mapped[str] = mapped_column(String)
    claim_summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String, default="")
    reliability_grade: Mapped[str] = mapped_column(String)  # A | B | C


class NutrientLimit(Base):
    __tablename__ = "nutrient_limits"
    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_code: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)
    rda: Mapped[float | None] = mapped_column(Float)
    ul: Mapped[float | None] = mapped_column(Float)
    sex: Mapped[str] = mapped_column(String, default="ALL")  # ALL | M | F
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_refs.id"))


class InteractionRule(Base):
    __tablename__ = "interaction_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_a: Mapped[str] = mapped_column(String)
    ingredient_b: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_refs.id"))


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    trigger: Mapped[str] = mapped_column(String)  # manual | weekly
    result: Mapped[str] = mapped_column(Text)     # JSON — see analysis.AnalysisResult
