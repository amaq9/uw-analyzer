---
Project: UW Analyzer — Trade Credit Insurance Verified External Research & Evidence Agent
Doc: Handoff — Claude Code (sanitised copy of individual task log)
---

# Handoff — Claude Code (sanitised)

This is a shortened, sanitised copy of the Claude Code session log. It tracks only work assigned to Claude Code; a separate agent works in parallel and has its own tracking. Shared governance (`rulebook.md`, BRD/PRD invariants P-01 to P-10) binds this session too.

## Standing preference: how financial statements are analyzed

Use this lens whenever asked to review new financials. Lead with these five areas, not a P&L summary:

1. **Balance sheet strength:** assets, liabilities, equity buffer, asset quality (goodwill/intangibles), credit ratings.
2. **Liquidity:** current, quick and cash ratios, working capital, near-term debt maturities versus cash, undrawn facilities.
3. **Gearing:** financial debt, net debt/(net cash), lease liabilities, debt/equity, net debt/EBITDA, interest cover.
4. **Accounts receivable aging:** balance, DSO, cash absorbed by receivables, allowance for credit losses. If no aging schedule is disclosed (usual in a 10-K/10-Q), say so rather than infer it.
5. **Cash flow generation:** operating cash flow, free cash flow, FCF after dividends and buybacks, and net change in cash.

End with a short overall credit-style view (strengths, weaknesses, what to watch).

## Task log

### 2026-10-03 — Orientation and scope review
- Read the project files and the BRD and PRD (v1.0, 16 Sep 2026). Summarized scope, phases (0–7), stack and open decisions. No repo changes.

### 2026-10-03 — Financial statement reviews (SEC filings)
- **Starbucks FY2025 10-K:** reviewed with the lens above. Weak liquidity (current ratio 0.72x), shareholders' deficit, free cash flow not covering the dividend.
- **Nike Q2 FY26 10-Q:** reviewed with the lens above. Strong balance sheet (net cash, low gearing), but operating cash flow down 44% and free cash flow not covering the dividend.
- No AR aging schedule was disclosed in either filing; ratios are calculated from the filed statements.
