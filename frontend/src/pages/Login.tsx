import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../api";
import { useAuth } from "../auth";
import { Topbar } from "../components";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(email, password);
      nav("/app");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Topbar />
      <div className="container-narrow">
        <h1>Sign in</h1>
        <p className="muted" style={{ marginTop: 8 }}>
          Welcome back to Cascade.
        </p>
        <form className="stack" style={{ marginTop: 24 }} onSubmit={submit}>
          {err && <div className="alert alert-error">{err}</div>}
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
              required
            />
          </div>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? <span className="spinner" /> : "Sign in"}
          </button>
        </form>
        <p className="muted small" style={{ marginTop: 16 }}>
          No account? <Link to="/register">Create one</Link>
        </p>
      </div>
    </>
  );
}
