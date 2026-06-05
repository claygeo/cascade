import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { JsonView, StatusPill, Topbar } from "../components";
import { usePollRun } from "../hooks";
import { RunSteps } from "../RunSteps";
import type { Run } from "../types";

export default function RunView() {
  const { id } = useParams();
  const { org } = useAuth();
  const { run, error } = usePollRun(id ?? null, (rid) =>
    api<Run>(`/orgs/${org!.id}/runs/${rid}`),
  );

  return (
    <>
      <Topbar />
      <div className="container">
        <Link to="/app" className="link-btn">
          ← Back to dashboard
        </Link>

        {error && (
          <div className="alert alert-error" style={{ marginTop: 16 }}>
            {error}
          </div>
        )}

        {!run ? (
          <div className="center" style={{ padding: 48 }}>
            <span className="spinner" />
          </div>
        ) : (
          <div style={{ marginTop: 16 }}>
            <div className="row between">
              <div>
                <h1 className="mono" style={{ fontSize: 22 }}>
                  run {run.id.slice(0, 8)}
                </h1>
                <div className="faint small" style={{ marginTop: 4 }}>
                  trigger: {run.trigger} · attempt {run.attempts}
                </div>
              </div>
              <StatusPill status={run.status} />
            </div>

            <div style={{ marginTop: 24 }}>
              <RunSteps run={run} />
            </div>

            {run.status === "succeeded" && run.output?.result != null && (
              <div className="panel" style={{ marginTop: 16 }}>
                <div className="step-type" style={{ marginBottom: 8 }}>
                  final output
                </div>
                <JsonView data={run.output.result} />
              </div>
            )}
            {run.status === "failed" && run.error && (
              <div className="alert alert-error" style={{ marginTop: 16 }}>
                {run.error}
              </div>
            )}

            <details style={{ marginTop: 16 }}>
              <summary className="faint small" style={{ cursor: "pointer" }}>
                run input
              </summary>
              <div style={{ marginTop: 8 }}>
                <JsonView data={run.input} />
              </div>
            </details>
          </div>
        )}
      </div>
    </>
  );
}
