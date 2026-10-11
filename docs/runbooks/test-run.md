# Test run script (plain English)

For the Product Owner. Local, personal test product. Nothing here sends a decision anywhere. Public U.S.-listed
companies only (SEC filings).

## Before you start (once per day)
1. Docker Desktop open; in PowerShell: `docker ps` shows postgres, redis, s3, clamav as `Up`.
2. Window B, the app: `cd api` then `uv run python scripts/dev_server.py` (restart it after any new version so it picks up the latest code). Open `MY-LOGIN-TOKENS.txt` for your login codes.
3. Window D, the worker: `cd api`, `$env:CONNECTOR_CONTACT = "your address"`, `uv run python scripts/worker.py`.
4. Window E, the web page: `cd web`, `$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"`, `npm run dev`.
5. Browser: http://localhost:3000/sign-in. Paste the **UNDERWRITER** code, press the button twice if needed, then "Continue to workspace".
   (Codes live in memory: refreshing the page signs you out.)

## Test 1: a full case, start to finish
1. **Cases, New case.** Legal name exactly as registered (for example `Under Armour, Inc.`), jurisdiction `United States`, industry, a requested amount and currency. Save.
2. **Open the case, Entity tab.** Add the candidate entity (same legal name; put the SEC CIK in the registration number if you know it). Press **Choose this entity**. Expected: status "Entity resolved" and "Research may start".
   - *Stop test:* add two candidates first. Expected: status "Entity ambiguous", research blocked until you choose.
3. **Research tab.** Countries `US` (add `CA` etc. if relevant). **Create research plan**, then **Start research**. Expected: steps turn to Succeeded for SEC, GLEIF, OFAC and World Bank; the news steps may Fail (rate limit) and say so. "Accessed: Yes" only where a call succeeded. Press **Show source material** to see the exact copy fetched.
4. **Draft recommendation tab, press "Analyse the research and prepare a draft".** The built-in analyzer reads the
   exact copies fetched from the public sources, assesses the five financial areas (Strong, Satisfactory, Needs
   attention or Weak, in words, with reasons and a trend), adds the sanctions, entity and country findings, proposes an
   amount, and prepares the **draft recommendation** (approve an amount, or decline). Nothing is decided. It can be run
   again; it adds a new draft version and no duplicate findings.
   - A possible sanctions-list match makes **no draft**: a review item is raised for a person instead.
   - A company with no SEC data (private or non-U.S.) gets a plain message about what is missing.
   - Optional: ask Claude Code in the chat "analyse case <id>" to add judgement on top (it records the same way).
5. **Evidence and claims tab.** Each finding shows its verification status, how fresh the evidence is, and (separately) which source was accessed and when. Nobody can type a status in.
6. **Review items tab.** Normally empty. If two reliable sources disagree, an item appears; sign in with the **REVIEWER** code to resolve it in writing.
7. **Draft recommendation tab.** Read the draft ("Not a decision"), open the full draft for reasons and sources, then record **your own decision**: adopt, change (outcome and amount, with a reason) or reject (with a reason). It cannot be edited afterwards.
8. **Report tab.** All checks should pass. **Complete the report.** Then change something (ask Claude Code to add a finding) and complete again: a new version appears; version 1 is unchanged and shows "matches its recorded hash".
9. **Audit trail** (sidebar, sign in with the AUDITOR code): every action above is listed, with no case content.
10. **Draft against decision** (sidebar): your decision appears next to the draft.

## Test 1b: your own financial statements (private or any company)
1. Create the case and choose the entity as in Test 1 (steps 1 and 2). Research is not needed.
2. **Documents tab, upload** your financial statements (PDF with selectable text, Excel, CSV or Word), category *Financial statement*.
3. Press **Read figures** next to the file. The product suggests figures next to the exact line label it found. Check each
   against your document, correct or fill any, choose **unit** (units, thousands, millions), **currency** and whether the
   statements are **audited**, then press **Confirm these figures**.
4. **Draft recommendation tab, Analyse.** The analysis uses your confirmed figures (the currency must match the request).
   Unaudited statements show as weaker evidence in the findings.

## Test 2: things that must refuse
- Research before the entity is chosen: blocked with a plain reason.
- Reject or change a draft without a reason: the button stays disabled.
- Complete a report while a check fails: button disabled, reason shown.
- A look-alike company name on SEC: that step ends "no unique match" and nothing is guessed.
- Sign in with the **AUDITOR** code: you can read everything but cannot decide or complete.

## Known limits today
- Adverse news and court records are not covered; the news index often rate-limits.
- Sector outlook is not covered (only country-level economic data).
- Financial statements are read from the SEC's structured data, not the printed filing text.
- Documents you upload are stored and scanned but the analyst reads SEC data; uploads matter for private companies later.
- Screens for adding evidence or claims by hand do not exist: the analyst (Claude Code) records them.
