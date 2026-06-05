import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../api";
import { useAuth } from "../auth";
import { Topbar } from "../components";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await register(email, password, fullName || undefined);
      nav("/app");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Topbar />
      <div className="container-narrow">
        <h1>Create your workspace</h1>
        <p className="muted" style={{ marginTop: 8 }}>
          Start building AI workflows in seconds.
        </p>
        <form className="stack" style={{ marginTop: 24 }} onSubmit={submit}>
          {err && <div className="alert alert-error">{err}</div>}
          <div className="field">
            <label>Name</label>
            <input className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Ada Lovelace" />
          </div>
          <div className="field">
            <label>Email</label>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
            <span className="faint small">At least 8 characters.</span>
          </div>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? <span className="spinner" /> : "Create account"}
          </button>
        </form>
        <p className="muted small" style={{ marginTop: 16 }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </>
  );
}
