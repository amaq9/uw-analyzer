# Assisted mode: asking Claude Code to analyse a case (local, test product)

Until the automatic research pipeline exists (ADR 0008), a Claude Code session acts as the analyst.
It reads the case and its uploaded documents, writes a draft recommendation, and submits it through the
same checked API as everything else. **It never records the decision.** You do that.

## What you do
1. Start the local services and the API (see [local-development.md](local-development.md)).
2. In the UI or API, create the case, add the entity, resolve it (or record it as not confirmed), and
   upload the financial statements.
3. Tell Claude Code: **"analyse case `<case id>`"**.
4. Open the draft recommendation in the UI (or `GET /api/v1/cases/<id>/draft-recommendations`). It is
   labelled "Draft recommendation for the underwriter. Not a decision."
5. Record your own decision: adopt, change or reject (`POST .../draft-recommendations/<draft id>/decision`).
   A reason is required to change or reject. Your choices feed the agreement view (`GET /api/v1/agreement`).

## What Claude Code does
1. `uv run python scripts/assisted.py case <id>` reads the case, candidates, documents and earlier drafts.
2. `uv run python scripts/assisted.py fetch <id> <document id> <file>` saves each document to read it.
3. Applies the five areas of the financial statement method (balance sheet, liquidity, gearing,
   receivables aging, cash flow) with the deterministic ratio script. If no aging schedule is disclosed
   it says so rather than inferring one.
4. Searches the web for sector outlook (market sentiment plus macroeconomic impact) and for adverse
   findings, keeping every source address, read time and quoted words. Anything not found is listed as
   an information gap, never invented (P-01, P-02).
5. Writes `draft.json` (shape below) and runs `uv run python scripts/assisted.py submit <id> draft.json`.
6. Reports back in plain language, including limitations. The server applies policy v1.0, so the
   outcome and amount come from the rules, not from the author.

## Draft file shape
```json
{
  "ai_proposed_amount": "900000",
  "financial_findings_weak": false,
  "decline_findings": [],
  "factors": [{"code": "sector_outlook", "explanation": "Why the amount is lower."}],
  "summary": "Two or three sentences.",
  "reasons": [{"text": "Current ratio is 1.6x.",
               "evidence": [{"kind": "document", "document_id": "<uuid>", "quote": "exact words"}]}],
  "information_gaps": ["Receivables aging not disclosed"],
  "source": {"kind": "claude_code_session", "model": "<model>", "skill_version": "<version>",
             "policy_version": "1.0"}
}
```
Web evidence uses `{"kind": "web", "url": "https://...", "retrieved_at": "<time>", "quote": "..."}`.
A verified insolvency, sanctions, fraud or regulatory action, or going-concern doubt goes in
`decline_findings` only when verified; an unverified material finding is refused and needs a person.

## How to tell it worked
- Submit prints HTTP 201 and a draft with `notice` and `test_product: true`.
- The audit trail shows `draft.imported` by `claude-code-session`, with ids only.
- Re-running makes a new version; earlier drafts are kept.

## If it fails
- 409: the entity is not resolved or unconfirmed yet.
- 422: read the message; it names the missing evidence, factor or amount.
- 503 on documents: start the storage and scanner (`docker compose -f infra/docker-compose.dev.yml up -d`).
- Payment behaviour is out of scope: each draft states it was not assessed.
