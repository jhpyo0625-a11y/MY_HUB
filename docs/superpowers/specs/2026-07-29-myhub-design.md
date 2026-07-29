# MyHub — Personal Health Management Service: Design Spec

**Date:** 2026-07-29
**Status:** Approved by owner
**Author:** Lead Developer (Claude) with owner (pyokilseop@gmail.com)

---

## 1. Overview

MyHub is a single-user web service for personal health management. The owner logs
health metrics, meals, and supplements; an AI assistant analyzes the data, warns
about supplement duplication/overdose, ranks the top 3 lacking nutrients with
practical actions, and asks follow-up questions when data is too thin to analyze.

### Confirmed product decisions

| Decision | Choice |
|---|---|
| Audience | Single user (the owner). No public signup. |
| Language | Korean UI; food/supplement data accepted in Korean and English. |
| Backend | Python — FastAPI |
| Frontend | React (Vite + TypeScript + Tailwind), mobile-first PWA |
| Database | SQLite (via SQLAlchemy) |
| AI provider | OpenAI API (vision-capable mini model for extraction; stronger model for analysis/chat) |
| Food nutrient data | 식품의약품안전처 식품영양성분 DB API first, GPT estimation fallback (source flagged per item) |
| Evidence/citations | Curated internal reference base only (KDRIs 2020, NIH ODS, ULs, interaction rules). AI may cite nothing else. |
| Analysis trigger | On-demand button + automatic weekly run |
| Reminders | Browser web push (PWA service worker); in-app badge as fallback |
| Photo input | Supplement labels, meal photos, 건강검진 결과지, 영양정보표 |
| Metric domains | Body basics, blood/lab values, lifestyle, symptoms/conditions |
| Nutrient actions | Foods with portions + 1–2 simple recipe ideas from frequently-logged ingredients |
| Follow-up questioning | Chat page + one-tap prompt cards on dashboard |
| Visual direction | Clean clinical: light theme, calm blue/green, data-forward |
| Priority device | Phone (mobile-first; desktop works) |
| Hosting | Small cloud host (Fly.io / Railway), single Docker container, volume for SQLite + photos |

### Out of scope for v1

Multi-user accounts, weekly meal planning, wearable/device sync, native mobile
apps, medication interaction checking beyond supplements.

---

## 2. Architecture

One FastAPI application serving a JSON API; React SPA built by Vite and served
as static files by the same app. Single Docker container deployed to a small
cloud host with a persistent volume mounted for the SQLite file and uploaded
photos.

```
[React PWA (mobile-first)]
   │  JSON over HTTPS, session cookie auth
[FastAPI]
   ├── SQLAlchemy → SQLite (volume)
   ├── APScheduler → weekly analysis job, reminder firing
   ├── pywebpush → browser push notifications
   ├── OpenAI API → photo extraction, analysis, chat, nutrient fallback
   └── 식약처 식품영양성분 DB API → food nutrient lookup
```

**Auth:** single account, password set via environment variable/first-run setup.
Session cookie. Required because health data sits on the public internet; no
signup flow, no user table beyond one row of profile data.

**Key principle — AI writes nothing unreviewed:** every AI extraction (photos)
goes through a confirmation screen before saving. Every safety warning
(duplication/overdose) is computed by deterministic rules, not the LLM.

---

## 3. Data model

All tables single-user; no `user_id` foreign keys needed except a single
`profile` row.

| Table | Purpose | Key fields |
|---|---|---|
| `profile` | The one user | name, sex, birth date, password hash, push subscription JSON |
| `metric_definitions` | Master catalog of every health metric the app knows | code, Korean name, unit, domain (body/lab/lifestyle/symptom), normal range low/high, input type (number/choice/text) |
| `metric_entries` | Sparse, timestamped user values | metric code, value, measured_at, source (manual/photo) |
| `meals` | A logged meal | eaten_at, dish name, note, photo path |
| `meal_items` | Ingredients/components of a meal | meal id, name, amount, per-nutrient values (JSON), nutrient_source (mfds_db / ai_estimate) |
| `supplements` | A supplement product | brand, product name, photo path, serving size, active flag |
| `supplement_ingredients` | Dosed ingredients per product | supplement id, ingredient code, amount, unit (per serving) |
| `supplement_schedules` | When it's taken | supplement id, days of week, time of day, servings |
| `intake_logs` | Adherence record | schedule id, date, status (taken/skipped) |
| `analyses` | Stored AI analysis runs | run_at, trigger (manual/weekly), result JSON (schema below) |
| `chat_messages` | Conversation history | role, content, created_at |
| `evidence_refs` | Curated citation base | id, type (KDRI/NIH_ODS/UL/interaction_rule), nutrient code, claim summary, source URL, reliability grade (A/B/C) |
| `nutrient_limits` | Machine-readable rules for the safety engine | ingredient code, RDA, UL, unit, age/sex qualifiers (from KDRIs 2020) |

**Sparse-by-design:** `metric_entries` holds only what the owner has actually
entered. The master list is a menu, not a requirement. History is append-only —
new entries never overwrite old ones, enabling trend charts.

**Reliability grades:** A = official guideline (KDRIs, 식약처, NIH ODS),
B = systematic review / meta-analysis, C = weaker evidence. Shown as badges
next to every claim in analysis output.

---

## 4. Features

### 4.1 Data input

- **Manual forms:** metric list grouped by domain (신체 기본 / 혈액검사 /
  생활습관 / 증상). Fill only what you know. Numeric, choice, and free-text
  input types per `metric_definitions`.
- **Photo upload (4 kinds):** supplement label, meal photo, 건강검진 결과지,
  영양정보표. Each kind has its own GPT-vision extraction prompt returning
  structured JSON. Flow: upload → extraction → **confirmation screen with
  editable parsed fields → user approves → save.** Garbage extractions get
  caught at confirmation; nothing enters the DB without review.
- **Calendar logging:** month/week/day views. Meals (dish + ingredients) and
  supplements shown together. Tap a slot to log. Log as much or as little as
  desired.

### 4.2 Nutrient resolution (meals)

For each `meal_item`: query 식약처 식품영양성분 DB API by name; on miss or API
failure, ask GPT to estimate nutrients for the named food/amount. Store which
source produced the numbers (`nutrient_source`) and show a small marker in the
UI (DB-verified vs AI-estimated).

### 4.3 Safety engine (deterministic, no AI)

Runs instantly whenever a supplement or schedule changes:

1. Sum each ingredient's daily dose across all active supplement schedules.
2. Compare totals against `nutrient_limits` (UL, RDA).
3. Flag: (a) same ingredient in 2+ products (duplication), (b) total ≥ UL
   (overdose risk), (c) known bad combinations from `interaction_rule` rows.

Warnings appear on the supplement page and dashboard. The AI assistant may
*explain* a warning conversationally but never computes or overrides it.

### 4.4 Analysis engine

**Triggers:** "분석하기" button (on-demand) + APScheduler weekly job.

**Input assembly (deterministic code):** latest value per metric, 7-day and
30-day nutrient aggregates from meals, supplement intake with adherence,
active symptoms, profile (age/sex for KDRI lookup).

**LLM call:** structured output validated by Pydantic schema:

```json
{
  "summary": "overall status in plain Korean",
  "deficiencies": [{"nutrient": "...", "confidence": "high|med|low", "evidence_ids": [..]}],
  "excesses": [...],
  "top3": [
    {
      "nutrient": "...",
      "why": "...",
      "actions": [
        {"type": "food", "text": "...", "portion": "..."},
        {"type": "recipe", "text": "...", "uses_frequent_ingredients": true},
        {"type": "habit", "text": "..."}
      ],
      "evidence_ids": [..]
    }
  ],
  "missing_data": [{"metric_code": "...", "why_it_matters": "..."}]
}
```

Constraints enforced in the prompt + validator: max 3 `top3` entries, ≥3
actions each, every claim carries `evidence_ids` resolving into
`evidence_refs`, recipe suggestions must prefer ingredients appearing
frequently in the owner's `meal_items` history (the input assembly passes a
frequent-ingredients list). Invalid or out-of-base citations → the run is
rejected and retried once, then surfaced as an error.

`missing_data` feeds the dashboard prompt cards.

### 4.5 Reminders

`supplement_schedules` drive APScheduler jobs → web push via pywebpush →
service worker shows notification ("오메가3 드실 시간이에요"), tapping opens
the checklist to mark taken/skipped. If the push subscription is dead/absent,
the dashboard badge shows pending intakes instead.

### 4.6 Conversational assistant (follow-up mechanism)

Chat page backed by the stronger OpenAI model with conversation history and a
system prompt containing: current data snapshot, latest analysis, evidence
base excerpts, and the `missing_data` list. Behavior rules in the prompt:

- When data is insufficient, ask **one simple question at a time**, in easy
  Korean, no jargon.
- Answers that map to metrics are proposed as structured saves ("혈압
  120/80으로 저장할까요?") — user confirms, then written to `metric_entries`.
- Cites only `evidence_refs`; says "잘 모르겠어요" + recommends a professional
  for out-of-scope medical questions.

Dashboard prompt cards are the second surface: each `missing_data` item
renders as a card with a one-tap inline answer field.

---

## 5. Pages (Korean UI, 5 pages)

| # | Page | Contents |
|---|---|---|
| 1 | **대시보드** | Health status summary, top-3 nutrient cards with actions, today's supplement checklist (tap to mark taken), safety warnings, missing-data prompt cards |
| 2 | **캘린더** | Month/week/day toggle; meals and supplement schedule together; tap slot to add/log; adherence dots |
| 3 | **내 데이터** | Master metric list grouped by domain, fill-what-you-know forms, photo upload entry point, per-metric history charts |
| 4 | **AI 채팅** | Conversation view, follow-up questions, structured-save confirmations |
| 5 | **리포트** | Latest full analysis with evidence badges (A/B/C) and source links, past report list, "분석하기" button |

**Design system:** light theme, white base, calm blue/green accents,
data-forward (clean charts, clear numbers), generous touch targets,
bottom-tab navigation on mobile. Trustworthy-clinical, not sterile.

---

## 6. Error handling

| Failure | Behavior |
|---|---|
| 식약처 API down/miss | GPT nutrient estimation fallback, marked `ai_estimate` |
| OpenAI API down | Logging/calendar fully usable; analysis & chat show friendly retry message |
| Photo extraction nonsense | Confirmation screen — user edits or discards |
| Push subscription expired | In-app badge fallback; settings page shows re-enable button |
| Analysis citation invalid | Retry once with error feedback; then surface failure, keep last good report |
| SQLite/volume issue | Daily backup of DB file to a second path on the volume |

---

## 7. Testing

pytest on the deterministic core — this is where wrong answers hurt:

- Safety engine: duplication detection, UL summation across schedules, unit
  handling (mg/µg/IU), interaction rules.
- Nutrient aggregation: 7/30-day windows, missing-day handling.
- Analysis input assembly: latest-value selection, frequent-ingredient list.
- Reminder scheduling: day-of-week/time expansion, timezone (Asia/Seoul).
- Analysis output: Pydantic schema validation + citation-resolution check.

LLM output *content* is not unit-tested; its *shape and citations* are.
Frontend: light — component smoke tests only; manual QA via /qa flow.

---

## 8. Build phases (Lead-Dev task breakdown)

Each phase ends with a usable app. Detailed per-task implementation plan to be
written next (writing-plans).

### Phase 1 — Core logging (the backbone)
1. Repo scaffold: FastAPI + Vite React + Tailwind + SQLite + Docker
2. Auth (single account, session cookie) + profile setup
3. `metric_definitions` seed (master list, KDRI-informed) + 내 데이터 page with manual forms + history charts
4. Meals & supplements CRUD + 캘린더 page (month/week/day)
5. 식약처 nutrient lookup + GPT fallback for meal items

### Phase 2 — Intelligence
6. `evidence_refs` + `nutrient_limits` curation (KDRIs 2020, NIH ODS, ULs, interaction rules)
7. Safety engine + warnings UI
8. Analysis engine (input assembly, LLM call, schema validation, report storage) + 리포트 page
9. 대시보드 page (summary, top-3 cards, checklist, warnings, missing-data cards)

### Phase 3 — Eyes and voice
10. Photo pipeline (4 extraction types + confirmation screens)
11. AI 채팅 page (follow-up mechanism, structured saves)
12. Web push reminders (service worker, subscription mgmt, APScheduler firing)

### Phase 4 — Ship
13. Weekly auto-analysis job, DB backup job
14. Mobile polish pass, PWA install flow, QA
15. Deploy to cloud host, HTTPS, volume setup

### Cost guardrails
Mini model for extraction/nutrient-fallback; stronger model only for
analysis + chat. Expected light personal use: a few USD/month.

---

## 9. Risks

- **AI health advice liability:** mitigated by curated-citations-only rule,
  reliability badges, deterministic safety engine, and a persistent "의학적
  진단이 아닙니다" disclaimer in analysis/chat UI.
- **식약처 API quality/availability:** fallback path designed in; source
  always flagged.
- **Curation effort for evidence base:** start narrow (the ~20 nutrients
  KDRIs covers well) and grow as needed.
- **Push on iOS:** requires add-to-home-screen; in-app badge fallback covers
  the gap.
