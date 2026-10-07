# ADR 0007: Secure document uploads (S3-compatible storage and virus scanning)

- **Status:** Accepted, 2026-10-07 (approved Phase 1 plan, decision 4; ADR 0003 local pilot)
- **Date:** 2026-10-07 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.

## Context
FR-1.2 requires financial statements, credit reports and supporting files to go to **private object
storage with malware, type and size checks** (SEC-07: allow-listed types, size limits, malware scan,
randomised names, private storage, no direct execution). Uploaded documents are the evidence the later
research relies on, so they must be safe to handle and impossible to alter silently.

## Decision
1. **Pipeline, in this order, and nothing is kept if any step fails:** check the file, scan it, store it,
   record it. If recording fails after storing, the stored object is removed.
2. **Checks on the bytes, not the name.** An allow-list of PDF, Word (docx), Excel (xlsx), CSV, text, PNG and
   JPEG, identified from the file's own contents. The file name and extension must agree with the contents.
   Office files must really be Office files, with no macros, no unsafe paths, bounded size and a bounded
   expansion ratio (zip-bomb guard). PDFs containing scripts, launch actions or embedded files are
   refused. Size limit default 20 MB (configurable up to 25 MB, the scanner's own limit), enforced both
   from the declared length (before the body is read) and while reading. A case holds at most 50 documents.
3. **Virus scanning with ClamAV** (clamd INSTREAM). **Fail closed:** if the scanner cannot be reached or does
   not give a clear answer, the upload is refused with a retryable 503 and nothing is saved. An infected
   file is refused, never stored, and the signature name stays out of responses and audit events.
4. **Private S3-compatible storage** over the standard S3 protocol (works with real S3 or any compatible
   store). Objects use random keys inside the tenant's prefix; **the user's file name is never part of a
   storage path.** Locally this is SeaweedFS (Apache-2.0), because MinIO no longer publishes its images
   on Docker Hub. Swapping stores is configuration.
5. **Immutable metadata.** `case_documents` is append-only (database triggers refuse UPDATE, DELETE and
   TRUNCATE), with the SHA-256, size, detected type, category, uploader and time. A retention and
   controlled-deletion policy is still an open decision.
6. **Access.** Upload needs `case:write`; list and download need `case:read`; every call is tenant-checked
   and cross-tenant attempts are audited. Downloads are attachments with `nosniff` and `no-store`, and
   are sent as a generic binary type so a browser never renders them.
7. **Audit** records upload, rejection (a short reason code only) and download. File names, contents and
   storage locations never appear in audit details or logs.
8. **Switched off unless fully configured** (`S3_*` and `CLAMAV_HOST` together); otherwise uploads answer
   503 and the rest of the product is unaffected.

## Alternatives considered
- **Trusting the browser's content type or extension:** rejected; trivially forged.
- **Scanning asynchronously after storing:** rejected for now; it leaves an unscanned file in storage.
  Synchronous scanning is simpler and safe for a local single-user pilot. Revisit for scale.
- **Storing files in Postgres:** simpler, but poor for large files, backups and later hosting.
- **MinIO:** not available as a published image any more; SeaweedFS chosen as a free S3-compatible equivalent.

## Consequences
- ClamAV and the object store run as two more local containers (compose services `clamav` and `s3`).
  CI starts both from pinned image digests, so the real-service tests always run.
- Uploads are limited to the allow-listed types; a customer sending another type must convert it first.
- Still open: server-side encryption at rest and bucket policies (infrastructure, when hosting is
  decided), retention and deletion, per-tenant quotas and rate limits, and extracting text from uploads
  (a research-phase concern).

## Rollback
Remove the `S3_*` and `CLAMAV_HOST` settings to switch uploads off. `alembic downgrade 0003` drops
`case_documents`; stored objects remain in the bucket and can be deleted from there.
