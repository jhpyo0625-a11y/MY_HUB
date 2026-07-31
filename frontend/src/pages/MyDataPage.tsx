import { useEffect, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { PhotoUploadButton } from "../PhotoUpload";

interface MetricDef {
  code: string; name_ko: string; unit: string; domain: string;
  input_type: string; range_low: number | null; range_high: number | null;
}
interface Entry {
  id: number; metric_code: string; value_num: number | null;
  value_text: string | null; measured_at: string;
}
type Latest = Record<string, { value_num: number | null; value_text: string | null; measured_at: string }>;

const DOMAIN_LABELS: Record<string, string> = {
  body: "신체 기본", lab: "혈액검사", lifestyle: "생활습관", symptom: "증상",
};
const DOMAIN_ORDER = ["body", "lab", "lifestyle", "symptom"];
const SCALE_LABELS = ["없음", "가끔", "자주", "심함"];

function HistoryChart({ def, entries }: { def: MetricDef; entries: Entry[] }) {
  const data = entries
    .filter((e) => e.value_num !== null)
    .map((e) => ({ x: e.measured_at.slice(5, 10), y: e.value_num }))
    .reverse();
  if (data.length < 2)
    return <p className="py-3 text-sm text-slate-400">기록이 2개 이상이면 그래프가 표시됩니다</p>;
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#e7e5e4" vertical={false} />
        <XAxis dataKey="x" tick={{ fontSize: 11, fill: "#78716c" }}
               tickLine={false} axisLine={{ stroke: "#e7e5e4" }} />
        <YAxis tick={{ fontSize: 11, fill: "#78716c" }} tickLine={false}
               axisLine={false} width={40} domain={["auto", "auto"]} />
        <Tooltip formatter={(v) => [`${v} ${def.unit}`, def.name_ko]} />
        {def.range_low !== null && def.range_high !== null && (
          <ReferenceArea y1={def.range_low} y2={def.range_high}
                         fill="#10b981" fillOpacity={0.08} />
        )}
        <Line type="monotone" dataKey="y" stroke="#0f766e" strokeWidth={2}
              dot={{ r: 3, fill: "#0f766e" }} activeDot={{ r: 5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function MetricRow({ def, latest, onSaved }: {
  def: MetricDef;
  latest: Latest[string] | undefined;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && def.input_type !== "text")
      api<Entry[]>(`/api/metrics/entries?code=${def.code}`).then(setEntries);
  }, [open, def]);

  async function save(valueNum: number | null, valueText: string | null) {
    setSaving(true);
    setError(null);
    try {
      await api("/api/metrics/entries", {
        method: "POST",
        body: JSON.stringify({
          metric_code: def.code, value_num: valueNum, value_text: valueText,
        }),
      });
      setInput("");
      onSaved();
      if (open && def.input_type !== "text")
        api<Entry[]>(`/api/metrics/entries?code=${def.code}`).then(setEntries);
    } catch {
      setError("저장에 실패했어요. 다시 시도해주세요.");
    } finally {
      setSaving(false);
    }
  }

  const latestLabel = latest
    ? def.input_type === "scale" && latest.value_num !== null
      ? SCALE_LABELS[latest.value_num]
      : def.input_type === "text"
        ? latest.value_text
        : `${latest.value_num} ${def.unit}`
    : "—";

  return (
    <div className="border-b border-slate-100 py-3 last:border-0">
      <button className="flex min-h-11 w-full items-center justify-between"
              onClick={() => setOpen(!open)}>
        <span className="text-slate-700">{def.name_ko}</span>
        <span className="flex items-center gap-1.5 text-sm">
          <span className={latest ? "font-medium text-slate-800" : "text-slate-400"}>
            {latestLabel}
          </span>
          <span className="text-slate-300">{open ? "▾" : "▸"}</span>
        </span>
      </button>
      {open && (
        <div className="space-y-3 pt-2">
          {def.input_type !== "text" && <HistoryChart def={def} entries={entries} />}
          {def.input_type === "scale" ? (
            <div className="flex gap-2">
              {SCALE_LABELS.map((label, i) => (
                <button key={i} disabled={saving}
                        onClick={() => save(i, null)}
                        className="flex-1 rounded-lg border border-slate-300 py-2 text-sm text-slate-600 transition-colors active:bg-slate-900 active:text-white">
                  {label}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex gap-2">
              <input
                type={def.input_type === "number" ? "number" : "text"}
                inputMode={def.input_type === "number" ? "decimal" : undefined}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={def.unit || "입력"}
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 focus:border-slate-900 focus:outline-none"
              />
              <button
                disabled={saving || !input}
                onClick={() =>
                  def.input_type === "number"
                    ? save(Number(input), null)
                    : save(null, input)
                }
                className="rounded-lg bg-slate-900 px-4 text-white transition-colors hover:bg-slate-800 disabled:opacity-40">
                저장
              </button>
            </div>
          )}
          {error && <p className="text-sm text-rose-600">{error}</p>}
        </div>
      )}
    </div>
  );
}

interface ProfileData { name: string; sex: string | null; birth_date: string | null; }

function ProfileCard() {
  const [profile, setProfile] = useState<ProfileData>({ name: "", sex: null, birth_date: null });
  const [saved, setSaved] = useState(false);

  useEffect(() => { api<ProfileData>("/api/profile").then(setProfile); }, []);

  async function save() {
    await api("/api/profile", { method: "PUT", body: JSON.stringify(profile) });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  return (
    <section className="reveal space-y-3 rounded-2xl border border-stone-200/80 bg-white p-5 shadow-sm shadow-slate-200/50">
      <h2 className="font-display text-base font-bold text-slate-800">프로필</h2>
      <div className="flex gap-2">
        <input value={profile.name} placeholder="이름"
               onChange={(e) => setProfile({ ...profile, name: e.target.value })}
               className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none" />
        <select value={profile.sex ?? ""}
                onChange={(e) => setProfile({ ...profile, sex: e.target.value || null })}
                className="rounded-lg border border-slate-300 px-2 text-sm">
          <option value="">성별</option>
          <option value="M">남</option>
          <option value="F">여</option>
        </select>
        <input type="date" value={profile.birth_date ?? ""}
               onChange={(e) => setProfile({ ...profile, birth_date: e.target.value || null })}
               className="rounded-lg border border-slate-300 px-2 text-sm" />
      </div>
      <button onClick={save}
              className="w-full rounded-full bg-slate-900 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-800">
        {saved ? "저장됨 ✓" : "프로필 저장"}
      </button>
    </section>
  );
}

interface LabEntry { metric_code: string; value_num: number | null; measured_at: string | null; }
interface LabExtract { entries?: LabEntry[]; }

function LabResultUpload({ defs, onSaved }: { defs: MetricDef[]; onSaved: () => void }) {
  const [entries, setEntries] = useState<LabEntry[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const defByCode = Object.fromEntries(defs.map((d) => [d.code, d]));

  function applyExtract(result: { extracted: LabExtract | null; error: string | null }) {
    setEntries((result.extracted?.entries ?? []).filter((e) => defByCode[e.metric_code]));
    setNotice(result.error ? `인식 실패: ${result.error}` : null);
  }

  async function save() {
    if (!entries?.length) return;
    setSaving(true);
    setError(null);
    try {
      await api("/api/metrics/entries/bulk", {
        method: "POST",
        body: JSON.stringify({ entries }),
      });
      setEntries(null);
      onSaved();
    } catch {
      setError("저장에 실패했어요. 값을 확인해주세요.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="reveal space-y-3 rounded-2xl border border-stone-200/80 bg-white p-5 shadow-sm shadow-slate-200/50">
      <h2 className="font-display text-base font-bold text-slate-800">건강검진 결과지</h2>
      <PhotoUploadButton kind="lab_result" label="결과지 사진으로 입력" onExtracted={applyExtract} />
      {notice && <p className="text-xs text-amber-600">{notice}</p>}
      {entries && (
        <div className="space-y-2">
          {entries.map((e, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <span className="w-28 shrink-0 text-sm text-slate-700">
                {defByCode[e.metric_code]?.name_ko ?? e.metric_code}
              </span>
              <input type="number" value={e.value_num ?? ""}
                     onChange={(ev) => setEntries(entries.map((x, i) =>
                       i === idx ? { ...x, value_num: Number(ev.target.value) } : x))}
                     className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <button onClick={() => setEntries(entries.filter((_, i) => i !== idx))}
                      className="text-xs text-slate-400">✕</button>
            </div>
          ))}
          <button onClick={save} disabled={saving || entries.length === 0}
                  className="w-full rounded-full bg-slate-900 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-40">
            {saving ? "저장 중…" : `${entries.length}개 항목 저장`}
          </button>
          {error && <p className="text-sm text-rose-600">{error}</p>}
        </div>
      )}
    </section>
  );
}

export default function MyDataPage() {
  const [defs, setDefs] = useState<MetricDef[]>([]);
  const [latest, setLatest] = useState<Latest>({});

  function reload() {
    api<Latest>("/api/metrics/latest").then(setLatest);
  }
  useEffect(() => {
    api<MetricDef[]>("/api/metrics/definitions").then(setDefs);
    reload();
  }, []);

  return (
    <div className="mx-auto max-w-lg space-y-5 px-4 pb-4 pt-6">
      <header>
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-teal-700/60">My Data</p>
        <h1 className="mt-1 font-display text-3xl font-extrabold leading-none text-slate-900">내 데이터</h1>
        <p className="mt-2 text-sm text-slate-500">
          아는 항목만 입력하세요. 입력한 데이터만 분석에 사용됩니다.
        </p>
      </header>
      <ProfileCard />
      <LabResultUpload defs={defs} onSaved={reload} />
      {DOMAIN_ORDER.map((domain) => (
        <section key={domain}
                 className="rounded-2xl border border-stone-200/80 bg-white px-5 py-3 shadow-sm shadow-slate-200/50">
          <h2 className="pt-1 pb-1 font-display text-base font-bold text-slate-800">
            {DOMAIN_LABELS[domain]}
          </h2>
          {defs.filter((d) => d.domain === domain).map((d) => (
            <MetricRow key={d.code} def={d} latest={latest[d.code]} onSaved={reload} />
          ))}
        </section>
      ))}
    </div>
  );
}
