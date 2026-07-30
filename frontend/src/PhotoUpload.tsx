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
  const inputId = `photo-${kind}-${label}`;

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const result = await apiUpload<ExtractResult<T>>("/api/photos/extract", kind, file);
      onExtracted(result);
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <>
      <input ref={inputRef} type="file" accept="image/*" capture="environment"
             onChange={onChange} className="hidden" id={inputId} />
      <label htmlFor={inputId}
             className="inline-block cursor-pointer rounded-full border border-teal-600 px-4 py-2 text-sm font-medium text-teal-700 transition-colors active:bg-teal-50">
        {loading ? "분석 중…" : `📷 ${label}`}
      </label>
    </>
  );
}

export function photoUrl(path: string): string {
  return `/api/photos/${path}`;
}
