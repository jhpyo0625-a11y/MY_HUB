import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

interface MealItemOut { id: number; name: string; amount: string; nutrient_source: string; }
interface MealOut { id: number; eaten_at: string; dish_name: string; items: MealItemOut[]; }
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
  const [items, setItems] = useState([{ name: "", amount: "" }]);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await api("/api/meals", {
        method: "POST",
        body: JSON.stringify({
          eaten_at: `${date}T${time}:00`,
          dish_name: dish,
          items: items.filter((i) => i.name.trim()),
        }),
      });
      onDone();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 space-y-3">
      <div className="flex gap-2">
        <input value={dish} onChange={(e) => setDish(e.target.value)}
               placeholder="음식 이름 (예: 김치찌개)"
               className="flex-1 border border-slate-300 rounded-lg px-3 py-2" />
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)}
               className="border border-slate-300 rounded-lg px-2" />
      </div>
      {items.map((it, idx) => (
        <div key={idx} className="flex gap-2">
          <input value={it.name} placeholder="재료"
                 onChange={(e) => setItems(items.map((x, i) => i === idx ? { ...x, name: e.target.value } : x))}
                 className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          <input value={it.amount} placeholder="양 (예: 100g, 반 모)"
                 onChange={(e) => setItems(items.map((x, i) => i === idx ? { ...x, amount: e.target.value } : x))}
                 className="w-32 border border-slate-200 rounded-lg px-3 py-2 text-sm" />
        </div>
      ))}
      <div className="flex gap-2">
        <button onClick={() => setItems([...items, { name: "", amount: "" }])}
                className="text-sm text-sky-600 py-2">+ 재료 추가</button>
        <button onClick={save} disabled={saving || !dish.trim()}
                className="ml-auto bg-sky-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-40">
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
    <div className="space-y-4">
      <section className="space-y-2">
        <h3 className="text-sm font-semibold text-slate-500">영양제</h3>
        {slots.length === 0 && <p className="text-sm text-slate-400">예정된 영양제가 없습니다</p>}
        {slots.map((s) => (
          <div key={s.schedule_id} className="bg-white rounded-xl shadow-sm p-3 flex items-center gap-2">
            <span className="text-sm">{s.time} · {s.supplement_name} {s.servings > 1 ? `×${s.servings}` : ""}</span>
            <div className="ml-auto flex gap-1">
              <button onClick={() => setIntake(s, "taken")}
                      className={`px-3 py-2 rounded-lg text-sm ${s.status === "taken" ? "bg-emerald-500 text-white" : "border border-slate-300"}`}>
                복용 ✓
              </button>
              <button onClick={() => setIntake(s, "skipped")}
                      className={`px-3 py-2 rounded-lg text-sm ${s.status === "skipped" ? "bg-slate-400 text-white" : "border border-slate-300"}`}>
                건너뜀
              </button>
            </div>
          </div>
        ))}
      </section>
      <section className="space-y-2">
        <div className="flex items-center">
          <h3 className="text-sm font-semibold text-slate-500">식사</h3>
          <button onClick={() => setAdding(!adding)} className="ml-auto text-sm text-sky-600 py-2">
            {adding ? "닫기" : "+ 식사 기록"}
          </button>
        </div>
        {adding && <AddMealForm date={date} onDone={() => { setAdding(false); reload(); }} />}
        {meals.map((m) => (
          <div key={m.id} className="bg-white rounded-xl shadow-sm p-3">
            <div className="flex items-center">
              <span className="font-medium">{m.eaten_at.slice(11, 16)} · {m.dish_name}</span>
              <button onClick={() => removeMeal(m.id)} className="ml-auto text-xs text-slate-400 py-2">삭제</button>
            </div>
            {m.items.length > 0 && (
              <p className="text-xs text-slate-500 mt-1">
                {m.items.map((i) => `${i.name}${i.nutrient_source === "ai_estimate" ? "*" : ""}`).join(", ")}
              </p>
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
    <div className="max-w-lg mx-auto px-4 pt-6 space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-bold">캘린더</h1>
        <div className="ml-auto flex rounded-lg border border-slate-300 overflow-hidden text-sm">
          {(["month", "week", "day"] as View[]).map((v) => (
            <button key={v} onClick={() => setView(v)}
                    className={`px-3 py-2 ${view === v ? "bg-sky-600 text-white" : "bg-white"}`}>
              {v === "month" ? "월" : v === "week" ? "주" : "일"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <button onClick={() => shift(-1)} className="px-3 py-2 text-slate-500">◀</button>
        <span className="font-medium">{title}</span>
        <button onClick={() => shift(1)} className="px-3 py-2 text-slate-500">▶</button>
      </div>

      {view === "month" && (
        <div className="bg-white rounded-xl shadow-sm p-2">
          <div className="grid grid-cols-7 text-center text-xs text-slate-400 pb-1">
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
                        className="aspect-square rounded-lg text-sm flex flex-col items-center justify-center hover:bg-sky-50">
                  {i + 1}
                  <span className="flex gap-0.5 h-1.5">
                    {hasMeal && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />}
                    {daySlots.length > 0 && (
                      <span className={`w-1.5 h-1.5 rounded-full ${allTaken ? "bg-sky-600" : "bg-slate-300"}`} />
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
                      className="w-full bg-white rounded-xl shadow-sm p-3 text-left">
                <span className="text-sm font-medium">{d.slice(5)} ({DAY_NAMES[i]})</span>
                <p className="text-xs text-slate-500 mt-1">
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
