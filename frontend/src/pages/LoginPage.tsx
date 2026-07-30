import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      navigate("/dashboard");
    } catch {
      setError("비밀번호가 올바르지 않습니다");
    }
  }

  return (
    <div className="mx-auto max-w-lg px-4 pt-28">
      <div className="mb-8 text-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-teal-700/60">
          Personal Health
        </p>
        <h1 className="mt-2 font-display text-5xl font-extrabold text-slate-900">MyHub</h1>
        <p className="mt-2 text-sm text-slate-400">나의 건강 기록과 분석</p>
      </div>
      <form onSubmit={submit}
            className="reveal space-y-4 rounded-2xl border border-stone-200/80 bg-white p-6 shadow-sm shadow-slate-200/50">
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호"
          className="w-full rounded-lg border border-slate-300 px-3 py-3 focus:border-slate-900 focus:outline-none"
        />
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <button className="w-full rounded-full bg-slate-900 py-3 font-medium text-white transition-colors hover:bg-slate-800">
          로그인
        </button>
      </form>
    </div>
  );
}
