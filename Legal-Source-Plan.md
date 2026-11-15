# Legal source ingestion
Scope: import the official Constitution into the existing statutes index. Extend court ingestion through an explicit approved export or feed. Keep private cases outside public corpus collection.
API: reuse /research. UI shows article, source, judgment outcome and evidence. Auth: existing lawyer/admin checks. Guardrail: store court criticism only when explicitly stated and quoted. Tickets: constitution import, then court feeds, then reviewed case annotations. Runbook: import into disposable DB first and verify article lookup.
# Research and court export integration

- PRD and flow: lawyer asks for an article or case, API returns matching passages with source references.
- Requirements and schema: read the existing SQLite archive by PDF hash and page. Reuse Judgment and JudgmentChunk for verified exports. Keep source URL and verbatim text.
- API and UI: existing research response gains optional Constitution PDF page and URL. UI links the citation to the PDF page.
- Permissions and failures: existing research authorization applies. A missing optional archive yields no Constitution results. Import failures produce a nonzero exit and retain source exports.
- Guardrails: Constitution results quote the archive directly. Import only authorized court exports. Never infer counsel misconduct or treat cited law as a court finding.
- Tickets: exact article lookup, repeatable export batch runner, source coverage verification, then official feed and structured annotations.
- Runbook: run the importer into a test DB, check citations and run focused tests. Schedule the batch command after providing an authorized export directory and database configuration.
## Court archive collector
PRD: refresh selected court/year partitions into the local research index.
Technical and data contract: use public AWS Open Data objects, deterministic archive identity, the existing judgment schema, and source PDF URLs. Workflow: list metadata, skip already indexed objects, fetch PDF, extract text, upsert. API/UI: existing research and similar-case routes consume the index. Permissions: collector is a local operator task, user queries stay local. Failures: retry on next scheduled invocation and report failures. Guardrails: retain recorded disposition, leave unverified legal annotations empty. Tickets: archive adapter, smoke test, scheduling, source-verified annotations. Deployment: run one bounded batch before enabling a schedule.
