import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "./auth";
import type { LogEntry } from "./types";

export function Topbar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="topbar">
      <Link to="/" className="brand">
        <span className="brand-dot" /> Cascade
      </Link>
      <div className="nav-actions">
        {user ? (
          <>
            <Link to="/app" className="btn btn-ghost btn-sm">
              Dashboard
            </Link>
            <span className="muted small">{user.email}</span>
            <button
              className="btn btn-secondary btn-sm"
              onClick={async () => {
                await logout();
                nav("/");
              }}
            >
              Sign out
            </button>
          </>
        ) : (
          <>
            <Link to="/login" className="btn btn-ghost btn-sm">
              Sign in
            </Link>
            <Link to="/register" className="btn btn-primary btn-sm">
              Get started
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export function StatusPill({ status }: { status: string }) {
  return (
    <span className={`pill ${status}`}>
      <span className="dot" />
      {status}
    </span>
  );
}

export function JsonView({ data }: { data: unknown }) {
  return <pre className="json">{JSON.stringify(data, null, 2)}</pre>;
}

export function Logs({ logs }: { logs: LogEntry[] }) {
  if (!logs || logs.length === 0) return null;
  return (
    <div className="logs">
      {logs.map((l, i) => (
        <div className="log-line" key={i}>
          <span className={`lvl ${l.level}`}>{l.level}</span>
          <span>{l.message}</span>
        </div>
      ))}
    </div>
  );
}

const GLYPHS: Record<string, string> = {
  http_fetch: "↯",
  llm: "✶",
  transform: "⤳",
  conditional: "?",
  output: "▣",
};

export function StepGlyph({ type }: { type: string }) {
  return <span className="glyph">{GLYPHS[type] ?? "•"}</span>;
}
