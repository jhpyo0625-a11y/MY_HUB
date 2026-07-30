import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api";

interface Action {
  type: string; text: string; portion?: string | null;
  uses_frequent_ingredients?: boolean | null;
}
export interface Top3Entry {
  nutrient: string; why: string; actions: Action[]; evidence_ids: number[];
}
interface NutrientNote { nutrient: string; confidence: string; evidence_ids: number[]; }
interface MissingDataItem { metric_code: string; why_it_matters: string; }
export interface EvidenceRef {
  id: number; type: string; nutrient_code: string;
  claim_summary: string; source_url: string; reliability_grade: string;
}
export interface AnalysisDetail {
  id: number; run_at: string; trigger: string; summary: string;
  deficiencies: NutrientNote[]; excesses: NutrientNote[];
  top3: Top3Entry[]; missing_data: MissingDataItem[];
  evidence?: Record<string, EvidenceRef>;
}
interface AnalysisListItem { id: number; run_at: string; trigger: string; summary: string; }

const CONFIDENCE: Record<string, { label: string; cls: string }> = {
  high: { label: "높음", cls: "bg-emerald-50 text-emerald-700 ring-emerald-600/20" },
  med: { label: "중간", cls: "bg-amber-50 text-amber-700 ring-amber-600/20" },
  low: { label: "낮음", cls: "bg-slate-100 text-slate-600 ring-slate-500/20" },
};
const GRADE_CLS: Record<string, string> = {
  A: "bg-emerald-600 text-white",
  B: "bg-amber-500 text-white",
  C: "bg-slate-400 text-white",
};
const ACTION: Record<string, { label: string; cls: string }> = {
  food: { label: "음식", cls: "bg-emerald-50 text-emerald-700" },
  recipe: { label: "레시피", cls: "bg-teal-50 text-teal-700" },
  habit: { label: "습관", cls: "bg-sky-50 text-sky-700" },
};
const EVIDENCE_TYPE_LABEL: Record<string, string> = {
  KDRI: "KDRI", NIH_ODS: "NIH ODS", UL: "UL", interaction_rule: "상호작용",
};

const fmtDate = (iso: string) => iso.slice(0, 16).replace("T", " ");

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="font-display text-base font-bold tracking-tight text-slate-800">
      {children}
    </h2>
  );
}

export function EvidenceBadges({ ids, evidence }: {
  ids: number[]; evidence?: Record<string, EvidenceRef>;
}) {
  if (!evidence) return null;
  const refs = ids.map((id) => evidence[String(id)]).filter(Boolean);
  if (refs.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {refs.map((r) => {
        const grade = GRADE_CLS[r.reliability_grade] ?? "bg-slate-400 text-white";
        const label = EVIDENCE_TYPE_LABEL[r.type] ?? r.type;
        const body = (
          <>
            <span className={`font-mono text-[10px] font-semibold leading-none rounded px-1 py-0.5 ${grade}`}>
              {r.reliability_grade}
            </span>
            <span className="text-[11px] text-slate-500">{label}</span>
            {r.source_url && <span className="text-[11px] text-slate-400">↗</span>}
          </>
        );
        return r.source_url ? (
          <a key={r.id} href={r.source_url} target="_blank" rel="noreferrer"
             title={r.claim_summary}
             className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1 transition-colors hover:border-slate-300 hover:bg-slate-50">
            {body}
          </a>
        ) : (
          <span key={r.id} title={r.claim_summary}
                className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1">
            {body}
          </span>
        );
      })}
    </div>
  );
}

export function Top3Card({ entry, rank, evidence }: {
  entry: Top3Entry; rank?: number; evidence?: Record<string, EvidenceRef>;
}) {
  return (
    <article className="rounded-2xl border border-stone-200/80 bg-white p-5 shadow-sm shadow-slate-200/50">
      <header className="flex items-baseline gap-3">
        {rank != null && (
          <span className="font-mono text-2xl font-semibold leading-none text-teal-700/30 tabular-nums">
            {String(rank).padStart(2, "0")}
          </span>
        )}
        <h3 className="font-display text-xl font-bold leading-tight text-slate-900">
          {entry.nutrient}
        </h3>
        <span className="ml-auto inline-flex items-center gap-1.5 text-xs font-medium text-rose-600">
          <span className="h-1.5 w-1.5 rounded-full bg-rose-500" /> 부족
        </span>
      </header>
      <p className="mt-1.5 text-sm leading-relaxed text-slate-500">{entry.why}</p>
      <ul className="mt-4 space-y-2.5">
        {entry.actions.map((a, i) => {
          const cat = ACTION[a.type] ?? { label: a.type, cls: "bg-slate-100 text-slate-600" };
          return (
            <li key={i} className="flex items-start gap-2.5 text-sm text-slate-700">
              <span className={`mt-0.5 shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${cat.cls}`}>
                {cat.label}
              </span>
              <span className="leading-snug">
                {a.text}
                {a.portion ? <span className="text-slate-400"> · {a.portion}</span> : null}
              </span>
            </li>
          );
        })}
      </ul>
      {entry.evidence_ids.length > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-3">
          <EvidenceBadges ids={entry.evidence_ids} evidence={evidence} />
        </div>
      )}
    </article>
  );
}

function NoteCard({ title, notes, evidence, tone }: {
  title: string; notes: NutrientNote[]; evidence?: Record<string, EvidenceRef>;
  tone: "rose" | "amber";
}) {
  const dot = tone === "rose" ? "bg-rose-400" : "bg-amber-400";
  return (
    <div className="reveal rounded-2xl border border-stone-200/80 bg-white p-5 shadow-sm shadow-slate-200/50">
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
        <h3 className="font-display text-base font-bold text-slate-800">{title}</h3>
      </div>
      <ul className="mt-3 space-y-3">
        {notes.map((n, i) => {
          const c = CONFIDENCE[n.confidence] ?? CONFIDENCE.low;
          return (
            <li key={i} className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-slate-800">{n.nutrient}</span>
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${c.cls}`}>
                신뢰도 {c.label}
              </span>
              <span className="ml-auto">
                <EvidenceBadges ids={n.evidence_ids} evidence={evidence} />
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function ReportPage() {
  const [detail, setDetail] = useState<AnalysisDetail | null>(null);
  const [history, setHistory] = useState<AnalysisListItem[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  function loadLatest() {
    api<AnalysisDetail | null>("/api/analysis/latest").then(setDetail);
  }
  function loadHistory() {
    api<AnalysisListItem[]>("/api/analysis").then(setHistory);
  }
  useEffect(() => { loadLatest(); loadHistory(); }, []);

  async function runAnalysis() {
    setRunning(true);
    setError("");
    try {
      const result = await api<AnalysisDetail>("/api/analysis/run", { method: "POST" });
      setDetail(result);
      loadHistory();
    } catch {
      setError("분석에 실패했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-5 px-4 pb-4 pt-6">
      <header className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-teal-700/60">
            Analysis
          </p>
          <h1 className="mt-1 font-display text-3xl font-extrabold leading-none text-slate-900">
            리포트
          </h1>
        </div>
        <button onClick={runAnalysis} disabled={running}
                className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-slate-800 disabled:opacity-40">
          {running ? "분석 중…" : "분석하기"}
        </button>
      </header>

      <p className="border-l-2 border-slate-200 pl-2 text-xs text-slate-400">
        의학적 진단이 아닙니다. 참고용 정보입니다.
      </p>
      {error && (
        <p className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </p>
      )}

      {detail ? (
        <div className="space-y-5">
          <section className="reveal rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-teal-900 p-6 text-white shadow-lg shadow-slate-900/20">
            <p className="font-mono text-[11px] tracking-wider text-teal-300/80">
              {fmtDate(detail.run_at)}
            </p>
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

          {(detail.deficiencies.length > 0 || detail.excesses.length > 0) && (
            <section className="space-y-3">
              {detail.deficiencies.length > 0 && (
                <NoteCard title="부족 가능성" notes={detail.deficiencies}
                          evidence={detail.evidence} tone="rose" />
              )}
              {detail.excesses.length > 0 && (
                <NoteCard title="과다 가능성" notes={detail.excesses}
                          evidence={detail.evidence} tone="amber" />
              )}
            </section>
          )}
        </div>
      ) : (
        <div className="py-16 text-center">
          <p className="mb-3 font-display text-5xl text-slate-200">◍</p>
          <p className="text-sm leading-relaxed text-slate-400">
            아직 분석 기록이 없습니다.<br />분석하기 버튼을 눌러보세요.
          </p>
        </div>
      )}

      {history.length > 0 && (
        <section className="space-y-2 pt-2">
          <SectionTitle>지난 리포트</SectionTitle>
          <div className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white">
            {history.map((h) => (
              <button key={h.id}
                      onClick={() => api<AnalysisDetail>(`/api/analysis/${h.id}`).then(setDetail)}
                      className="w-full px-4 py-3 text-left transition-colors hover:bg-slate-50">
                <p className="font-mono text-[11px] text-slate-400">{fmtDate(h.run_at)}</p>
                <p className="mt-0.5 truncate text-sm text-slate-700">{h.summary}</p>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
