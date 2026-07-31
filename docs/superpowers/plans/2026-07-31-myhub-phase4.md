# MyHub Phase 4 — Ship Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Phase 1–3 app into a deployed, installable product: automatic weekly analysis and DB backup jobs, a PWA install flow with mobile viewport polish, and a documented deploy to a small cloud host with HTTPS and a persistent volume.

**Architecture:** Two small backend additions register onto the existing `BackgroundScheduler` already running in `app/main.py`'s lifespan (alongside Phase 3's `reminder_tick`): a weekly cron job that calls the existing `run_analysis` engine, and a daily cron job that hot-copies the SQLite file via `sqlite3`'s backup API (WAL-safe, unlike a plain file copy). On the frontend, a `manifest.webmanifest` plus an unconditional service-worker registration make the app installable; a small `InstallPrompt` component surfaces the native `beforeinstallprompt` event as a dismissible banner. Deployment is a Fly.io config file (`fly.toml`) referencing the existing Dockerfile, plus documented one-time `flyctl` ops steps — no new application code for this part, matching how Phase 3 treated VAPID keypair generation as a manual step.

**Tech Stack:** Same as Phase 1–3 (FastAPI, SQLAlchemy 2.x, SQLite, pytest, APScheduler · React + Vite + TS + Tailwind v4, Vitest). No new backend or frontend dependencies. Deploy target: Fly.io (per spec §1 "Small cloud host (Fly.io / Railway)").

**Spec:** `docs/superpowers/specs/2026-07-29-myhub-design.md` §6 (error handling — daily backup), §8 tasks 13–15.

**Scope notes (deviations, deliberate):**
- PWA icon uses the existing `frontend/public/favicon.svg` as the manifest's only icon entry (`sizes: "any"`), not a generated PNG icon set. `# ponytail: add real 192/512px PNG icons if the SVG doesn't render on an install surface you care about (some older Android/iOS home-screen icon paths still expect PNG).`
- `manifest.webmanifest`'s `start_url` is `/dashboard` (the app's real home), not `/` — there's no content at `/` and the SPA catch-all in `main.py` already redirects unknown paths to `index.html`, but `/dashboard` skips that round-trip on launch.
- Fly.io region is set to `nrt` (Tokyo, closest available region to Korea) as a reasonable default — change it in `fly.toml` if the owner prefers otherwise. This is a single-user app; region choice has no correctness implications, only latency.
- VAPID keys were already generated as a manual step in Phase 3 (`docs/superpowers/plans/2026-07-29-myhub-phase3.md` Task 4 Step 10). Deploy step in this plan only covers *setting* `VAPID_PRIVATE_KEY`/`VAPID_PUBLIC_KEY`/`VAPID_SUBJECT` as Fly secrets — regenerate first if that step was skipped.
- "Mobile polish pass" (spec item 14) is scoped narrowly to what's concretely testable/reviewable: iOS safe-area bottom padding for the fixed tab bar, `overscroll-behavior` to kill rubber-band scroll, and `viewport-fit=cover`. It is not a general design pass — file a follow-up if more is wanted after using the installed app for a while.
- "QA" (spec item 14) is a manual step (last step of Task 3) using the existing `/qa` skill against a mobile viewport, not new automated tests — frontend testing stays "light — component smoke tests only" per spec §7.

## Global Constraints (Phase 4 additions on top of Phase 1/2/3's)

- New scheduler jobs register on the same `scheduler = BackgroundScheduler()` instance in `app/main.py`, using the same `id=`/`replace_existing=True` pattern as Phase 3's `reminder_tick` job.
- New scheduler tick wrappers (`_weekly_analysis_tick`, `_backup_tick`) follow the `_reminder_tick` precedent: untested glue that opens/closes its own `SessionLocal()` and never lets an exception escape, so one bad run can't kill the background scheduler thread. The logic they call (`run_scheduled_analysis`, `backup_db`) is unit-tested directly, same division of labor as `_reminder_tick` / `check_and_send_reminders`.
- `Base.metadata.create_all` only — no new tables this phase, no migrations.
- Mock OpenAI in tests the same way `test_analysis.py` already does: `monkeypatch.setattr(analysis, "OpenAI", FakeClientClass)`, never hit the network.
- No new backend or frontend dependencies.
- Dev runs unchanged: `cd backend; .venv\Scripts\uvicorn app.main:app --reload --port 8000` / `cd frontend; npm run dev`.
- Commit messages end with a `Co-Authored-By:` trailer identifying whichever model executes the task (repo convention — see recent `git log`, not a fixed string).

## File Structure (Phase 4 additions)

```
fly.toml                  # NEW — Fly.io app config (build, http_service, volume mount)
.env.example              # + VAPID_* vars
backend/
  app/
    analysis.py           # + run_scheduled_analysis(db)
    backup.py             # NEW — backup_db()
    main.py               # + logging import, weekly-analysis + db-backup scheduler jobs
  tests/
    test_analysis.py      # appended
    test_backup.py        # NEW
frontend/
  public/
    manifest.webmanifest  # NEW
  index.html               # + manifest link, theme-color, viewport-fit=cover
  src/
    main.tsx                # + unconditional service-worker registration
    InstallPrompt.tsx        # NEW — beforeinstallprompt banner
    InstallPrompt.test.tsx   # NEW
    App.tsx                  # + <InstallPrompt />
    index.css                 # + safe-area padding, overscroll-behavior
```

---

### Task 1: Weekly auto-analysis scheduler job

**Files:**
- Modify: `backend/app/analysis.py` (append function)
- Modify: `backend/app/main.py`
- Test: append to `backend/tests/test_analysis.py`

**Interfaces:**
- Consumes: `run_analysis(db: Session, trigger: str) -> Analysis`, `AnalysisError` (both already exist in `app.analysis`).
- Produces: `run_scheduled_analysis(db: Session) -> Analysis | None` — calls `run_analysis(db, trigger="weekly")`, catches `AnalysisError`, logs it, returns `None` instead of raising.

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_analysis.py` (reuses the module-level `GOOD_RESULT`, `_fake_client`, `_seed_evidence` already defined in this file):
```python
def test_run_scheduled_analysis_success(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([GOOD_RESULT]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    result = analysis.run_scheduled_analysis(db)
    assert result is not None
    assert result.trigger == "weekly"


def test_run_scheduled_analysis_swallows_failure(db_session_factory, monkeypatch):
    from app import analysis
    db = _seed_evidence(db_session_factory)
    bad = {**GOOD_RESULT, "top3": [{**GOOD_RESULT["top3"][0], "evidence_ids": [999]}]}
    monkeypatch.setattr(analysis, "OpenAI", _fake_client([bad, bad]))
    monkeypatch.setattr(analysis.settings, "openai_api_key", "test-key")

    assert analysis.run_scheduled_analysis(db) is None
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_analysis.py -v -k scheduled
```
Expected: FAIL — `AttributeError: module 'app.analysis' has no attribute 'run_scheduled_analysis'`.

- [ ] **Step 3: Implement `run_scheduled_analysis`**

Append to `backend/app/analysis.py` (end of file, after `run_analysis`):
```python


def run_scheduled_analysis(db: Session) -> Analysis | None:
    """Weekly cron entry point — never raises, so a bad LLM response or
    provider outage can't crash the background scheduler thread."""
    try:
        return run_analysis(db, trigger="weekly")
    except AnalysisError:
        logger.warning("weekly scheduled analysis failed", exc_info=True)
        return None
```

- [ ] **Step 4: Run tests, verify pass**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_analysis.py -v
```
Expected: all pass.

- [ ] **Step 5: Wire the weekly cron job into main.py**

In `backend/app/main.py`, change:
```python
from contextlib import asynccontextmanager
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from .config import settings
from .db import init_db

scheduler = BackgroundScheduler()


def _reminder_tick() -> None:
    from .db import SessionLocal
    from .reminders import check_and_send_reminders
    db = SessionLocal()
    try:
        check_and_send_reminders(db, datetime.now())
    finally:
        db.close()
```
to:
```python
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from .config import settings
from .db import init_db

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def _reminder_tick() -> None:
    from .db import SessionLocal
    from .reminders import check_and_send_reminders
    db = SessionLocal()
    try:
        check_and_send_reminders(db, datetime.now())
    finally:
        db.close()


def _weekly_analysis_tick() -> None:
    from .analysis import run_scheduled_analysis
    from .db import SessionLocal
    db = SessionLocal()
    try:
        run_scheduled_analysis(db)
    finally:
        db.close()
```

Then, in the `lifespan` function, change:
```python
    scheduler.add_job(_reminder_tick, "interval", minutes=1, id="reminder_tick",
                      replace_existing=True)
    scheduler.start()
```
to:
```python
    scheduler.add_job(_reminder_tick, "interval", minutes=1, id="reminder_tick",
                      replace_existing=True)
    scheduler.add_job(_weekly_analysis_tick, "cron", day_of_week="mon", hour=8,
                      minute=0, id="weekly_analysis", replace_existing=True)
    scheduler.start()
```

- [ ] **Step 6: Run full backend test suite, verify pass**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/analysis.py backend/app/main.py backend/tests/test_analysis.py
git commit -m "feat: run analysis automatically every Monday via the scheduler"
```

---

### Task 2: DB backup job

**Files:**
- Create: `backend/app/backup.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_backup.py`

**Interfaces:**
- Consumes: `settings.db_path`, `settings.myhub_data_dir` from `app.config`.
- Produces: `backup_db() -> Path | None` — `None` if the live DB file doesn't exist yet (nothing to back up); otherwise hot-copies it to `<myhub_data_dir>/myhub_backup.db` via `sqlite3.Connection.backup()` (safe under WAL, unlike `shutil.copy`) and returns that path.

- [ ] **Step 1: Write failing tests**

`backend/tests/test_backup.py`:
```python
import sqlite3


def test_backup_db_copies_data(tmp_path, monkeypatch):
    from app.config import settings
    from app import backup
    monkeypatch.setattr(settings, "myhub_data_dir", tmp_path)

    src = sqlite3.connect(settings.db_path)
    src.execute("CREATE TABLE t (id INTEGER)")
    src.execute("INSERT INTO t VALUES (1)")
    src.commit()
    src.close()

    result = backup.backup_db()
    assert result == tmp_path / "myhub_backup.db"
    assert result.is_file()

    check = sqlite3.connect(result)
    assert check.execute("SELECT id FROM t").fetchone() == (1,)
    check.close()


def test_backup_db_missing_source_returns_none(tmp_path, monkeypatch):
    from app.config import settings
    from app import backup
    monkeypatch.setattr(settings, "myhub_data_dir", tmp_path)

    assert backup.backup_db() is None
```

- [ ] **Step 2: Run tests, verify fail**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_backup.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backup'`.

- [ ] **Step 3: Implement backup module**

`backend/app/backup.py`:
```python
import logging
import sqlite3
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)


def backup_db() -> Path | None:
    """Hot-copy the live SQLite file to a second path on the same volume via
    sqlite3's backup API, which is WAL-safe (a plain file copy is not, since
    a concurrent writer could be mid-checkpoint)."""
    if not settings.db_path.is_file():
        return None
    backup_path = settings.myhub_data_dir / "myhub_backup.db"
    src = sqlite3.connect(settings.db_path)
    try:
        dst = sqlite3.connect(backup_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return backup_path
```

- [ ] **Step 4: Run tests, verify pass**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/test_backup.py -v
```
Expected: all pass.

- [ ] **Step 5: Wire the daily backup job into main.py**

In `backend/app/main.py`, change:
```python
    scheduler.add_job(_reminder_tick, "interval", minutes=1, id="reminder_tick",
                      replace_existing=True)
    scheduler.add_job(_weekly_analysis_tick, "cron", day_of_week="mon", hour=8,
                      minute=0, id="weekly_analysis", replace_existing=True)
    scheduler.start()
```
to:
```python
    scheduler.add_job(_reminder_tick, "interval", minutes=1, id="reminder_tick",
                      replace_existing=True)
    scheduler.add_job(_weekly_analysis_tick, "cron", day_of_week="mon", hour=8,
                      minute=0, id="weekly_analysis", replace_existing=True)
    scheduler.add_job(_backup_tick, "cron", hour=3, minute=0, id="db_backup",
                      replace_existing=True)
    scheduler.start()
```

Then add the tick wrapper next to `_weekly_analysis_tick`:
```python
def _backup_tick() -> None:
    from .backup import backup_db
    try:
        backup_db()
    except Exception:
        logger.warning("db backup failed", exc_info=True)
```

- [ ] **Step 6: Run full backend test suite, verify pass**

```powershell
cd backend; .venv\Scripts\python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/backup.py backend/app/main.py backend/tests/test_backup.py
git commit -m "feat: back up the SQLite file daily via the scheduler"
```

---

### Task 3: PWA install flow + mobile viewport polish

**Files:**
- Create: `frontend/public/manifest.webmanifest`
- Modify: `frontend/index.html`
- Modify: `frontend/src/main.tsx`
- Create: `frontend/src/InstallPrompt.tsx`
- Test: `frontend/src/InstallPrompt.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: nothing new.
- Produces: `InstallPrompt` (default export, no props) — a component that renders `null` until the browser fires `beforeinstallprompt`, then renders a dismissible banner with a "설치" button that calls the captured event's `.prompt()`.

- [ ] **Step 1: Write the failing test**

`frontend/src/InstallPrompt.test.tsx`:
```tsx
import { test, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import InstallPrompt from "./InstallPrompt";

function fireBeforeInstallPrompt() {
  const event = new Event("beforeinstallprompt", { cancelable: true }) as Event & {
    prompt: () => Promise<void>;
    userChoice: Promise<{ outcome: string }>;
  };
  event.prompt = () => Promise.resolve();
  event.userChoice = Promise.resolve({ outcome: "accepted" });
  fireEvent(window, event);
}

test("renders nothing until beforeinstallprompt fires", () => {
  render(<InstallPrompt />);
  expect(screen.queryByText("설치")).toBeNull();

  fireBeforeInstallPrompt();
  expect(screen.getByText("설치")).toBeDefined();
});

test("닫기 button hides the banner", () => {
  render(<InstallPrompt />);
  fireBeforeInstallPrompt();
  expect(screen.getByText("설치")).toBeDefined();

  fireEvent.click(screen.getByText("닫기"));
  expect(screen.queryByText("설치")).toBeNull();
});
```

- [ ] **Step 2: Run test, verify it fails**

```powershell
cd frontend; npm run test -- InstallPrompt
```
Expected: FAIL — cannot find module `./InstallPrompt`.

- [ ] **Step 3: Implement InstallPrompt**

`frontend/src/InstallPrompt.tsx`:
```tsx
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
```

- [ ] **Step 4: Run test, verify it passes**

```powershell
cd frontend; npm run test -- InstallPrompt
```
Expected: both tests pass.

- [ ] **Step 5: Create the web manifest**

`frontend/public/manifest.webmanifest`:
```json
{
  "name": "MyHub — 건강 관리",
  "short_name": "MyHub",
  "start_url": "/dashboard",
  "display": "standalone",
  "background_color": "#fafaf9",
  "theme_color": "#0f766e",
  "icons": [
    { "src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any" }
  ]
}
```

- [ ] **Step 6: Link the manifest and add mobile meta tags**

In `frontend/index.html`, change:
```html
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
```
to:
```html
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="apple-touch-icon" href="/favicon.svg" />
    <link rel="manifest" href="/manifest.webmanifest" />
    <meta name="theme-color" content="#0f766e" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
```

- [ ] **Step 7: Register the service worker unconditionally on load**

In `frontend/src/main.tsx`, change:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
```
to:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

ReactDOM.createRoot(document.getElementById("root")!).render(
```

- [ ] **Step 8: Render InstallPrompt in the app shell**

In `frontend/src/App.tsx`, change:
```tsx
import ChatPage from "./pages/ChatPage";
```
to:
```tsx
import ChatPage from "./pages/ChatPage";
import InstallPrompt from "./InstallPrompt";
```
and change:
```tsx
        </Routes>
        <TabBar />
      </div>
    </BrowserRouter>
```
to:
```tsx
        </Routes>
        <InstallPrompt />
        <TabBar />
      </div>
    </BrowserRouter>
```

- [ ] **Step 9: Add safe-area padding and kill overscroll bounce**

In `frontend/src/index.css`, change:
```css
body {
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
```
to:
```css
html, body {
  overscroll-behavior-y: contain;
}

body {
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

/* iPhone home-indicator clearance for the fixed bottom tab bar.
   # ponytail: only covers the tab bar; extend to modals/sheets if any
   grow to the screen edge later. */
.safe-bottom {
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
```

Then in `frontend/src/App.tsx`, change the `TabBar`'s nav className:
```tsx
    <nav className="fixed bottom-0 inset-x-0 bg-white/90 backdrop-blur border-t border-stone-200">
```
to:
```tsx
    <nav className="safe-bottom fixed bottom-0 inset-x-0 bg-white/90 backdrop-blur border-t border-stone-200">
```

- [ ] **Step 10: Run full frontend test suite, verify pass**

```powershell
cd frontend; npm run test
```
Expected: all pass, including the existing `App.test.tsx` tab-bar smoke test.

- [ ] **Step 11: Manual QA on a real mobile viewport**

Run the app locally (`cd backend; .venv\Scripts\uvicorn app.main:app --reload --port 8000` and `cd frontend; npm run dev`), then use the `/qa` skill against a mobile viewport (or Chrome DevTools device toolbar) to confirm: the install banner appears where Chrome supports `beforeinstallprompt`, the tab bar doesn't overlap the iOS home indicator in a notched-device emulation, and pull-to-refresh/rubber-band bounce is gone. Fix anything visibly broken before moving on — this step has no automated check by design (spec §7: frontend testing is smoke-only, manual QA covers the rest).

- [ ] **Step 12: Commit**

```powershell
git add frontend/public/manifest.webmanifest frontend/index.html frontend/src/main.tsx frontend/src/InstallPrompt.tsx frontend/src/InstallPrompt.test.tsx frontend/src/App.tsx frontend/src/index.css
git commit -m "feat: add PWA install prompt and mobile viewport polish"
```

---

### Task 4: Deploy to Fly.io — HTTPS, volume, secrets

**Files:**
- Create: `fly.toml`
- Modify: `.env.example`

**Interfaces:** none — this task is deploy configuration and one-time ops steps, not testable application code (same treatment Phase 3 gave VAPID keypair generation).

- [ ] **Step 1: Add the Fly.io app config**

`fly.toml` (repo root, next to `Dockerfile`):
```toml
app = "myhub"
primary_region = "nrt"

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

[[mounts]]
  source = "myhub_data"
  destination = "/app/data"

[[vm]]
  memory = "512mb"
  cpu_kind = "shared"
  cpus = 1
```
`force_https = true` gives HTTPS termination at Fly's edge for free — this is what makes `MYHUB_COOKIE_SECURE=true` safe to set (spec §2 auth note, `.env.example` deploy note). The `[[mounts]]` block binds a persistent volume at `/app/data`, matching the Dockerfile's `VOLUME /app/data` and `MYHUB_DATA_DIR=/app/data`.

- [ ] **Step 2: Document VAPID env vars in `.env.example`**

In `.env.example`, after the `MYHUB_COOKIE_SECURE` line, add:
```
# Web push VAPID keys (generated once — see Phase 3 plan Task 4 Step 10).
# On Fly.io, secrets are env vars only (no baked-in file), so set
# VAPID_PRIVATE_KEY to the raw base64 private key string, not a .pem path.
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:you@example.com
```

- [ ] **Step 3: One-time ops — provision and deploy (manual, run by the owner)**

```powershell
flyctl auth login
flyctl apps create myhub
flyctl volumes create myhub_data --region nrt --size 1
flyctl secrets set MYHUB_PASSWORD=<strong-password> MYHUB_SECRET_KEY=<long-random-string> `
  MYHUB_ENV=production MYHUB_COOKIE_SECURE=true `
  OPENAI_API_KEY=<key> `
  VAPID_PUBLIC_KEY=<key> VAPID_PRIVATE_KEY=<raw-private-key> VAPID_SUBJECT=mailto:you@example.com
flyctl deploy
```
Adjust the region in both `fly.toml` and the `volumes create` command together if a different one is preferred — they must match. `flyctl deploy` builds the existing multi-stage `Dockerfile` (frontend build → static assets copied into the FastAPI image) and ships it.

- [ ] **Step 4: Verify the deployed app**

```powershell
curl https://myhub.fly.dev/api/health
```
Expected: `{"ok":true}` over HTTPS. Then open `https://myhub.fly.dev` in a phone browser, log in, and confirm the install banner and push-notification toggle both work against the live deployment.

- [ ] **Step 5: Commit the deploy config**

```powershell
git add fly.toml .env.example
git commit -m "chore: add Fly.io deploy config and document VAPID env vars"
```
