import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ApiError } from "../api";
import { JsonView, StatusPill, StepGlyph, Topbar } from "../components";
import { usePollRun } from "../hooks";
import { RunSteps } from "../RunSteps";
import type { Run } from "../types";

const GITHUB_URL = "https://github.com/claygeo/cascade";

interface Sample {
  id: string;
  name: string;
  description: string;
  steps: { position: number; type: string; name: string; config: any }[];
}

const FEATURES = [
  {
    title: "Crash-safe job engine",
    body: "Runs execute on a separate worker via a Postgres queue with leases + heartbeats. If a worker dies mid-run, another reclaims and re-runs it.",
  },
  {
    title: "Provider-agnostic LLM",
    body: "One adapter reaches both OpenAI and Anthropic models through OpenRouter. Bring your own key — encrypted at rest with Fernet.",
  },
  {
    title: "Multi-tenant + roles",
    body: "Orgs, members, and owner/editor/viewer permissions, enforced server-side on every request. No client-trusted tenancy.",
  },
];

export default function Landing() {
  const [sample, setSample] = useState<Sample | null>(null);
  const [tone, setTone] = useState("witty");
  const [runId, setRunId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const { run } = usePollRun(runId, (id) => api<Run>(`/public/runs/${id}`, { auth: false }));

  useEffect(() => {
    api<Sample>("/public/sample", { auth: false })
      .then(setSample)
      .catch(() => setErr("Sample workflow isn't seeded yet — start the worker."));
  }, []);

  const busy = starting || run?.status === "queued" || run?.status === "running";

  async function runSample() {
    setErr(null);
    setStarting(true);
    try {
      const r = await api<{ id: string }>("/public/sample/runs", {
        method: "POST",
        body: { input: { tone } },
        auth: false,
      });
      setRunId(r.id);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Failed to start run");
    } finally {
      setStarting(false);
    }
  }

  const result = run?.status === "succeeded" ? run.output?.result : null;

  return (
    <>
      <Topbar />
      <div className="container">
        <div className="hero">
          <h1>Build, run, and monitor AI workflows.</h1>
          <p>
            Cascade chains API calls, LLM steps, and logic into reliable workflows — executed as
            background jobs with live per-step logs. FastAPI · PostgreSQL · OpenAI/Anthropic · Docker.
          </p>
          <div className="row gap8" style={{ marginTop: 24 }}>
            <Link to="/register" className="btn btn-primary btn-lg">
              Get started free
            </Link>
            <a className="btn btn-secondary btn-lg" href={GITHUB_URL} target="_blank" rel="noreferrer">
              View source on GitHub
            </a>
          </div>
        </div>

        <div className="card">
          <div className="row between wrap" style={{ gap: 12 }}>
            <div>
              <div className="row gap8">
                <h2>Try it live</h2>
                <span className="tag">no signup</span>
              </div>
              <p className="muted small" style={{ marginTop: 4 }}>
                {sample ? sample.description : "Loading sample workflow…"}
              </p>
            </div>
            <div className="row gap8">
              <select
                className="select"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                style={{ width: 120 }}
                disabled={busy}
              >
                <option value="witty">witty</option>
                <option value="serious">serious</option>
                <option value="hype">hype</option>
              </select>
              <button className="btn btn-primary" onClick={runSample} disabled={busy || !sample}>
                {busy ? (
                  <>
                    <span className="spinner" /> Running…
                  </>
                ) : (
                  "Run sample"
                )}
              </button>
            </div>
          </div>

          {err && (
            <div className="alert alert-error" style={{ marginTop: 16 }}>
              {err}
            </div>
          )}

          {!run && sample && (
            <div className="stack" style={{ marginTop: 16 }}>
              {sample.steps.map((s) => (
                <div className="step-card" key={s.position}>
                  <StepGlyph type={s.type} />
                  <div className="grow">
                    <div className="step-type">{s.type}</div>
                    <strong>{s.name}</strong>
                  </div>
                </div>
              ))}
            </div>
          )}

          {run && (
            <div style={{ marginTop: 16 }}>
              <div className="row between" style={{ marginBottom: 12 }}>
                <span className="faint small mono">run {run.id.slice(0, 8)}</span>
                <StatusPill status={run.status} />
              </div>
              <RunSteps run={run} />
              {result && (
                <div className="panel" style={{ marginTop: 16 }}>
                  <div className="step-type" style={{ marginBottom: 8 }}>
                    final output
                  </div>
                  <JsonView data={result} />
                </div>
              )}
              {run.status === "failed" && (
                <div className="alert alert-error" style={{ marginTop: 12 }}>
                  {run.error}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="row wrap" style={{ marginTop: 32, gap: 16 }}>
          {FEATURES.map((f) => (
            <div className="card grow" key={f.title} style={{ minWidth: 240, flexBasis: 280 }}>
              <h3>{f.title}</h3>
              <p className="muted small" style={{ marginTop: 6 }}>
                {f.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
