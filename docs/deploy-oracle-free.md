# Deploy MyHub on Oracle Cloud Always Free

Runs MyHub on an Oracle Cloud "Always Free" Ampere A1 VM, permanently free —
no Fly.io paid plan needed. Uses Docker Compose (app + Caddy) instead of
`fly.toml`; Caddy gets automatic HTTPS from a free DuckDNS subdomain instead
of Fly's edge TLS.

**Interfaces:** none — this is deploy infrastructure, not application code.
`docker-compose.yml` and `Caddyfile` at the repo root are config the app
doesn't read directly; only `MYHUB_DOMAIN` (used by `Caddyfile`) is new.

## 1. Create the Oracle Cloud account and VM

1. Sign up at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) (a
   credit card is required for identity verification — it is not charged
   unless you explicitly upgrade to a paid plan).
2. Console → **Compute → Instances → Create Instance**.
   - Image: **Canonical Ubuntu** (latest LTS).
   - Shape: **Ampere → VM.Standard.A1.Flex**, 2 OCPU / 12 GB RAM is plenty
     for a single-user app (up to 4 OCPU / 24 GB is available free if you
     want headroom).
   - Add your SSH public key (or let Oracle generate a key pair for you and
     download the private key).
   - If you hit "Out of host capacity" for the A1 shape, retry a few times
     or try a different Availability Domain / region close to you — this is
     a known Oracle Always Free constraint, not a config problem.
3. **Networking → IP Management → Reserved Public IPs** — reserve a public
   IP and attach it to the instance's VNIC, so the address never changes on
   reboot (a plain ephemeral IP can change).
4. Open HTTP/HTTPS in the subnet's **Security List** (Ingress Rules): allow
   TCP 80 and 443 from `0.0.0.0/0` (22 for SSH should already be open).
5. Oracle's Ubuntu image also ships a host-level `iptables` INPUT-DROP rule
   independent of the Security List — SSH in and run:
   ```bash
   sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save   # or: sudo apt install iptables-persistent
   ```
   Skip this and Caddy's HTTPS challenge will time out even though the
   Security List looks correct.

## 2. Point a free DuckDNS subdomain at the VM

1. Sign in at [duckdns.org](https://www.duckdns.org/) with an existing
   account (GitHub/Google/Reddit).
2. Create a subdomain, e.g. `myhub` → `myhub.duckdns.org`.
3. Set its IP to the reserved public IP from step 1.3. Because that IP is
   reserved (static), you only need to do this once — no dynamic-update
   script required.

## 3. Install Docker on the VM

```bash
ssh ubuntu@<reserved-ip>
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# log out and back in for the group change to take effect
docker compose version   # confirm the compose plugin is present
```

## 4. Copy the project and configure `.env`

```bash
git clone <your-fork-url> myhub && cd myhub
cp .env.example .env
```

Edit `.env`:
- `MYHUB_PASSWORD`, `MYHUB_SECRET_KEY` — set to real values (required in
  production; the app refuses to boot with the defaults once
  `MYHUB_ENV=production` or `MYHUB_COOKIE_SECURE=true`).
- `MYHUB_ENV=production`, `MYHUB_COOKIE_SECURE=true` — Caddy terminates
  HTTPS in front of the app, same assumption the app already makes for the
  Fly.io path.
- `OPENAI_API_KEY` (and `OPENAI_BASE_URL`/model vars if using a
  non-OpenAI-compatible provider).
- `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` — reuse the
  keypair generated in Phase 3 (`docs/superpowers/plans/2026-07-29-myhub-phase3.md`
  Task 4 Step 10); regenerate first if that step was skipped.
- `MYHUB_DOMAIN=myhub.duckdns.org` — new for this path, read by
  `Caddyfile` (via `docker-compose.yml`'s `${MYHUB_DOMAIN}` substitution),
  not by the app itself.

## 5. Start it

```bash
docker compose up -d --build
```

Caddy requests a Let's Encrypt certificate for `MYHUB_DOMAIN` on first
request — allow ~30 seconds after startup before it's reachable over HTTPS.

## 6. Verify

```bash
curl https://myhub.duckdns.org/api/health
```

Expected: `{"ok":true}` over HTTPS. Then open the URL in a phone browser,
log in, and confirm the PWA install banner and push-notification toggle
both work against the live deployment.

## Notes

- `myhub_data` is a named Docker volume holding the live SQLite file and
  the app's own daily backup copy (`backup.py`) — both live on the same
  VM disk. That protects against DB corruption / accidental table drops,
  not VM/disk loss. If that durability gap matters, periodically `docker
  cp` or `rsync` the volume off-box.
- `fly.toml` is still in the repo as an alternative if you'd rather use
  managed hosting later — Fly.io no longer has a free tier, but a minimal
  always-on machine there runs about $2/month.
- To update after a `git pull`: `docker compose up -d --build`.
