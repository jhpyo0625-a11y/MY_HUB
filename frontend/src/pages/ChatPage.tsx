import { useEffect, useRef, useState } from "react";
import { api } from "../api";

interface ProposedEntry { metric_code: string; value_num: number | null; value_text: string | null; }
interface ChatMsg {
  id: number; role: "user" | "assistant"; content: string;
  proposed_entries: ProposedEntry[]; created_at: string;
}

function ProposedEntryCard({ entry, onConfirmed }: {
  entry: ProposedEntry; onConfirmed: () => void;
}) {
  const [saved, setSaved] = useState(false);
  async function confirm() {
    await api("/api/metrics/entries", { method: "POST", body: JSON.stringify(entry) });
    setSaved(true);
    onConfirmed();
  }
  return (
    <div className="mt-2 flex items-center gap-2 rounded-xl border border-teal-200 bg-teal-50 px-3 py-2 text-sm">
      <span className="text-teal-800">
        {entry.metric_code} = {entry.value_num ?? entry.value_text}
      </span>
      <button onClick={confirm} disabled={saved}
              className="ml-auto rounded-full bg-teal-700 px-3 py-1 text-xs font-medium text-white disabled:opacity-40">
        {saved ? "저장됨 ✓" : "저장"}
      </button>
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  function reload() {
    api<ChatMsg[]>("/api/chat/messages").then(setMessages);
  }
  useEffect(reload, []);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    if (!input.trim() || sending) return;
    setSending(true);
    const content = input;
    setInput("");
    try {
      const res = await api<{ user_message: ChatMsg; assistant_message: ChatMsg }>(
        "/api/chat/messages", { method: "POST", body: JSON.stringify({ content }) });
      setMessages((m) => [...m, res.user_message, res.assistant_message]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-80px)] max-w-lg flex-col px-4 pt-6">
      <header className="pb-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-teal-700/60">Chat</p>
        <h1 className="mt-1 font-display text-3xl font-extrabold leading-none text-slate-900">AI 채팅</h1>
      </header>
      <div className="flex-1 space-y-3 overflow-y-auto pb-3">
        {messages.length === 0 && (
          <p className="pt-8 text-center text-sm text-slate-400">
            건강 데이터에 대해 무엇이든 물어보세요.
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              m.role === "user" ? "bg-slate-900 text-white" : "border border-stone-200 bg-white text-slate-800"
            }`}>
              <p>{m.content}</p>
              {m.proposed_entries.map((e, i) => (
                <ProposedEntryCard key={i} entry={e} onConfirmed={reload} />
              ))}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2 border-t border-stone-200 py-3">
        <input value={input} onChange={(e) => setInput(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && send()}
               placeholder="메시지를 입력하세요"
               className="flex-1 rounded-full border border-slate-300 px-4 py-2.5 text-sm focus:border-slate-900 focus:outline-none" />
        <button onClick={send} disabled={sending || !input.trim()}
                className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-40">
          전송
        </button>
      </div>
    </div>
  );
}
