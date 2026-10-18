import type { DecisionRecord } from "@/components/case/types";
import { ApiRequestError, api } from "@/lib/api/client";

/** The recorded decision for a draft, or null when none has been recorded yet. */
export async function loadDecision(token: string, base: string, draftId: string, signal: AbortSignal) {
  try {
    return await api<DecisionRecord>(token, "GET", `${base}/${draftId}/decision`, undefined, signal);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) return null;
    throw error;
  }
}
