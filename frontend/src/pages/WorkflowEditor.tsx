import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { StepGlyph, Topbar } from "../components";
import type { ProviderKey, StepType, Workflow } from "../types";

const STEP_TYPES: StepType[] = ["http_fetch", "llm", "transform", "conditional", "output"];

const HINTS: Record<StepType, string> = {
  http_fetch: '{\n  "method": "GET",\n  "url": "https://hacker-news.firebaseio.com/v0/topstories.json"\n}',
  llm: '{\n  "prompt": "Summarize: {{ steps.fetch.output.body }}",\n  "max_tokens": 300\n}',
  transform: '{\n  "template": { "first_id": "{{ steps.fetch.output.body.0 }}" }\n}',
  conditional: '{\n  "left": "{{ steps.fetch.output.status_code }}",\n  "op": "==",\n  "right": 200\n}',
  output: '{\n  "value": { "result": "{{ steps.llm.output.content }}" }\n}',
};

interface EditStep {
  type: StepType;
  name: string;
  configText: string;
}

function KeyAdder({ orgId, onAdded }: { orgId?: string; onAdded: (k: ProviderKey) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (!orgId) return null;

  async function add() {
    setBusy(true);
    setErr(null);
    try {
      const k = await api<ProviderKey>(`/orgs/${orgId}/keys`, { method: "POST", body: { name, key } });
      onAdded(k);
      setOpen(false);
      setName("");
      setKey("");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Failed to add key");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: 12 }}>
      {!open ? (
        <button className="link-btn" onClick={() => setOpen(true)}>
          + Add your own OpenRouter key (BYOK)
        </button>
      ) : (
        <div className="panel">
          {err && (
            <div className="alert alert-error" style={{ marginBottom: 8 }}>
              {err}
            </div>
          )}
          <div className="row gap8 wrap">
            <input className="input grow" placeholder="Key name" value={name} onChange={(e) => setName(e.target.value)} />
            <input
              className="input grow mono"
              placeholder="sk-or-v1-…"
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            <button className="btn btn-primary btn-sm" onClick={add} disabled={busy || !name || !key}>
              {busy ? <span className="spinner" /> : "Add"}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
          <p className="faint small" style={{ marginTop: 8 }}>
            Stored encrypted (Fernet); we only ever display the last 4 characters.
          </p>
        </div>
      )}
    </div>
  );
}

export default function WorkflowEditor() {
  const { id } = useParams();
  const isNew = !id;
  const { org } = useAuth();
  const nav = useNavigate();

  const [name, setName] = useState("Untitled workflow");
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState<EditStep[]>([{ type: "llm", name: "summarize", configText: HINTS.llm }]);
  const [readOnly, setReadOnly] = useState(false);
  const [keys, setKeys] = useState<ProviderKey[]>([]);
  const [keyId, setKeyId] = useState("");
  const [inputText, setInputText] = useState("{}");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(!isNew);

  useEffect(() => {
    if (!org) return;
    api<ProviderKey[]>(`/orgs/${org.id}/keys`).then(setKeys).catch(() => {});
  }, [org]);

  useEffect(() => {
    if (isNew || !org) return;
    let on = true;
    (async () => {
      try {
        const wf = await api<Workflow>(`/orgs/${org.id}/workflows/${id}`);
        if (!on) return;
        setName(wf.name);
        setDescription(wf.description || "");
        setReadOnly(wf.is_sample);
        setSteps(
          wf.steps.map((s) => ({
            type: s.type as StepType,
            name: s.name,
            configText: JSON.stringify(s.config, null, 2),
          })),
        );
      } catch (e) {
        if (on) setError(e instanceof ApiError ? e.message : "Failed to load workflow");
      } finally {
        if (on) setLoading(false);
      }
    })();
    return () => {
      on = false;
    };
  }, [id, org, isNew]);

  const setStep = (i: number, patch: Partial<EditStep>) =>
    setSteps((s) => s.map((st, j) => (j === i ? { ...st, ...patch } : st)));
  const addStep = () =>
    setSteps((s) => [...s, { type: "llm", name: `step_${s.length + 1}`, configText: HINTS.llm }]);
  const removeStep = (i: number) => setSteps((s) => s.filter((_, j) => j !== i));
  const move = (i: number, dir: -1 | 1) =>
    setSteps((s) => {
      const j = i + dir;
      if (j < 0 || j >= s.length) return s;
      const copy = [...s];
      [copy[i], copy[j]] = [copy[j], copy[i]];
      return copy;
    });

  function buildSteps() {
    return steps.map((s, i) => {
      let config: unknown;
      try {
        config = JSON.parse(s.configText || "{}");
      } catch {
        throw new Error(`Step ${i + 1} ("${s.name}") has invalid JSON config`);
      }
      return { type: s.type, name: s.name, config };
    });
  }

  async function save(): Promise<string | null> {
    setError(null);
    setSaving(true);
    try {
      const payload = { name, description: description || null, steps: buildSteps() };
      if (isNew) {
        const wf = await api<Workflow>(`/orgs/${org!.id}/workflows`, { method: "POST", body: payload });
        nav(`/app/workflows/${wf.id}`);
        return wf.id;
      }
      await api(`/orgs/${org!.id}/workflows/${id}`, { method: "PUT", body: payload });
      return id!;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function run() {
    setError(null);
    let input: unknown;
    try {
      input = JSON.parse(inputText || "{}");
    } catch {
      setError("Run input must be valid JSON");
      return;
    }
    setRunning(true);
    try {
      let wfId = id;
      if (isNew) {
        const saved = await save();
        if (!saved) return;
        wfId = saved;
      }
      const r = await api<{ id: string }>(`/orgs/${org!.id}/workflows/${wfId}/runs`, {
        method: "POST",
        body: { input, provider_key_id: keyId || null },
      });
      nav(`/app/runs/${r.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }

  if (loading)
    return (
      <>
        <Topbar />
        <div className="center" style={{ height: "50vh" }}>
          <span className="spinner" />
        </div>
      </>
    );

  return (
    <>
      <Topbar />
      <div className="container">
        <Link to="/app" className="link-btn">
          ← Back
        </Link>
        {error && (
          <div className="alert alert-error" style={{ marginTop: 16 }}>
            {error}
          </div>
        )}
        {readOnly && (
          <div className="alert alert-info" style={{ marginTop: 16 }}>
            This is the read-only sample workflow.
          </div>
        )}

        <div className="row between" style={{ marginTop: 16 }}>
          <h1>{isNew ? "New workflow" : "Edit workflow"}</h1>
          <div className="row gap8">
            {!readOnly && (
              <button className="btn btn-secondary" onClick={save} disabled={saving}>
                {saving ? <span className="spinner" /> : "Save"}
              </button>
            )}
            <button className="btn btn-primary" onClick={run} disabled={running}>
              {running ? (
                <>
                  <span className="spinner" /> Running…
                </>
              ) : (
                "Run"
              )}
            </button>
          </div>
        </div>

        <div className="card" style={{ marginTop: 16 }}>
          <div className="field">
            <label>Name</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} disabled={readOnly} />
          </div>
          <div className="field" style={{ marginTop: 12 }}>
            <label>Description</label>
            <input
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={readOnly}
            />
          </div>
        </div>

        <h2 style={{ marginTop: 32 }}>Steps</h2>
        <div className="stack" style={{ marginTop: 16 }}>
          {steps.map((s, i) => (
            <div className="card" key={i}>
              <div className="row between">
                <div className="row gap8">
                  <StepGlyph type={s.type} />
                  <span className="faint small">step {i + 1}</span>
                </div>
                {!readOnly && (
                  <div className="row gap8">
                    <button className="btn btn-ghost btn-sm" onClick={() => move(i, -1)} disabled={i === 0}>
                      ↑
                    </button>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => move(i, 1)}
                      disabled={i === steps.length - 1}
                    >
                      ↓
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => removeStep(i)}>
                      Remove
                    </button>
                  </div>
                )}
              </div>
              <div className="row gap8" style={{ marginTop: 12 }}>
                <div className="field" style={{ width: 160 }}>
                  <label>Type</label>
                  <select
                    className="select"
                    value={s.type}
                    disabled={readOnly}
                    onChange={(e) => {
                      const nextType = e.target.value as StepType;
                      const blank = s.configText.trim() === "" || s.configText.trim() === "{}";
                      setStep(i, { type: nextType, configText: blank ? HINTS[nextType] : s.configText });
                    }}
                  >
                    {STEP_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field grow">
                  <label>Name</label>
                  <input
                    className="input"
                    value={s.name}
                    onChange={(e) => setStep(i, { name: e.target.value })}
                    disabled={readOnly}
                  />
                </div>
              </div>
              <div className="field" style={{ marginTop: 12 }}>
                <label>Config (JSON) — reference earlier steps with {"{{ steps.NAME.output… }}"}</label>
                <textarea
                  className="textarea"
                  value={s.configText}
                  onChange={(e) => setStep(i, { configText: e.target.value })}
                  disabled={readOnly}
                  spellCheck={false}
                  rows={6}
                />
              </div>
            </div>
          ))}
          {!readOnly && (
            <button className="btn btn-secondary" onClick={addStep}>
              + Add step
            </button>
          )}
        </div>

        <h2 style={{ marginTop: 32 }}>Run</h2>
        <div className="card" style={{ marginTop: 16 }}>
          <div className="field">
            <label>Input (JSON)</label>
            <textarea
              className="textarea"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              rows={3}
              spellCheck={false}
            />
          </div>
          <div className="field" style={{ marginTop: 12 }}>
            <label>API key for LLM steps</label>
            <select className="select" value={keyId} onChange={(e) => setKeyId(e.target.value)}>
              <option value="">Server default (shared sample key)</option>
              {keys.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name} (••{k.last4})
                </option>
              ))}
            </select>
          </div>
          <KeyAdder orgId={org?.id} onAdded={(k) => setKeys((ks) => [k, ...ks])} />
        </div>
      </div>
    </>
  );
}
