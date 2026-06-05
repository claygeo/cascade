# Deploy runbook

Three platforms: **Supabase** (Postgres, `cascade` schema), **Render** (API +
in-process worker, Docker), **Netlify** (frontend). The first deploy needs ~5
minutes of dashboard clicks; everything else is automated.

## 0. Secrets you'll need

| Secret | How to get it |
| --- | --- |
| `DATABASE_URL` | Supabase → project → Settings → Database → Connection string → **Session pooler** (URI). Format: `postgresql+asyncpg://postgres.<ref>:<pwd>@aws-0-<region>.pooler.supabase.com:5432/postgres` |
| `FERNET_KEY` | `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |
| `OPENROUTER_API_KEY` | your OpenRouter key (set a spend cap on it!) |

> Note the `postgresql+asyncpg://` scheme — SQLAlchemy needs the async driver
> prefix. If Supabase gives you `postgresql://`, just insert `+asyncpg`.

## 1. Database schema (Supabase)

From `backend/` with `DATABASE_URL` set in `.env`:

```bash
alembic revision --autogenerate -m "initial schema"   # first time only
alembic upgrade head                                   # creates the cascade schema + tables
python -m app.seed                                     # seeds the public sample workflow
```

Verify the integration + crash-recovery tests against the live DB:

```bash
RUN_DB_TESTS=1 pytest tests/test_integration.py
```

## 2. API + worker (Render)

The free tier runs the worker **in-process** in the API (one web service, $0).

1. Push this repo to GitHub.
2. Render → **New → Blueprint** → pick the repo. It reads `render.yaml`.
3. Set the `sync: false` env vars when prompted:
   - `DATABASE_URL` — the Session-pooler URI
   - `FERNET_KEY` — the generated key (**must match** what you use elsewhere)
   - `OPENROUTER_API_KEY` — your key
   - `FRONTEND_ORIGIN` — your Netlify URL (fill after step 3; redeploy)
4. Deploy. The start command runs `alembic upgrade head` then serves.
   Health check: `GET /health`. API docs: `/docs`.

## 3. Frontend (Netlify)

```bash
cd frontend
npm install && npm run build
netlify deploy --prod --dir dist        # links/creates a site
```

Then set the API origin so the SPA calls the live backend:

```bash
netlify env:set VITE_API_BASE https://<your-api>.onrender.com
npm run build && netlify deploy --prod --dir dist
```

Finally set `FRONTEND_ORIGIN` on Render to the Netlify URL and redeploy (CORS).

## Notes

- Free Render web services cold-start after ~15 min idle; the first request
  after idle takes a few seconds.
- To run a dedicated worker instead of in-process, uncomment `cascade-worker`
  in `render.yaml` (paid instance) and set `RUN_WORKER_IN_PROCESS=false`.
