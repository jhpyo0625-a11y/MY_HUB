import { useRef, useState } from "react";
import { apiUpload } from "./api";

export interface ExtractResult<T> {
  photo_path: string;
  extracted: T | null;
  error: string | null;
}

export function PhotoUploadButton<T>({ kind, label, onExtracted }: {
  kind: string;
  label: string;
  onExtracted: (result: ExtractResult<T>) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputId = `photo-${kind}-${label}`;

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setLoading(true);
    try {
      const result = await apiUpload<ExtractResult<T>>("/api/photos/extract", kind, file);
      onExtracted(result);
    } catch {
      setError("업로드에 실패했어요. 다시 시도해주세요.");
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <input ref={inputRef} type="file" accept="image/*" capture="environment"
             onChange={onChange} className="hidden" id={inputId} />
      <label htmlFor={inputId}
             className="inline-block cursor-pointer rounded-full border border-teal-600 px-4 py-2 text-sm font-medium text-teal-700 transition-colors active:bg-teal-50">
        {loading ? "분석 중…" : `📷 ${label}`}
      </label>
      {error && <p className="mt-1 text-sm text-rose-600">{error}</p>}
    </div>
  );
}

export function photoUrl(path: string): string {
  return `/api/photos/${path}`;
}
