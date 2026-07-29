import { useEffect, useState } from "react";
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
export interface AnalysisDetail {
  id: number; run_at: string; trigger: string; summary: string;
  deficiencies: NutrientNote[]; excesses: NutrientNote[];
  top3: Top3Entry[]; missing_data: MissingDataItem[];
}
interface AnalysisListItem { id: number; run_at: string; trigger: string; summary: string; }

const GRADE_LABEL: Record<string, string> = { high: "높음", med: "중간", low: "낮음" };
const ACTION_LABEL: Record<string, string> = { food: "음식", recipe: "레시피", habit: "습관" };

export function Top3Card({ entry }: { entry: Top3Entry }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-4 space-y-2">
      <p className="font-medium">{entry.nutrient}</p>
      <p className="text-sm text-slate-500">{entry.why}</p>
      <ul className="space-y-1">
        {entry.actions.map((a, i) => (
          <li key={i} className="text-sm">
            <span className="text-xs text-sky-600 font-semibold mr-1">
              [{ACTION_LABEL[a.type] ?? a.type}]
            </span>
            {a.text}{a.portion ? ` (${a.portion})` : ""}
          </li>
        ))}
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
    <div className="max-w-lg mx-auto px-4 pt-6 space-y-4">
      <div className="flex items-center">
        <h1 className="text-xl font-bold">리포트</h1>
        <button onClick={runAnalysis} disabled={running}
                className="ml-auto bg-sky-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-40">
          {running ? "분석 중..." : "분석하기"}
        </button>
      </div>
      <p className="text-xs text-slate-400">의학적 진단이 아닙니다. 참고용 정보입니다.</p>
      {error && <p className="text-sm text-red-500">{error}</p>}

      {detail ? (
        <>
          <div className="bg-white rounded-xl shadow-sm p-4">
            <p className="text-xs text-slate-400">{detail.run_at.slice(0, 16).replace("T", " ")}</p>
            <p className="mt-1">{detail.summary}</p>
          </div>

          {detail.top3.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-500">부족 영양소 TOP 3</h2>
              {detail.top3.map((e, i) => <Top3Card key={i} entry={e} />)}
            </section>
          )}

          {detail.deficiencies.length > 0 && (
            <section className="bg-white rounded-xl shadow-sm p-4 space-y-1">
              <h2 className="text-sm font-semibold text-slate-500">부족 가능성</h2>
              {detail.deficiencies.map((d, i) => (
                <p key={i} className="text-sm">{d.nutrient} · 신뢰도 {GRADE_LABEL[d.confidence] ?? d.confidence}</p>
              ))}
            </section>
          )}

          {detail.excesses.length > 0 && (
            <section className="bg-white rounded-xl shadow-sm p-4 space-y-1">
              <h2 className="text-sm font-semibold text-slate-500">과다 가능성</h2>
              {detail.excesses.map((d, i) => (
                <p key={i} className="text-sm">{d.nutrient} · 신뢰도 {GRADE_LABEL[d.confidence] ?? d.confidence}</p>
              ))}
            </section>
          )}
        </>
      ) : (
        <p className="text-sm text-slate-400 text-center pt-8">
          아직 분석 기록이 없습니다. 분석하기 버튼을 눌러보세요.
        </p>
      )}

      {history.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-slate-500">지난 리포트</h2>
          {history.map((h) => (
            <button key={h.id}
                    onClick={() => api<AnalysisDetail>(`/api/analysis/${h.id}`).then(setDetail)}
                    className="w-full text-left bg-white rounded-xl shadow-sm p-3">
              <p className="text-xs text-slate-400">{h.run_at.slice(0, 16).replace("T", " ")}</p>
              <p className="text-sm truncate">{h.summary}</p>
            </button>
          ))}
        </section>
      )}
    </div>
  );
}
