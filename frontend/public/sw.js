self.addEventListener("push", (event) => {
  let data = { title: "MyHub", body: "" };
  try { data = event.data.json(); } catch { /* malformed payload — show default */ }
  event.waitUntil(self.registration.showNotification(data.title, { body: data.body, data }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow("/dashboard"));
});
