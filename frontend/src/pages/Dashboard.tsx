import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { StatusPill, Topbar } from "../components";
import type { RunSummary, WorkflowSummary } from "../types";

export default function Dashboard() {
  const { org } = useAuth();
  const [wfs, setWfs] = useState<WorkflowSummary[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!org) return;
    let on = true;
    (async () => {
      try {
        const [w, r] = await Promise.all([
          api<WorkflowSummary[]>(`/orgs/${org.id}/workflows`),
          api<RunSummary[]>(`/orgs/${org.id}/runs?limit=8`),
        ]);
        if (on) {
          setWfs(w);
          setRuns(r);
        }
      } finally {
        if (on) setLoading(false);
      }
    })();
    return () => {
      on = false;
    };
  }, [org]);

  return (
    <>
      <Topbar />
      <div className="container">
        <div className="row between">
          <h1>Workflows</h1>
          <Link to="/app/workflows/new" className="btn btn-primary">
            New workflow
          </Link>
        </div>

        {loading ? (
          <div className="center" style={{ padding: 48 }}>
            <span className="spinner" />
          </div>
        ) : (
          <div style={{ marginTop: 24 }}>
            {wfs.length === 0 ? (
              <div className="empty">No workflows yet — create your first one.</div>
            ) : (
              <div className="stack">
                {wfs.map((w) => (
                  <Link to={`/app/workflows/${w.id}`} key={w.id} className="card card-hover">
                    <div className="row between">
                      <div>
                        <strong>{w.name}</strong>
                        {w.is_sample && (
                          <span className="tag" style={{ marginLeft: 8 }}>
                            sample
                          </span>
                        )}
                        <div className="muted small" style={{ marginTop: 4 }}>
                          {w.description || "No description"}
                        </div>
                      </div>
                      <span className="faint small">
                        updated {new Date(w.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}

            {runs.length > 0 && (
              <>
                <h2 style={{ marginTop: 40 }}>Recent runs</h2>
                <div className="stack" style={{ marginTop: 16 }}>
                  {runs.map((r) => (
                    <Link to={`/app/runs/${r.id}`} key={r.id} className="card card-hover">
                      <div className="row between">
                        <span className="mono small">run {r.id.slice(0, 8)}</span>
                        <div className="row gap8">
                          <span className="faint small">
                            {new Date(r.created_at).toLocaleTimeString()}
                          </span>
                          <StatusPill status={r.status} />
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}
