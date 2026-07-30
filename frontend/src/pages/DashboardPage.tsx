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

const WARNING_STYLE: Record<string, { cls: string; icon: string }> = {
  overdose: { cls: "bg-rose-50 text-rose-800 border-rose-200", icon: "⚠" },
  duplication: { cls: "bg-amber-50 text-amber-800 border-amber-200", icon: "⧉" },
  interaction: { cls: "bg-amber-50 text-amber-800 border-amber-200", icon: "⚠" },
};

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="font-display text-base font-bold tracking-tight text-slate-800">
      {children}
    </h2>
  );
}

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
    <div className="rounded-2xl border border-stone-200/80 bg-white p-5 shadow-sm shadow-slate-200/50">
      <p className="font-display text-base font-bold text-slate-800">{def.name_ko}</p>
      <p className="mt-1 text-sm leading-relaxed text-slate-500">{item.why_it_matters}</p>
      {def.input_type === "scale" ? (
        <div className="mt-3 flex gap-2">
          {["없음", "가끔", "자주", "심함"].map((label, i) => (
            <button key={i} disabled={saving} onClick={() => save(i, null)}
                    className="flex-1 rounded-lg border border-slate-300 py-2 text-sm transition-colors active:bg-sky-50">
              {label}
            </button>
          ))}
        </div>
      ) : (
        <div className="mt-3 flex gap-2">
          <input
            type={def.input_type === "number" ? "number" : "text"}
            inputMode={def.input_type === "number" ? "decimal" : undefined}
            value={input} onChange={(e) => setInput(e.target.value)}
            placeholder={def.unit || "입력"}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button disabled={saving || !input}
                  onClick={() => def.input_type === "number" ? save(Number(input), null) : save(null, input)}
                  className="rounded-lg bg-slate-900 px-4 text-sm text-white transition-colors hover:bg-slate-800 disabled:opacity-40">
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
    <div className="mx-auto max-w-lg space-y-5 px-4 pb-4 pt-6">
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-teal-700/60">Today</p>
        <h1 className="mt-1 font-display text-3xl font-extrabold leading-none text-slate-900">대시보드</h1>
      </header>

      {warnings.length > 0 && (
        <section className="space-y-2">
          {warnings.map((w, i) => {
            const s = WARNING_STYLE[w.type] ?? { cls: "bg-slate-50 text-slate-700 border-slate-200", icon: "•" };
            return (
              <div key={i} className={`reveal flex items-start gap-2.5 rounded-2xl border p-3.5 text-sm leading-relaxed ${s.cls}`}>
                <span className="mt-0.5 shrink-0 text-base leading-none">{s.icon}</span>
                <span>{w.message}</span>
              </div>
            );
          })}
        </section>
      )}

      {slots.length > 0 && (
        <section className="space-y-2.5">
          <SectionTitle>오늘의 영양제</SectionTitle>
          {slots.map((s) => (
            <div key={s.schedule_id}
                 className="flex items-center gap-3 rounded-2xl border border-stone-200/80 bg-white p-3.5 shadow-sm shadow-slate-200/50">
              <span className="font-mono text-sm text-slate-400 tabular-nums">{s.time}</span>
              <span className="text-sm font-medium text-slate-800">
                {s.supplement_name}
                {s.servings > 1 ? <span className="text-slate-400"> ×{s.servings}</span> : null}
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
      )}

      {detail ? (
        <div className="space-y-5">
          <section className="reveal rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-teal-900 p-6 text-white shadow-lg shadow-slate-900/20">
            <p className="font-mono text-[11px] tracking-wider text-teal-300/80">건강 상태 요약</p>
            <p className="mt-2 font-display text-xl leading-relaxed">{detail.summary}</p>
          </section>
          {detail.top3.length > 0 && (
            <section className="space-y-3">
              <SectionTitle>
                부족 영양소 <span className="font-mono text-teal-700">TOP 3</span>
              </SectionTitle>
              <div className="space-y-3">
                {detail.top3.map((e, i) => (
                  <div key={i} className="reveal" style={{ animationDelay: `${i * 80}ms` }}>
                    <Top3Card entry={e} rank={i + 1} evidence={detail.evidence} />
                  </div>
                ))}
              </div>
            </section>
          )}
          {detail.missing_data.length > 0 && (
            <section className="space-y-2.5">
              <SectionTitle>추가로 알려주시면 좋아요</SectionTitle>
              {detail.missing_data.map((m, i) => (
                <MissingDataCard key={i} item={m} def={defByCode[m.metric_code]} onSaved={reload} />
              ))}
            </section>
          )}
        </div>
      ) : (
        <div className="py-16 text-center">
          <p className="mb-3 font-display text-5xl text-slate-200">◍</p>
          <p className="text-sm leading-relaxed text-slate-400">
            아직 분석 기록이 없습니다.<br />리포트 탭에서 분석하기를 눌러보세요.
          </p>
        </div>
      )}
    </div>
  );
}
