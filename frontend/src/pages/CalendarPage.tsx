import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { PhotoUploadButton, photoUrl } from "../PhotoUpload";

interface MealItemOut { id: number; name: string; amount: string; nutrient_source: string; }
interface MealOut {
  id: number; eaten_at: string; dish_name: string;
  photo_path: string | null; items: MealItemOut[];
}
interface MealExtract { dish_name?: string; items?: { name: string; amount: string }[]; }
interface LabelExtract {
  name?: string; amount?: string; nutrients?: Record<string, number | null>;
}
interface Slot {
  date: string; time: string; schedule_id: number; supplement_id: number;
  supplement_name: string; servings: number; status: "taken" | "skipped" | "pending";
}
type View = "month" | "week" | "day";

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const startOfWeek = (d: Date) => addDays(d, -((d.getDay() + 6) % 7)); // Monday
const DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"];

function rangeFor(view: View, anchor: Date): [Date, Date] {
  if (view === "day") return [anchor, anchor];
  if (view === "week") return [startOfWeek(anchor), addDays(startOfWeek(anchor), 6)];
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
  return [first, last];
}

function AddMealForm({ date, onDone }: { date: string; onDone: () => void }) {
  const [dish, setDish] = useState("");
  const [time, setTime] = useState("12:00");
  const [items, setItems] = useState<
    { name: string; amount: string; nutrients?: Record<string, number | null> }[]
  >([{ name: "", amount: "" }]);
  const [photoPath, setPhotoPath] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function applyMealExtract(result: {
    photo_path: string; extracted: MealExtract | null; error: string | null;
  }) {
    setPhotoPath(result.photo_path);
    if (result.extracted) {
      if (result.extracted.dish_name) setDish(result.extracted.dish_name);
      if (result.extracted.items?.length) setItems(result.extracted.items);
    }
    setNotice(result.error ? `사진은 저장했지만 자동 인식은 실패했어요: ${result.error}` : null);
  }

  function applyLabelExtract(result: {
    extracted: LabelExtract | null; error: string | null;
  }) {
    if (result.extracted) {
      const extracted = result.extracted;
      setItems((prev) => [...prev.filter((i) => i.name.trim()), {
        name: extracted.name || "", amount: extracted.amount || "",
        nutrients: extracted.nutrients,
      }]);
    }
    setNotice(result.error ? `영양정보표 인식 실패: ${result.error}` : null);
  }

  async function save() {
    setSaving(true);
    try {
      await api("/api/meals", {
        method: "POST",
        body: JSON.stringify({
          eaten_at: `${date}T${time}:00`,
          dish_name: dish,
          photo_path: photoPath,
          items: items.filter((i) => i.name.trim()),
        }),
      });
      onDone();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3 rounded-2xl border border-stone-200/80 bg-white p-4 shadow-sm shadow-slate-200/50">
      <div className="flex gap-2">
        <PhotoUploadButton kind="meal" label="음식 사진" onExtracted={applyMealExtract} />
        <PhotoUploadButton kind="nutrition_label" label="영양정보표" onExtracted={applyLabelExtract} />
      </div>
      {notice && <p className="text-xs text-amber-600">{notice}</p>}
      {photoPath && (
        <img src={photoUrl(photoPath)} className="h-24 w-24 rounded-lg object-cover" />
      )}
      <div className="flex gap-2">
        <input value={dish} onChange={(e) => setDish(e.target.value)}
               placeholder="음식 이름 (예: 김치찌개)"
               className="flex-1 rounded-lg border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none" />
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)}
               className="rounded-lg border border-slate-300 px-2" />
      </div>
      {items.map((it, idx) => (
        <div key={idx} className="flex gap-2">
          <input value={it.name} placeholder="재료"
                 onChange={(e) => setItems(items.map((x, i) => i === idx ? { ...x, name: e.target.value } : x))}
                 className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none" />
          <input value={it.amount} placeholder="양 (예: 100g, 반 모)"
                 onChange={(e) => setItems(items.map((x, i) => i === idx ? { ...x, amount: e.target.value } : x))}
                 className="w-32 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none" />
        </div>
      ))}
      <div className="flex gap-2">
        <button onClick={() => setItems([...items, { name: "", amount: "" }])}
                className="py-2 text-sm font-medium text-teal-700">+ 재료 추가</button>
        <button onClick={save} disabled={saving || !dish.trim()}
                className="ml-auto rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-40">
          {saving ? "영양성분 계산 중…" : "저장"}
        </button>
      </div>
    </div>
  );
}

function DayDetail({ date, meals, slots, reload }: {
  date: string; meals: MealOut[]; slots: Slot[]; reload: () => void;
}) {
  const [adding, setAdding] = useState(false);

  async function setIntake(slot: Slot, status: "taken" | "skipped") {
    await api("/api/intake", {
      method: "POST",
      body: JSON.stringify({ schedule_id: slot.schedule_id, date, status }),
    });
    reload();
  }
  async function removeMeal(id: number) {
    await api(`/api/meals/${id}`, { method: "DELETE" });
    reload();
  }

  return (
    <div className="space-y-5">
      <section className="space-y-2.5">
        <h3 className="font-display text-base font-bold text-slate-800">영양제</h3>
        {slots.length === 0 && <p className="text-sm text-slate-400">예정된 영양제가 없습니다</p>}
        {slots.map((s) => (
          <div key={s.schedule_id}
               className="flex items-center gap-3 rounded-2xl border border-stone-200/80 bg-white p-3.5 shadow-sm shadow-slate-200/50">
            <span className="font-mono text-sm text-slate-400 tabular-nums">{s.time}</span>
            <span className="text-sm font-medium text-slate-800">
              {s.supplement_name}{s.servings > 1 ? <span className="text-slate-400"> ×{s.servings}</span> : null}
            </span>
            <div className="ml-auto flex gap-1.5">
              <button onClick={() => setIntake(s, "taken")}
                      className={`rounded-lg px-3 py-2 text-sm transition-colors ${s.status === "taken" ? "bg-emerald-500 text-white" : "border border-slate-300 text-slate-600"}`}>
                복용 ✓
              </button>
              <button onClick={() => setIntake(s, "skipped")}
                      className={`rounded-lg px-3 py-2 text-sm transition-colors ${s.status === "skipped" ? "bg-slate-400 text-white" : "border border-slate-300 text-slate-600"}`}>
                건너뜀
              </button>
            </div>
          </div>
        ))}
      </section>
      <section className="space-y-2.5">
        <div className="flex items-center">
          <h3 className="font-display text-base font-bold text-slate-800">식사</h3>
          <button onClick={() => setAdding(!adding)} className="ml-auto py-2 text-sm font-medium text-teal-700">
            {adding ? "닫기" : "+ 식사 기록"}
          </button>
        </div>
        {adding && <AddMealForm date={date} onDone={() => { setAdding(false); reload(); }} />}
        {meals.map((m) => (
          <div key={m.id} className="rounded-2xl border border-stone-200/80 bg-white p-3.5 shadow-sm shadow-slate-200/50">
            <div className="flex items-center">
              <span className="font-medium text-slate-800">
                <span className="font-mono text-sm text-slate-400">{m.eaten_at.slice(11, 16)}</span> · {m.dish_name}
              </span>
              <button onClick={() => removeMeal(m.id)} className="ml-auto py-2 text-xs text-slate-400">삭제</button>
            </div>
            {m.items.length > 0 && (
              <p className="mt-1 text-xs text-slate-500">
                {m.items.map((i) => `${i.name}${i.nutrient_source === "ai_estimate" ? "*" : ""}`).join(", ")}
              </p>
            )}
            {m.photo_path && (
              <img src={photoUrl(m.photo_path)} className="mt-2 h-16 w-16 rounded-lg object-cover" />
            )}
          </div>
        ))}
        {meals.length > 0 && meals.some((m) => m.items.some((i) => i.nutrient_source === "ai_estimate")) && (
          <p className="text-xs text-slate-400">* AI 추정 영양성분</p>
        )}
      </section>
    </div>
  );
}

export default function CalendarPage() {
  const [view, setView] = useState<View>("day");
  const [anchor, setAnchor] = useState(new Date());
  const [meals, setMeals] = useState<MealOut[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);

  const [start, end] = rangeFor(view, anchor);

  const reload = useCallback(() => {
    api<{ meals: MealOut[]; supplement_slots: Slot[] }>(
      `/api/calendar?start=${iso(start)}&end=${iso(end)}`
    ).then((d) => { setMeals(d.meals); setSlots(d.supplement_slots); });
  }, [view, anchor]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(reload, [reload]);

  function shift(n: number) {
    if (view === "day") setAnchor(addDays(anchor, n));
    else if (view === "week") setAnchor(addDays(anchor, n * 7));
    else setAnchor(new Date(anchor.getFullYear(), anchor.getMonth() + n, 1));
  }

  const title =
    view === "day"
      ? `${anchor.getMonth() + 1}월 ${anchor.getDate()}일 (${DAY_NAMES[(anchor.getDay() + 6) % 7]})`
      : view === "week"
        ? `${start.getMonth() + 1}/${start.getDate()} – ${end.getMonth() + 1}/${end.getDate()}`
        : `${anchor.getFullYear()}년 ${anchor.getMonth() + 1}월`;

  const byDate = (arr: { [k: string]: any }[], key: string, d: string) =>
    arr.filter((x) => String(x[key]).slice(0, 10) === d);

  return (
    <div className="mx-auto max-w-lg space-y-4 px-4 pb-4 pt-6">
      <header className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-teal-700/60">Calendar</p>
          <h1 className="mt-1 font-display text-3xl font-extrabold leading-none text-slate-900">캘린더</h1>
        </div>
        <div className="flex overflow-hidden rounded-lg border border-slate-300 text-sm">
          {(["month", "week", "day"] as View[]).map((v) => (
            <button key={v} onClick={() => setView(v)}
                    className={`px-3 py-2 transition-colors ${view === v ? "bg-slate-900 text-white" : "bg-white text-slate-600"}`}>
              {v === "month" ? "월" : v === "week" ? "주" : "일"}
            </button>
          ))}
        </div>
      </header>

      <div className="flex items-center justify-between">
        <button onClick={() => shift(-1)} className="px-3 py-2 text-slate-400">◀</button>
        <span className="font-display text-base font-bold text-slate-800">{title}</span>
        <button onClick={() => shift(1)} className="px-3 py-2 text-slate-400">▶</button>
      </div>

      {view === "month" && (
        <div className="rounded-2xl border border-stone-200/80 bg-white p-2 shadow-sm shadow-slate-200/50">
          <div className="grid grid-cols-7 pb-1 text-center text-xs text-slate-400">
            {DAY_NAMES.map((d) => <span key={d}>{d}</span>)}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: (start.getDay() + 6) % 7 }).map((_, i) => <span key={`b${i}`} />)}
            {Array.from({ length: end.getDate() }).map((_, i) => {
              const d = iso(new Date(anchor.getFullYear(), anchor.getMonth(), i + 1));
              const hasMeal = byDate(meals, "eaten_at", d).length > 0;
              const daySlots = byDate(slots, "date", d);
              const allTaken = daySlots.length > 0 && daySlots.every((s) => s.status === "taken");
              return (
                <button key={d}
                        onClick={() => { setAnchor(new Date(d)); setView("day"); }}
                        className="flex aspect-square flex-col items-center justify-center rounded-lg text-sm text-slate-700 transition-colors hover:bg-teal-50">
                  {i + 1}
                  <span className="flex h-1.5 gap-0.5">
                    {hasMeal && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />}
                    {daySlots.length > 0 && (
                      <span className={`h-1.5 w-1.5 rounded-full ${allTaken ? "bg-teal-600" : "bg-slate-300"}`} />
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {view === "week" && (
        <div className="space-y-2">
          {Array.from({ length: 7 }).map((_, i) => {
            const d = iso(addDays(start, i));
            const dayMeals = byDate(meals, "eaten_at", d);
            const daySlots = byDate(slots, "date", d) as Slot[];
            return (
              <button key={d} onClick={() => { setAnchor(new Date(d)); setView("day"); }}
                      className="w-full rounded-2xl border border-stone-200/80 bg-white p-3.5 text-left shadow-sm shadow-slate-200/50 transition-colors hover:bg-stone-50">
                <span className="text-sm font-medium text-slate-800">{d.slice(5)} ({DAY_NAMES[i]})</span>
                <p className="mt-1 text-xs text-slate-500">
                  식사 {dayMeals.length}회 · 영양제 {daySlots.filter((s) => s.status === "taken").length}/{daySlots.length}
                </p>
              </button>
            );
          })}
        </div>
      )}

      {view === "day" && (
        <DayDetail date={iso(anchor)}
                   meals={byDate(meals, "eaten_at", iso(anchor)) as MealOut[]}
                   slots={byDate(slots, "date", iso(anchor)) as Slot[]}
                   reload={reload} />
      )}
    </div>
  );
}
