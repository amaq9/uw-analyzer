# Runbook: reading the notes and the auditor's report (ADR 0021)

The figures from SEC XBRL are only half of an annual report. The notes and the auditor's report can show a
going-concern warning, a covenant breach, a qualified opinion or a customer that is half of revenue.

## What the product does by itself
1. The SEC connector (version 2) keeps the newest 10-K's main document as a hash-checked snapshot, named
   `annual_report` in the retrieval's manifest. If it cannot fetch it, the figures are still kept and the manifest
   says why.
2. Running the analysis reads that text and shows **Notes and auditor's report** in Step 1: per topic, a result
   ("Concern stated", "No concern stated", "For you to read", "Not in the filing") and the filing's own sentences.
3. Three checklist prompts are answered from it. Without the filing they stay "Not assessable" and the gaps say the
   filing was not read.
4. It is information only. It never changes the amount or the outcome.

## If the screen says the printed 10-K was not read
Research runs made before connector version 2 did not fetch it. Start the research again (the worker needs
`CONNECTOR_CONTACT`), wait for it to finish, then analyse again. A new analysis creates a new recommendation version;
older ones stay as they were.

## What an analyst session adds
The text search cannot read covenant headroom, a debt maturity ladder or contingencies. Read the notes in full:

    cd api
    uv run python scripts/assisted.py case <case_id>              # find the run and the SEC call
    uv run python scripts/assisted.py snapshot <case_id> <annual_report_ref> filing.html

Record anything you find with the existing `evidence`, `claim` and `link` commands. Quote the filing exactly and cite
the note number. Never invent a source (P-01, P-02), never write "none" where the filing is silent, and keep
hypothetical risk-factor language out of findings.
