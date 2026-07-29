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
      navigate("/data");
    } catch {
      setError("비밀번호가 올바르지 않습니다");
    }
  }

  return (
    <div className="max-w-lg mx-auto px-4 pt-24">
      <h1 className="text-2xl font-bold text-center mb-8">MyHub</h1>
      <form onSubmit={submit} className="bg-white rounded-xl p-6 shadow-sm space-y-4">
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호"
          className="w-full border border-slate-300 rounded-lg px-3 py-3"
        />
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button className="w-full bg-sky-600 text-white rounded-lg py-3 font-semibold">
          로그인
        </button>
      </form>
    </div>
  );
}
