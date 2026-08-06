# RentA-Fleet PRO

Multi-tenant fleet rental management platform: vehicle inventory, driver
onboarding with automated risk scoring, rental lifecycle (create / extend /
return), financial decision support (cost analysis, pricing, loan
allocation), live GPS tracking, and predictive maintenance.

Turkish is the platform's business language — user-facing strings, most
domain identifiers, and code comments are in Turkish, since the product
targets the Turkish rent-a-car market.

## Architecture

Django REST Framework backend, layered "clean architecture" style:

```
backend/apps/*            Django apps — views, serializers, models, urls
backend/application/*     Use-case orchestration (touches the ORM, calls domain + infrastructure)
backend/domain/*          Pure business rules (risk scoring, pricing, eligibility) — no ORM/infra imports
backend/infrastructure/*  External services (ClickHouse, Enuygun/SIPP matching, cost calculation, reporting)
backend/common/*          Cross-cutting middleware, permissions, multi-tenancy helpers
```

Multi-tenancy is subdomain-based (`<company-slug>.rentafleetpro.com`),
resolved by `CompanyRouterMiddleware`. Row-level data scoping always keys off
`request.user.company`, not the subdomain-resolved `request.company` — see
`backend/common/multitenancy_tools/scope.py`.

Vue 3 (Composition API, `<script setup>`) + Pinia frontend, single-page app
with a lightweight hand-rolled hash router (`stores/uiStore.js`), not
vue-router.

### AI Fleet Operations Assistant

The chat widget (`AIChatbot.vue` → `POST /api/ai/consult/`, SSE) is a real
function-calling agent (OpenAI, `backend/infrastructure/services/ai/`), not
just a Q&A bot — it can query live fleet/driver/rental/financial data and
propose real actions (create/cancel/extend a rental, return a vehicle,
onboard a driver, record a loan/expense/insurance policy/income).

- **Tool catalog**: `infrastructure/services/ai/tools/{read_tools,write_tools}.py`.
  Every tool's parameter schema is generated directly from the same DRF
  serializer the equivalent HTTP endpoint already uses
  (`tools/schema.py:serializer_to_json_schema`) — there is exactly one source
  of truth for validation, so the tool schema can never drift from the real API.
- **Mutations require confirmation**: the agent never executes a
  create/cancel/extend/return/etc. tool directly. It proposes one via a
  `AIPendingAction` row (5-minute TTL, single-use `consumed_at`, company+user
  scoped) and the chat UI renders a confirm/cancel card; the action only runs
  when the user clicks "Onayla" (`POST /api/ai/actions/<uuid>/confirm/`).
  Read-only tools (vehicle/driver/rental/pricing lookups) run immediately.
- **Falls back gracefully**: with no `OPENAI_API_KEY`, or if the OpenAI call
  fails, the assistant degrades to the original deterministic, data-grounded
  Turkish fallback responses — no tool-calling, but never a hard error.
- AI-driven mutations are tagged in the audit trail (`common/audit.py`,
  Django admin `LogEntry`) as "AI asistanı aracılığıyla" so they're
  distinguishable from manual UI actions.

## Getting started

### Backend

```sh
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # or requirements.txt for runtime-only
cp .env.example .env                  # fill in real values
python manage.py migrate
python manage.py runserver
```

Requires PostgreSQL (relational data) and ClickHouse (vehicle telemetry) —
see `.env.example` for connection settings. `DJANGO_DEBUG=true` in `.env`
uses SQLite automatically and skips several production-only hardening checks
(cookie security, HSTS, the DB-engine parity guard in `settings.py`).

Demo data:

```sh
python manage.py seed_data                        # randomized bulk data + telemetry
python manage.py fleet_ops seed                    # two fixed, branded demo tenants (login creds included)
```

### Frontend

```sh
cd frontend
npm install
npm run dev
```

Proxies `/api` to `http://127.0.0.1:8000` in dev (see `vite.config.js`).

### Cache + background jobs (optional)

Set `REDIS_URL` (e.g. `redis://127.0.0.1:6379/0`) to enable a shared cache
(`django.core.cache.backends.redis.RedisCache`) and asynchronous Celery
tasks. Without it, the cache falls back to per-process `LocMemCache` and
Celery tasks run synchronously in-request (`CELERY_TASK_ALWAYS_EAGER`) — the
app works either way, this is purely a scale/production concern.

```sh
redis-server --daemonize yes
celery -A backend.celery_app worker --loglevel=info    # process tasks
celery -A backend.celery_app beat --loglevel=info       # run scheduled tasks (see settings.CELERY_BEAT_SCHEDULE)
```

## Deploy (Render, free tier)

Single Render **Web Service** runs everything: Django serves both the API
(`/api/*`) and the built Vue SPA (WhiteNoise serves `frontend/dist/` at `/`
— safe because the frontend uses hash routing, `#/overview`, so the browser
never requests any path but `/` from the server). One URL, no CORS to
configure, one dashboard. Backed by a free Render PostgreSQL database.

### First-time setup

1. Push this repo to GitHub (Render deploys from a GitHub repo).
2. On [render.com](https://render.com): **New +** → **Blueprint** → connect
   the repo → Render reads `render.yaml` at the repo root and provisions the
   web service + free Postgres database automatically.
3. Before the first deploy finishes, open the new service → **Environment**
   and set `OPENAI_API_KEY` (marked `sync: false` in `render.yaml`, so it's
   never committed — paste your real key there). Everything else
   (`DJANGO_SECRET_KEY`, `DATABASE_URL`, hosts, CORS) is already wired up in
   `render.yaml`.
4. Wait for the build to finish (`npm run build` + `pip install` +
   `collectstatic`, then `migrate` + `gunicorn` on start) and open the
   `*.onrender.com` URL Render gives you.
5. Seed demo data once: open the web service's **Shell** tab in the Render
   dashboard and run
   ```sh
   python backend/manage.py fleet_ops seed --i-know-this-is-not-prod
   ```
   (the flag is required because `DJANGO_DEBUG=false` in production and this
   command creates fixed demo passwords — see the command's own guard). This
   creates the two white-label demo tenants: `ahmet_mudur` / `ahmet123` and
   `ercan_mudur` / `ercan123`. Log in at `https://<your-app>.onrender.com/`
   with either.

### Known free-tier limits (fine for a demo, plan around them later)

- **Cold start**: the free web service sleeps after 15 min idle; the next
  request takes ~30-60s to wake it up. **Open the URL a few minutes before
  presenting** so it's already warm.
- **Free Postgres expires after 30 days.** Fine for tomorrow and continued
  work this month; before it expires, either upgrade the Render database or
  point `DATABASE_URL` at a separate always-free provider (e.g. Neon.tech)
  — no code change needed, it's one connection string.
- Multi-tenancy here uses the `?company=<slug>` query param (already
  supported, see `common/multitenancy_tools/scope.py`), not wildcard
  subdomains — a `*.onrender.com` wildcard isn't available on the free tier.
- `ClickHouse`/`Redis` are optional (see above) — leave them unset; the app
  degrades gracefully (health check reports them `"unavailable"`, everything
  else works normally). Vehicle live-telemetry/GPS panels will show empty
  data without a ClickHouse instance configured.
- Uploaded vehicle documents (`MEDIA_ROOT`) live on local container disk,
  which Render's free tier does **not** persist across deploys/restarts —
  fine for a demo, revisit with object storage (S3-compatible) later.

### Docker fallback

`render.yaml` uses Render's native Python build environment (`npm` +
`pip` in one `buildCommand`). If that build ever fails because the build
image lacks Node, switch the service's **Environment** to **Docker** in the
Render dashboard — a working multi-stage `Dockerfile` (Node build stage →
Python/gunicorn stage) is already at the repo root; Render will pick it up
automatically instead of `render.yaml`'s native build.

## Testing, linting, type-checking

```sh
# Backend
python -m pytest backend/tests -q
ruff check backend
mypy backend --config-file pyproject.toml

# Frontend
cd frontend
npm run test    # vitest
npm run lint    # eslint
npm run format  # prettier --write
npm run build
```

CI (`.github/workflows/ci.yml`) runs ruff, mypy, and pytest for the backend,
and eslint, vitest, and the production build for the frontend, on every push
and pull request. Both `ruff check backend` and `mypy backend --config-file
pyproject.toml` are fully clean (zero findings) and are hard gates — a PR
that introduces a new lint or type error fails CI. The only exceptions are a
handful of explicit, justified `pyproject.toml` `per-file-ignores` (a few
`zip()` calls in Excel-import commands where adding `strict=True` can't be
safely verified without real production spreadsheets) and narrow, commented
`# type: ignore[...]` lines where django-stubs cannot express a runtime
invariant (documented inline at each site).

## Further reading

- [MALIYET_HESAPLAMA_METODOLOJISI.md](MALIYET_HESAPLAMA_METODOLOJISI.md) — the
  authoritative vehicle cost/profitability calculation methodology.
- [GUNLUK_MALIYET_HESAPLAMA_DETAYLI.md](GUNLUK_MALIYET_HESAPLAMA_DETAYLI.md) —
  daily cost breakdown detail.
