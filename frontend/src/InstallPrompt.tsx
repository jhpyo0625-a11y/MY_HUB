import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export default function InstallPrompt() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    };
    const onInstalled = () => setDeferred(null);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (!deferred) return null;

  return (
    <div className="fixed bottom-20 inset-x-0 flex justify-center px-4 z-10">
      <div className="max-w-lg w-full bg-teal-700 text-white rounded-xl px-4 py-3 flex items-center justify-between shadow-lg gap-3">
        <span className="text-sm">홈 화면에 추가하고 더 빠르게 열어보세요</span>
        <div className="flex gap-2 shrink-0">
          <button
            className="text-xs font-semibold bg-white/20 rounded-lg px-3 py-1.5 min-h-11"
            onClick={async () => {
              await deferred.prompt();
              await deferred.userChoice;
              setDeferred(null);
            }}
          >
            설치
          </button>
          <button
            className="text-xs text-white/70 px-2 min-h-11"
            onClick={() => setDeferred(null)}
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
