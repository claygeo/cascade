import { JsonView, Logs, StatusPill, StepGlyph } from "./components";
import type { Run } from "./types";

export function RunSteps({ run }: { run: Run }) {
  return (
    <div className="stack">
      {run.step_runs.map((sr) => (
        <div className="step-card" key={sr.id}>
          <StepGlyph type={sr.type} />
          <div className="grow">
            <div className="row between">
              <div>
                <div className="step-type">{sr.type}</div>
                <strong>{sr.name}</strong>
              </div>
              <div className="row gap8">
                {sr.duration_ms != null && <span className="faint small">{sr.duration_ms} ms</span>}
                <StatusPill status={sr.status} />
              </div>
            </div>
            {sr.logs && sr.logs.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <Logs logs={sr.logs} />
              </div>
            )}
            {sr.error && (
              <div className="alert alert-error" style={{ marginTop: 10 }}>
                {sr.error}
              </div>
            )}
            {sr.status === "succeeded" && sr.output != null && (
              <details style={{ marginTop: 10 }}>
                <summary className="faint small" style={{ cursor: "pointer" }}>
                  step output
                </summary>
                <div style={{ marginTop: 8 }}>
                  <JsonView data={sr.output} />
                </div>
              </details>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
