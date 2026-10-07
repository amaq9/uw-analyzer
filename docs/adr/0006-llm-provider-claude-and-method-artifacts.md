# ADR 0006: Claude as the AI provider, with versioned method artifacts

- **Status:** Accepted, 2026-10-07 (Product Owner decision: use Claude, guided by the project's skills)
- **Date:** 2026-10-07 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.

## Context
The research, financial analysis and draft recommendation need an AI model (PRD section 8, ADR 0005).
The provider and web tools were open decisions (PRD section 19). The Product Owner chose **Claude via the
Anthropic API**, and asked that the **skills added to the project** help Claude reach its judgement.
Those skills are Claude Code skills (local to the developer's tool), so the running product cannot call
them directly and needs its own copies of the method.

## Decision
1. **Provider:** Claude through the Anthropic API, behind a **provider-neutral interface** (PRD section 8),
   so the provider or model can be changed by configuration. The model name is configuration, never
   hard-coded, and is recorded on every run (P-10). Starting default: `claude-sonnet-5-5` for extraction
   and analysis; a stronger model may be chosen for the final recommendation if testing shows a need.
2. **Method artifacts, versioned in the repo or private store, never scattered across the code:**
   - **Financial analysis method:** derived from the adapted `financial-statement-assessment` skill: the
     five areas in order (balance sheet strength, liquidity, gearing, receivables aging, cash flow), "not
     disclosed" instead of estimates, indicative-only benchmarks, no decision language. It becomes the
     versioned instruction set for the analysis step.
   - **Ratio calculator:** the skill's `calculate_ratios.py` becomes a **deterministic tool** the analysis
     step calls, so ratios are computed by code from extracted figures, never by the model's arithmetic.
   - **Recommendation policy:** the Product Owner's approved policy (v1.0), applied in a **separate step**
     from the analysis. The analysis step informs; only the recommendation step produces a draft
     (ADR 0005).
   - The research protocol prompt (consolidated prompt) as already planned.
   Every run records the version of each artifact (P-10).
3. **Two-step design.** (a) **Analyse:** extract figures from the supplied documents with provenance
   (the quote and where it appears), compute ratios with the tool, and write the five-area findings.
   (b) **Recommend:** apply the policy to the findings and produce the draft with reasons linked to
   evidence. Each step returns a **structured, schema-validated** result.
4. **Model output is untrusted input** (PRD section 8). It is validated for schema, enums, lengths, evidence
   links and policy limits before anything is stored. The model cannot set a verification status, mark a
   source as accessed, exceed the requested amount, go below the policy's 20% floor as an approval, or
   override the automatic-decline rules (those need verified evidence, P-06).
5. **Prompt injection:** uploaded documents and retrieved pages are data, never instructions.
   They are delimited, and tests include adversarial documents.
6. **Secrets:** the Product Owner's API key lives in a local environment variable (for example
   `ANTHROPIC_API_KEY`), never in Git, logs, prompts or the browser. It is never typed into chat.
7. **No training use.** Case content must not be used to train models unless a future policy approves it
   (PRD section 8). The Product Owner should confirm their own account's data terms.

## Data handling (read this)
- Calling the API **sends text from the uploaded documents, and the policy text, to Anthropic.** The policy
  describes how credit decisions are made and is proprietary; the Product Owner accepts that it is sent to
  the provider as part of the instructions for this personal test.
- Payment behaviour data is out of scope and is never requested or sent.
- Use public filings and made-up cases until the Product Owner confirms what their office allows.
- Logs and audit events never contain document text, figures or the policy text.

## Alternatives considered
- **Another provider:** possible later through the neutral interface; not chosen.
- **Calling the Claude Code skill from the product:** not possible; skills run inside the developer tool.
- **Letting the model do the arithmetic:** rejected; ratios come from code.

## Consequences
- A small recurring API cost, and a key the Product Owner must create and keep private.
- The analysis and recommendation steps are separately versioned and testable, and the Product Owner's
  testing (AI draft versus their own outcome) can point to which step needs tuning.
- Documents and the policy leave the laptop during analysis; this is accepted for the personal test only.

## Rollback
Switch the provider or model by configuration, or disable the AI steps; the case, entity and audit
features keep working without them.
