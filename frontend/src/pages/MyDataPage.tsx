import { useEffect, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";

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
    return <p className="text-sm text-slate-400 py-3">기록이 2개 이상이면 그래프가 표시됩니다</p>;
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="x" tick={{ fontSize: 11, fill: "#64748b" }}
               tickLine={false} axisLine={{ stroke: "#e2e8f0" }} />
        <YAxis tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false}
               axisLine={false} width={40} domain={["auto", "auto"]} />
        <Tooltip formatter={(v) => [`${v} ${def.unit}`, def.name_ko]} />
        {def.range_low !== null && def.range_high !== null && (
          <ReferenceArea y1={def.range_low} y2={def.range_high}
                         fill="#10b981" fillOpacity={0.08} />
        )}
        <Line type="monotone" dataKey="y" stroke="#0284c7" strokeWidth={2}
              dot={{ r: 3 }} activeDot={{ r: 5 }} />
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

  useEffect(() => {
    if (open && def.input_type !== "text")
      api<Entry[]>(`/api/metrics/entries?code=${def.code}`).then(setEntries);
  }, [open, def]);

  async function save(valueNum: number | null, valueText: string | null) {
    setSaving(true);
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
    <div className="border-b border-slate-100 last:border-0 py-3">
      <button className="w-full flex justify-between items-center min-h-11"
              onClick={() => setOpen(!open)}>
        <span>{def.name_ko}</span>
        <span className="text-slate-500 text-sm">{latestLabel} {open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="pt-2 space-y-3">
          {def.input_type !== "text" && <HistoryChart def={def} entries={entries} />}
          {def.input_type === "scale" ? (
            <div className="flex gap-2">
              {SCALE_LABELS.map((label, i) => (
                <button key={i} disabled={saving}
                        onClick={() => save(i, null)}
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
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={def.unit || "입력"}
                className="flex-1 border border-slate-300 rounded-lg px-3 py-2"
              />
              <button
                disabled={saving || !input}
                onClick={() =>
                  def.input_type === "number"
                    ? save(Number(input), null)
                    : save(null, input)
                }
                className="bg-sky-600 text-white rounded-lg px-4 disabled:opacity-40">
                저장
              </button>
            </div>
          )}
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
    <section className="bg-white rounded-xl shadow-sm p-4 space-y-2">
      <h2 className="text-sm font-semibold text-slate-500">프로필</h2>
      <div className="flex gap-2">
        <input value={profile.name} placeholder="이름"
               onChange={(e) => setProfile({ ...profile, name: e.target.value })}
               className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm" />
        <select value={profile.sex ?? ""}
                onChange={(e) => setProfile({ ...profile, sex: e.target.value || null })}
                className="border border-slate-300 rounded-lg px-2 text-sm">
          <option value="">성별</option>
          <option value="M">남</option>
          <option value="F">여</option>
        </select>
        <input type="date" value={profile.birth_date ?? ""}
               onChange={(e) => setProfile({ ...profile, birth_date: e.target.value || null })}
               className="border border-slate-300 rounded-lg px-2 text-sm" />
      </div>
      <button onClick={save}
              className="w-full bg-sky-600 text-white rounded-lg py-2 text-sm">
        {saved ? "저장됨 ✓" : "프로필 저장"}
      </button>
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
    <div className="max-w-lg mx-auto px-4 pt-6 space-y-6">
      <h1 className="text-xl font-bold">내 데이터</h1>
      <p className="text-sm text-slate-500">
        아는 항목만 입력하세요. 입력한 데이터만 분석에 사용됩니다.
      </p>
      <ProfileCard />
      {DOMAIN_ORDER.map((domain) => (
        <section key={domain} className="bg-white rounded-xl shadow-sm px-4 py-2">
          <h2 className="text-sm font-semibold text-slate-500 pt-2">
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
