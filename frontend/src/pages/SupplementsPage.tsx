import { useEffect, useState } from "react";
import { api } from "../api";

interface Ingredient { ingredient_code: string; amount: number; unit: string; }
interface Schedule { id?: number; days_of_week: string; time_of_day: string; servings: number; }
interface Supp {
  id: number; brand: string; product_name: string; serving_size: string;
  ingredients: Ingredient[]; schedules: Schedule[];
}

const DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"];
const INGREDIENT_SUGGESTIONS = [
  "vitamin_a", "vitamin_b1", "vitamin_b2", "vitamin_b6", "vitamin_b12",
  "vitamin_c", "vitamin_d", "vitamin_e", "vitamin_k", "folate", "niacin",
  "biotin", "calcium", "magnesium", "zinc", "iron", "selenium", "potassium",
  "omega3", "lutein", "probiotics", "coenzyme_q10", "milk_thistle",
];
const UNITS = ["mg", "ug", "IU", "g", "억CFU"];

const emptyForm = () => ({
  brand: "", product_name: "", serving_size: "1정",
  ingredients: [{ ingredient_code: "", amount: 0, unit: "mg" }] as Ingredient[],
  schedules: [{ days_of_week: "0123456", time_of_day: "09:00", servings: 1 }] as Schedule[],
});

function SuppForm({ initial, onSaved, onCancel }: {
  initial: (ReturnType<typeof emptyForm> & { id?: number });
  onSaved: () => void; onCancel: () => void;
}) {
  const [form, setForm] = useState(initial);
  const [saving, setSaving] = useState(false);

  function toggleDay(si: number, day: number) {
    const s = form.schedules[si];
    const has = s.days_of_week.includes(String(day));
    const days = has
      ? s.days_of_week.replace(String(day), "")
      : [...s.days_of_week, String(day)].sort().join("");
    setForm({
      ...form,
      schedules: form.schedules.map((x, i) => (i === si ? { ...x, days_of_week: days } : x)),
    });
  }

  async function save() {
    setSaving(true);
    try {
      const body = JSON.stringify({
        ...form,
        ingredients: form.ingredients.filter((i) => i.ingredient_code.trim()),
        schedules: form.schedules.filter((s) => s.days_of_week),
      });
      if (form.id)
        await api(`/api/supplements/${form.id}`, { method: "PUT", body });
      else await api("/api/supplements", { method: "POST", body });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 space-y-3">
      <div className="flex gap-2">
        <input value={form.brand} placeholder="브랜드"
               onChange={(e) => setForm({ ...form, brand: e.target.value })}
               className="w-28 border border-slate-300 rounded-lg px-3 py-2 text-sm" />
        <input value={form.product_name} placeholder="제품명 *"
               onChange={(e) => setForm({ ...form, product_name: e.target.value })}
               className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm" />
        <input value={form.serving_size} placeholder="1회 분량"
               onChange={(e) => setForm({ ...form, serving_size: e.target.value })}
               className="w-20 border border-slate-300 rounded-lg px-3 py-2 text-sm" />
      </div>

      <p className="text-xs font-semibold text-slate-500">성분 (1회 분량 기준)</p>
      <datalist id="ingredients">
        {INGREDIENT_SUGGESTIONS.map((s) => <option key={s} value={s} />)}
      </datalist>
      {form.ingredients.map((ing, idx) => (
        <div key={idx} className="flex gap-2">
          <input list="ingredients" value={ing.ingredient_code} placeholder="성분 (예: vitamin_d)"
                 onChange={(e) => setForm({ ...form, ingredients: form.ingredients.map((x, i) => i === idx ? { ...x, ingredient_code: e.target.value } : x) })}
                 className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          <input type="number" value={ing.amount || ""} placeholder="양"
                 onChange={(e) => setForm({ ...form, ingredients: form.ingredients.map((x, i) => i === idx ? { ...x, amount: Number(e.target.value) } : x) })}
                 className="w-20 border border-slate-200 rounded-lg px-3 py-2 text-sm" />
          <select value={ing.unit}
                  onChange={(e) => setForm({ ...form, ingredients: form.ingredients.map((x, i) => i === idx ? { ...x, unit: e.target.value } : x) })}
                  className="border border-slate-200 rounded-lg px-2 text-sm">
            {UNITS.map((u) => <option key={u}>{u}</option>)}
          </select>
          <button onClick={() => setForm({ ...form, ingredients: form.ingredients.filter((_, i) => i !== idx) })}
                  className="text-xs text-slate-400">✕</button>
        </div>
      ))}
      <button onClick={() => setForm({ ...form, ingredients: [...form.ingredients, { ingredient_code: "", amount: 0, unit: "mg" }] })}
              className="text-sm text-sky-600 py-1">+ 성분 추가</button>

      <p className="text-xs font-semibold text-slate-500">복용 스케줄</p>
      {form.schedules.map((s, si) => (
        <div key={si} className="space-y-2">
          <div className="flex gap-1">
            {DAY_NAMES.map((d, day) => (
              <button key={d} onClick={() => toggleDay(si, day)}
                      className={`w-9 h-9 rounded-full text-sm ${s.days_of_week.includes(String(day)) ? "bg-sky-600 text-white" : "border border-slate-300"}`}>
                {d}
              </button>
            ))}
          </div>
          <div className="flex gap-2 items-center">
            <input type="time" value={s.time_of_day}
                   onChange={(e) => setForm({ ...form, schedules: form.schedules.map((x, i) => i === si ? { ...x, time_of_day: e.target.value } : x) })}
                   className="border border-slate-200 rounded-lg px-2 py-1 text-sm" />
            <input type="number" min={1} value={s.servings}
                   onChange={(e) => setForm({ ...form, schedules: form.schedules.map((x, i) => i === si ? { ...x, servings: Number(e.target.value) } : x) })}
                   className="w-16 border border-slate-200 rounded-lg px-2 py-1 text-sm" />
            <span className="text-xs text-slate-500">회분</span>
            <button onClick={() => setForm({ ...form, schedules: form.schedules.filter((_, i) => i !== si) })}
                    className="text-xs text-slate-400">✕</button>
          </div>
        </div>
      ))}
      <button onClick={() => setForm({ ...form, schedules: [...form.schedules, { days_of_week: "0123456", time_of_day: "09:00", servings: 1 }] })}
              className="text-sm text-sky-600 py-1">+ 스케줄 추가</button>

      <div className="flex gap-2 pt-2">
        <button onClick={onCancel} className="flex-1 border border-slate-300 rounded-lg py-2 text-sm">취소</button>
        <button onClick={save} disabled={saving || !form.product_name.trim()}
                className="flex-1 bg-sky-600 text-white rounded-lg py-2 text-sm disabled:opacity-40">
          저장
        </button>
      </div>
    </div>
  );
}

export default function SupplementsPage() {
  const [supps, setSupps] = useState<Supp[]>([]);
  const [editing, setEditing] = useState<(ReturnType<typeof emptyForm> & { id?: number }) | null>(null);

  const reload = () => api<Supp[]>("/api/supplements").then(setSupps);
  useEffect(() => { reload(); }, []);

  async function remove(id: number) {
    if (!confirm("이 영양제를 목록에서 제거할까요? 복용 기록은 유지됩니다.")) return;
    await api(`/api/supplements/${id}`, { method: "DELETE" });
    reload();
  }

  return (
    <div className="max-w-lg mx-auto px-4 pt-6 space-y-4">
      <div className="flex items-center">
        <h1 className="text-xl font-bold">영양제 관리</h1>
        <button onClick={() => setEditing(emptyForm())}
                className="ml-auto bg-sky-600 text-white rounded-lg px-4 py-2 text-sm">
          + 추가
        </button>
      </div>

      {editing && (
        <SuppForm initial={editing}
                  onSaved={() => { setEditing(null); reload(); }}
                  onCancel={() => setEditing(null)} />
      )}

      {supps.map((s) => (
        <div key={s.id} className="bg-white rounded-xl shadow-sm p-4">
          <div className="flex items-start">
            <div>
              <p className="font-medium">{s.product_name}</p>
              <p className="text-xs text-slate-500">{s.brand} · {s.serving_size}</p>
            </div>
            <div className="ml-auto flex gap-3 text-sm">
              <button onClick={() => setEditing({ ...s })} className="text-sky-600 py-2">수정</button>
              <button onClick={() => remove(s.id)} className="text-slate-400 py-2">제거</button>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            {s.ingredients.map((i) => `${i.ingredient_code} ${i.amount}${i.unit}`).join(" · ")}
          </p>
          {s.schedules.map((sc, i) => (
            <p key={i} className="text-xs text-slate-400 mt-1">
              {[...sc.days_of_week].map((d) => DAY_NAMES[Number(d)]).join(",")} {sc.time_of_day}
              {sc.servings > 1 ? ` ×${sc.servings}` : ""}
            </p>
          ))}
        </div>
      ))}
      {supps.length === 0 && !editing && (
        <p className="text-sm text-slate-400 text-center pt-8">
          영양제를 추가하면 캘린더와 복용 알림에 반영됩니다
        </p>
      )}
    </div>
  );
}
