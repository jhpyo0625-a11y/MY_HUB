import { useEffect, useState } from "react";
import { api } from "../api";
import { PhotoUploadButton, photoUrl } from "../PhotoUpload";

interface Ingredient { ingredient_code: string; amount: number; unit: string; }
interface Schedule { id?: number; days_of_week: string; time_of_day: string; servings: number; }
interface Supp {
  id: number; brand: string; product_name: string; serving_size: string;
  photo_path: string | null;
  ingredients: Ingredient[]; schedules: Schedule[];
}
interface LabelExtract {
  brand?: string; product_name?: string; serving_size?: string;
  ingredients?: Ingredient[];
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
  photo_path: null as string | null,
  ingredients: [{ ingredient_code: "", amount: 0, unit: "mg" }] as Ingredient[],
  schedules: [{ days_of_week: "0123456", time_of_day: "09:00", servings: 1 }] as Schedule[],
});

function SuppForm({ initial, onSaved, onCancel }: {
  initial: (ReturnType<typeof emptyForm> & { id?: number });
  onSaved: () => void; onCancel: () => void;
}) {
  const [form, setForm] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function applyExtract(result: {
    photo_path: string; extracted: LabelExtract | null; error: string | null;
  }) {
    setForm((f) => ({
      ...f,
      photo_path: result.photo_path,
      brand: result.extracted?.brand ?? f.brand,
      product_name: result.extracted?.product_name ?? f.product_name,
      serving_size: result.extracted?.serving_size ?? f.serving_size,
      ingredients: result.extracted?.ingredients?.length
        ? result.extracted.ingredients
        : f.ingredients,
    }));
  }

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
    setError(null);
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
    } catch {
      setError("저장에 실패했어요. 다시 시도해주세요.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3 rounded-2xl border border-stone-200/80 bg-white p-5 shadow-sm shadow-slate-200/50">
      <div className="flex items-center gap-2">
        <PhotoUploadButton kind="supplement_label" label="라벨 사진" onExtracted={applyExtract} />
        {form.photo_path && (
          <img src={photoUrl(form.photo_path)} className="h-12 w-12 rounded-lg object-cover" />
        )}
      </div>

      <div className="flex gap-2">
        <input value={form.brand} placeholder="브랜드"
               onChange={(e) => setForm({ ...form, brand: e.target.value })}
               className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none" />
        <input value={form.product_name} placeholder="제품명 *"
               onChange={(e) => setForm({ ...form, product_name: e.target.value })}
               className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none" />
        <input value={form.serving_size} placeholder="1회 분량"
               onChange={(e) => setForm({ ...form, serving_size: e.target.value })}
               className="w-20 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none" />
      </div>

      <p className="text-xs font-semibold text-slate-500">성분 (1회 분량 기준)</p>
      <datalist id="ingredients">
        {INGREDIENT_SUGGESTIONS.map((s) => <option key={s} value={s} />)}
      </datalist>
      {form.ingredients.map((ing, idx) => (
        <div key={idx} className="flex gap-2">
          <input list="ingredients" value={ing.ingredient_code} placeholder="성분 (예: vitamin_d)"
                 onChange={(e) => setForm({ ...form, ingredients: form.ingredients.map((x, i) => i === idx ? { ...x, ingredient_code: e.target.value } : x) })}
                 className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none" />
          <input type="number" value={ing.amount || ""} placeholder="양"
                 onChange={(e) => setForm({ ...form, ingredients: form.ingredients.map((x, i) => i === idx ? { ...x, amount: Number(e.target.value) } : x) })}
                 className="w-20 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none" />
          <select value={ing.unit}
                  onChange={(e) => setForm({ ...form, ingredients: form.ingredients.map((x, i) => i === idx ? { ...x, unit: e.target.value } : x) })}
                  className="rounded-lg border border-slate-200 px-2 text-sm">
            {UNITS.map((u) => <option key={u}>{u}</option>)}
          </select>
          <button onClick={() => setForm({ ...form, ingredients: form.ingredients.filter((_, i) => i !== idx) })}
                  className="text-xs text-slate-400">✕</button>
        </div>
      ))}
      <button onClick={() => setForm({ ...form, ingredients: [...form.ingredients, { ingredient_code: "", amount: 0, unit: "mg" }] })}
              className="py-1 text-sm font-medium text-teal-700">+ 성분 추가</button>

      <p className="text-xs font-semibold text-slate-500">복용 스케줄</p>
      {form.schedules.map((s, si) => (
        <div key={si} className="space-y-2">
          <div className="flex gap-1">
            {DAY_NAMES.map((d, day) => (
              <button key={d} onClick={() => toggleDay(si, day)}
                      className={`h-9 w-9 rounded-full text-sm transition-colors ${s.days_of_week.includes(String(day)) ? "bg-slate-900 text-white" : "border border-slate-300 text-slate-600"}`}>
                {d}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <input type="time" value={s.time_of_day}
                   onChange={(e) => setForm({ ...form, schedules: form.schedules.map((x, i) => i === si ? { ...x, time_of_day: e.target.value } : x) })}
                   className="rounded-lg border border-slate-200 px-2 py-1 text-sm" />
            <input type="number" min={1} value={s.servings}
                   onChange={(e) => setForm({ ...form, schedules: form.schedules.map((x, i) => i === si ? { ...x, servings: Number(e.target.value) } : x) })}
                   className="w-16 rounded-lg border border-slate-200 px-2 py-1 text-sm" />
            <span className="text-xs text-slate-500">회분</span>
            <button onClick={() => setForm({ ...form, schedules: form.schedules.filter((_, i) => i !== si) })}
                    className="text-xs text-slate-400">✕</button>
          </div>
        </div>
      ))}
      <button onClick={() => setForm({ ...form, schedules: [...form.schedules, { days_of_week: "0123456", time_of_day: "09:00", servings: 1 }] })}
              className="py-1 text-sm font-medium text-teal-700">+ 스케줄 추가</button>

      <div className="flex gap-2 pt-2">
        <button onClick={onCancel} className="flex-1 rounded-full border border-slate-300 py-2 text-sm text-slate-600">취소</button>
        <button onClick={save} disabled={saving || !form.product_name.trim()}
                className="flex-1 rounded-full bg-slate-900 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-40">
          저장
        </button>
      </div>
      {error && <p className="text-sm text-rose-600">{error}</p>}
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
    <div className="mx-auto max-w-lg space-y-4 px-4 pb-4 pt-6">
      <header className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-teal-700/60">Supplements</p>
          <h1 className="mt-1 font-display text-3xl font-extrabold leading-none text-slate-900">영양제</h1>
        </div>
        <button onClick={() => setEditing(emptyForm())}
                className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-800">
          + 추가
        </button>
      </header>

      {editing && (
        <SuppForm initial={editing}
                  onSaved={() => { setEditing(null); reload(); }}
                  onCancel={() => setEditing(null)} />
      )}

      {supps.map((s) => (
        <div key={s.id} className="rounded-2xl border border-stone-200/80 bg-white p-5 shadow-sm shadow-slate-200/50">
          <div className="flex items-start gap-3">
            {s.photo_path && (
              <img src={photoUrl(s.photo_path)} className="h-12 w-12 rounded-lg object-cover" />
            )}
            <div>
              <p className="font-display text-lg font-bold text-slate-900">{s.product_name}</p>
              <p className="text-xs text-slate-500">{s.brand} · {s.serving_size}</p>
            </div>
            <div className="ml-auto flex gap-3 text-sm">
              <button onClick={() => setEditing({ ...s })} className="py-2 font-medium text-teal-700">수정</button>
              <button onClick={() => remove(s.id)} className="py-2 text-slate-400">제거</button>
            </div>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {s.ingredients.map((i) => `${i.ingredient_code} ${i.amount}${i.unit}`).join(" · ")}
          </p>
          {s.schedules.map((sc, i) => (
            <p key={i} className="mt-1 text-xs text-slate-400">
              <span className="font-mono">{[...sc.days_of_week].map((d) => DAY_NAMES[Number(d)]).join(",")} {sc.time_of_day}</span>
              {sc.servings > 1 ? ` ×${sc.servings}` : ""}
            </p>
          ))}
        </div>
      ))}
      {supps.length === 0 && !editing && (
        <p className="pt-8 text-center text-sm text-slate-400">
          영양제를 추가하면 캘린더와 복용 알림에 반영됩니다
        </p>
      )}
    </div>
  );
}
