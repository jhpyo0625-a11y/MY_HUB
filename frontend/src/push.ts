import { api } from "./api";

function urlBase64ToUint8Array(base64: string): BufferSource {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const base64Safe = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64Safe);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window;
}

export async function getPushSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return reg ? reg.pushManager.getSubscription() : null;
}

export async function enablePush(): Promise<void> {
  if (!pushSupported()) throw new Error("이 브라우저는 알림을 지원하지 않아요");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("알림 권한이 거부되었어요");

  const reg = await navigator.serviceWorker.register("/sw.js");
  const { key } = await api<{ key: string }>("/api/push/vapid-public-key");
  const subscription = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(key),
  });
  await api("/api/push/subscribe", {
    method: "POST",
    body: JSON.stringify({ subscription: subscription.toJSON() }),
  });
}

export async function disablePush(): Promise<void> {
  const subscription = await getPushSubscription();
  if (subscription) await subscription.unsubscribe();
  await api("/api/push/subscribe", { method: "DELETE" });
}
