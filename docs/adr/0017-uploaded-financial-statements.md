# ADR 0017: Uploaded financial statements, checked and confirmed by a person

- **Status:** Accepted, 2026-10-12 (Product Owner: "I should be able to upload the financials myself")
- **Date:** 2026-10-12 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Builds on:** ADR 0007 (secure uploads), ADR 0016 (built-in analyzer), P-01/P-02 (no fabricated evidence).

## Decision
1. **Upload, suggest, check, confirm, analyse.** A person uploads a statement (the existing secure upload). The product
   reads **suggested** figures from it (`GET /cases/{id}/documents/{doc}/figures-preview`, needs `case:write`): line labels
   such as "Total current liabilities" are matched and the numbers on the line are read. Supported: PDF with selectable
   text, Excel (.xlsx), CSV, Word (.docx) and text. A scanned picture cannot be read and the product says so.
2. **Nothing is used until a person confirms it.** The person sees each suggestion next to the label found in the
   document, corrects or fills figures, chooses the unit (units, thousands, millions), the currency and whether the
   statements are audited, reviewed or unaudited, and confirms (`POST /cases/{id}/statements`). The confirmed figures are
   stored append-only (`financial_statements`, migration 0014) with who confirmed and when; a later confirmation for the
   same period replaces the earlier one for analysis and the earlier one stays on record. A confirmation must name an
   uploaded document of the case: typed-from-nowhere figures are not accepted.
3. **The analyzer uses confirmed uploads first.** `POST /cases/{id}/analysis` (`financials`: `auto`, `uploaded` or `sec`)
   uses confirmed uploaded statements when present, otherwise SEC data. With uploaded figures no research run is needed,
   so private companies work. The same ratio method, section assessments, consolidated finding, amount proposal and
   draft path apply. The currency of the statements must match the currency of the request.
4. **Honest evidence class.** The figures become DOCUMENT evidence of the uploaded file. Audited statements are recorded
   as a commercial-class source and unaudited or reviewed ones as secondary (weak), declared by the person (`author_declared`).
   Under the evidence rules a weak source alone cannot verify a material finding, and a warning-sign finding needs a
   second independent or official primary source (FR-3.7), so such findings show as partly verified. Every draft states
   that the figures came from a document supplied by the company and whether it is audited.
5. **Limits stated:** the document text beyond the confirmed figures is not analysed; extraction is heuristic and may miss
   or misread lines (hence step 2); scanned pictures, other languages and unusual layouts need manual entry of the
   figures. Extraction reads only; it sends nothing anywhere.
6. **Safety:** only allow-listed file types already passed the upload checks; PDF text is read from the first 80 pages;
   no file content or figures are written to audit events or logs (the audit event has ids and a period count).
