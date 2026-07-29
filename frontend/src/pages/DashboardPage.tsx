import { useEffect, useState } from "react";
import { api } from "../api";
import { Top3Card, type AnalysisDetail } from "./ReportPage";

interface Warning {
  type: string; ingredient_code?: string; ingredient_codes?: string[]; message: string;
}
interface Slot {
  date: string; time: string; schedule_id: number; supplement_id: number;
  supplement_name: string; servings: number; status: "taken" | "skipped" | "pending";
}
interface MetricDef {
  code: string; name_ko: string; unit: string; domain: string;
  input_type: string; range_low: number | null; range_high: number | null;
}

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const WARNING_STYLE: Record<string, string> = {
  overdose: "bg-red-50 text-red-700 border-red-200",
  duplication: "bg-amber-50 text-amber-700 border-amber-200",
  interaction: "bg-amber-50 text-amber-700 border-amber-200",
};

function MissingDataCard({ item, def, onSaved }: {
  item: { metric_code: string; why_it_matters: string };
  def: MetricDef | undefined;
  onSaved: () => void;
}) {
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);
  if (!def) return null;

  async function save(valueNum: number | null, valueText: string | null) {
    setSaving(true);
    try {
      await api("/api/metrics/entries", {
        method: "POST",
        body: JSON.stringify({ metric_code: def!.code, value_num: valueNum, value_text: valueText }),
      });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 space-y-2">
      <p className="font-medium">{def.name_ko}</p>
      <p className="text-sm text-slate-500">{item.why_it_matters}</p>
      {def.input_type === "scale" ? (
        <div className="flex gap-2">
          {["없음", "가끔", "자주", "심함"].map((label, i) => (
            <button key={i} disabled={saving} onClick={() => save(i, null)}
                    className="flex-1 py-2 rounded-lg border border-slate-300 text-sm active:bg-sky-50">
              {label}
            </button>
          ))}
        </div>
      ) : (
        <div className="flex gap-2">
          <input
            type={def.input_type === "number" ? "number" : "text"}
            inputMode={def.input_type === "number" ? "decimal" : undefined}
            value={input} onChange={(e) => setInput(e.target.value)}
            placeholder={def.unit || "입력"}
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm" />
          <button disabled={saving || !input}
                  onClick={() => def.input_type === "number" ? save(Number(input), null) : save(null, input)}
                  className="bg-sky-600 text-white rounded-lg px-4 text-sm disabled:opacity-40">
            저장
          </button>
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);
  const [warnings, setWarnings] = useState<Warning[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [defs, setDefs] = useState<MetricDef[]>([]);
  const today = iso(new Date());

  function reload() {
    api<AnalysisDetail | null>("/api/analysis/latest").then(setDetail);
    api<Warning[]>("/api/safety/warnings").then(setWarnings);
    api<{ supplement_slots: Slot[] }>(`/api/calendar?start=${today}&end=${today}`)
      .then((d) => setSlots(d.supplement_slots));
  }
  useEffect(() => {
    reload();
    api<MetricDef[]>("/api/metrics/definitions").then(setDefs);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function setIntake(slot: Slot, status: "taken" | "skipped") {
    await api("/api/intake", {
      method: "POST",
      body: JSON.stringify({ schedule_id: slot.schedule_id, date: today, status }),
    });
    reload();
  }

  const defByCode = Object.fromEntries(defs.map((d) => [d.code, d]));

  return (
    <div className="max-w-lg mx-auto px-4 pt-6 space-y-4">
      <h1 className="text-xl font-bold">대시보드</h1>

      {warnings.length > 0 && (
        <section className="space-y-2">
          {warnings.map((w, i) => (
            <div key={i}
                className={`rounded-xl border p-3 text-sm ${WARNING_STYLE[w.type] ?? "bg-slate-50 border-slate-200"}`}>
              {w.message}
            </div>
          ))}
        </section>
      )}

      {slots.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-slate-500">오늘의 영양제</h2>
          {slots.map((s) => (
            <div key={s.schedule_id} className="bg-white rounded-xl shadow-sm p-3 flex items-center gap-2">
              <span className="text-sm">{s.time} · {s.supplement_name}</span>
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
      )}

      {detail ? (
        <>
          <div className="bg-white rounded-xl shadow-sm p-4">
            <p className="text-xs text-slate-400">건강 상태 요약</p>
            <p className="mt-1">{detail.summary}</p>
          </div>
          {detail.top3.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-500">부족 영양소 TOP 3</h2>
              {detail.top3.map((e, i) => <Top3Card key={i} entry={e} />)}
            </section>
          )}
          {detail.missing_data.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-500">추가로 알려주시면 좋아요</h2>
              {detail.missing_data.map((m, i) => (
                <MissingDataCard key={i} item={m} def={defByCode[m.metric_code]} onSaved={reload} />
              ))}
            </section>
          )}
        </>
      ) : (
        <p className="text-sm text-slate-400 text-center pt-8">
          아직 분석 기록이 없습니다. 리포트 탭에서 분석하기를 눌러보세요.
        </p>
      )}
    </div>
  );
}
