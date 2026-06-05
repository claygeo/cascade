# Upwork proposal draft

> Paste into Upwork (via Hermes). Replace `[DEMO_URL]` once Netlify is live.
> Keep it short — the demo does the talking.

---

Hi — instead of just telling you I can build this, I built a working miniature of
exactly what you described so you can click around before we even talk.

**Live demo:** [DEMO_URL]  (hit "Run sample" on the landing page — no signup)
**Source:** https://github.com/claygeo/cascade

It's an AI workflow SaaS: users sign up, build a workflow out of ordered steps
(fetch an API → call an LLM → transform → branch → output), run it as a
background job, and watch live per-step logs and results.

It's built on your exact stack and covers the pieces in your post:

- **FastAPI** backend, **PostgreSQL** (async SQLAlchemy + Alembic), **Docker**.
- **Background jobs**: runs execute on a worker via a Postgres queue
  (`SELECT … FOR UPDATE SKIP LOCKED`) with leases + heartbeats — if a worker dies
  mid-run, another reclaims and finishes it. There's a test that proves it.
- **OpenAI + Anthropic**: one provider-agnostic adapter reaches both; users can
  bring their own key (encrypted at rest).
- **Accounts, permissions, logging**: multi-tenant orgs with owner/editor/viewer
  roles enforced server-side, structured per-step logs.

The README has an architecture diagram and a section mapping each of your
requirements to where it lives in the code, so a 5-minute read tells you how I
think about structuring this kind of system as it grows.

I'm comfortable with the rate you posted and can start right away. Happy to walk
through the code or adapt the architecture to what you already have. What would
be most useful as a next step?

— Clayton
