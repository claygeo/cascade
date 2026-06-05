import { useEffect, useState } from "react";

import type { Run } from "./types";

const TERMINAL = ["succeeded", "failed", "canceled"];

/**
 * Polls a run until it reaches a terminal state, so the UI streams live
 * per-step progress. Restarts whenever `runId` changes.
 */
export function usePollRun(
  runId: string | null,
  fetcher: (id: string) => Promise<Run>,
  intervalMs = 1200,
) {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRun(null);
    setError(null);
    if (!runId) return;

    let active = true;
    let handle: number | undefined;

    async function tick() {
      try {
        const r = await fetcher(runId!);
        if (!active) return;
        setRun(r);
        if (TERMINAL.includes(r.status)) return;
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      }
      if (active) handle = window.setTimeout(tick, intervalMs);
    }
    tick();

    return () => {
      active = false;
      if (handle) window.clearTimeout(handle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  return { run, error };
}
