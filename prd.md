Below is a compact, portfolio‑ready spec and delivery plan for the AP Intake & Validation pilot using Docling. It includes workflow/PRD, user stories/epics, data models, system design, example snippets (shaped to match typical FastAPI/LangGraph/Docling usage), and step‑by‑step build/run instructions.

Product requirements (PRD)
- Goal: Turn emailed PDF invoices into validated, structured “prepared bills” ready for approval and ERP import—without executing payments.  
- Scope (pilot):  
  - Sources: Gmail/Graph inbox or file upload to storage.  
  - Extraction: Docling for header + line items; OCR fallback for scans; tiny LLM snippet only when confidence is low.  
  - Validation: structural checks, math checks, 2‑/3‑way match to POs/GRNs, vendor policy and currency/tax rules.  
  - Triage: auto‑ready vs exception bucket with reasons; human review UI to edit/approve.  
  - Export: CSV + JSON payload; optional QuickBooks/Xero sandbox exporter and dry‑run NetSuite/Intacct adapters.  
  - Observability: traces (Langfuse) and errors/perf (Sentry); KPI panel for accuracy, exception rate, cycle time, reviewer minutes.  
- Non‑goals (pilot): payments, vendor onboarding, GL coding automation beyond simple rules.

User stories and epics
- Epic: Ingestion
  - As AP staff, I want invoices captured from email/upload so nothing is missed.  
- Epic: Extraction
  - As the system, I want to parse header and line items from PDFs and store confidence per field.  
- Epic: Validation
  - As finance, I want rules that flag duplicates, math errors, missing POs, or mismatched receipts.  
- Epic: Review & Approval
  - As an approver, I want a side‑by‑side PDF preview, edit fields, and approve to “stage” for export.  
- Epic: Export
  - As finance ops, I want a clean CSV/API payload or dry‑run ERP export after approval.  
- Epic: Observability & KPIs
  - As leadership, I want weekly metrics for accuracy, exception reasons, and time saved.

End‑to‑end workflow
- Receive → Parse (Docling) → Patch low‑confidence fields (LLM if needed) → Validate → Triage (ready vs exception) → Human review (optional) → Stage export (CSV/JSON, optional sandbox API) → Done  
- Interrupts: HumanReview; EscalateToFinance.  
- Retries: bounded backoff on Parse/Validate; DLQ after N failures; replay from UI.

Data model (Postgres, minimal)
- invoices(id UUID PK, vendor_id, file_url, file_hash, status ENUM(received, parsed, validated, exception, ready, staged, done), created_at, updated_at)  
- invoice_extractions(id, invoice_id FK, header_json, lines_json, confidence_json, parser_version, created_at)  
- validations(id, invoice_id FK, pass BOOLEAN, checks_json, rules_version, created_at)  
- exceptions(id, invoice_id FK, reason_code, details_json, resolved_by, resolved_at)  
- staged_exports(id, invoice_id FK, payload_json, format ENUM(csv,json), status ENUM(prepared, sent, failed), destination, created_at)  
- vendors(id, name, currency, tax_id, active BOOLEAN)  
- pos(id, vendor_id FK, po_no, lines_json, status)  
- grns(id, po_id FK, lines_json, received_at)

System design
- API: FastAPI service exposes ingestion, review, export endpoints.  
- Worker: background worker consumes events (invoice.received, parsed, validated) via RabbitMQ; runs state transitions.  
- Agent flow: LangGraph state machine tracks per‑invoice progress and supports interrupts for human edits.  
- Storage: S3/R2/Supabase Storage for PDFs; signed URLs for the UI.  
- Observability: Langfuse client in agent nodes; Sentry SDK in API/worker.  
- Exporters: CSV/SFTP (always), QuickBooks/Xero sandbox (optional), NetSuite/Intacct dry‑run validator.

Key code snippets (illustrative)
- FastAPI file upload endpoint
```python
from fastapi import FastAPI, UploadFile
import hashlib, aiofiles
app = FastAPI()

@app.post("/invoices/upload")
async def upload_invoice(file: UploadFile):
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    # store to S3 and insert invoices row with status="received"
    # publish event "invoice.received" with invoice_id
    return {"hash": file_hash}
```
- LangGraph state definition (conceptual)
```python
from langgraph.graph import StateGraph, END

def receive(ctx): ...
def parse_docling(ctx): ...
def patch_low_conf(ctx): ...
def validate(ctx): ...
def triage(ctx): ...
def stage_export(ctx): ...

graph = StateGraph()
graph.add_node("receive", receive)
graph.add_node("parse", parse_docling)
graph.add_node("patch", patch_low_conf)
graph.add_node("validate", validate)
graph.add_node("triage", triage)
graph.add_node("stage", stage_export)
graph.set_entry_point("receive")
graph.add_edge("receive", "parse")
graph.add_edge("parse", "patch")
graph.add_edge("patch", "validate")
graph.add_edge("validate", "triage")
graph.add_edge("triage", "stage", condition=lambda ctx: ctx["ready"])
graph.add_edge("triage", END, condition=lambda ctx: not ctx["ready"])
runner = graph.compile()
```
- Docling extraction (pseudocode shape)
```python
from docling import Document
doc = Document.from_file(local_pdf_path)
header = {
  "vendor_name": doc.find_text("Vendor"),
  "invoice_no": doc.find_pattern(r"Invoice\s*#:\s*(\S+)"),
  "invoice_date": doc.find_date(),
  "currency": doc.find_currency(),
  "subtotal": doc.find_amount("Subtotal"),
  "tax": doc.find_amount("Tax"),
  "total": doc.find_amount("Total"),
}
lines = doc.find_table(headers=["Description","Qty","Price","Amount"])
confidence = {"header": header_conf, "lines": lines_conf}
```
- Validation rules (sketch)
```python
def math_checks(subtotal, tax, total, lines):
    lines_sum = sum([l["amount"] for l in lines])
    ok_lines = abs(lines_sum - subtotal) < 0.01
    ok_total = abs(subtotal + tax - total) < 0.01
    return ok_lines and ok_total

def business_checks(vendor, po_no, grn_lines):
    po = get_po(po_no)
    if po is None: return False, "PO_NOT_FOUND"
    return compare_lines(po["lines"], grn_lines or []), "OK"
```
- CSV export (canonical)
```python
import csv, io
def to_csv(payload):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["vendor_id","invoice_no","date","currency","subtotal","tax","total"])
    h = payload["header"]
    writer.writerow([h["vendor_id"],h["invoice_no"],h["date"],h["currency"],h["subtotal"],h["tax"],h["total"]])
    writer.writerow([])
    writer.writerow(["sku","description","qty","unit_price","amount"])
    for l in payload["lines"]:
        writer.writerow([l["sku"],l["desc"],l["qty"],l["unit_price"],l["amount"]])
    return buf.getvalue()
```

Build and run instructions
- Prereqs  
  - Python 3.11, Docker, Postgres (Neon/Supabase), RabbitMQ, S3‑compatible storage.  
  - Accounts: QuickBooks sandbox or Xero demo (optional).  
- Setup  
  - Clone repo; configure env: DATABASE_URL, QUEUE_URL, STORAGE_KEYS, SENTRY_DSN, LANGFUSE_KEYS.  
  - Run Alembic migrations; seed vendors/POs/GRNs with sample CSVs.  
  - Start services: `docker compose up` (db, mq, storage, api, worker, ui).  
- Test data  
  - Place sample PDFs in `fixtures/` and call POST /invoices/upload; or forward an email to your capture address.  
  - Open the UI, watch invoices move across statuses; edit an exception and approve; download CSV export.  
- Optional sandbox export  
  - Connect QuickBooks sandbox: set OAuth keys; enable “dry‑run” to preview payload before sending.  
- Observability  
  - Visit Langfuse dashboard to view traces and costs per invoice; check Sentry for errors/perf; load KPI page for accuracy, exception rate, cycle times.  
- Runbook  
  - Restore DB from snapshot; rotate OAuth and storage keys; drain DLQ and replay stuck invoices; roll back a staged export.

Demo script (90 seconds)
- Upload 3 invoices (clean, missing PO, subtotal mismatch).  
- Show Docling extraction and validation checks; one low‑confidence field gets patched by a small LLM call.  
- Fix the mismatch in the review UI; approve and stage; show CSV and (optional) QuickBooks dry‑run.  
- End on KPI tiles: accuracy %, exception breakdown, median time‑to‑ready.

What to publish on your portfolio
- One‑pager with the architecture diagram, demo clip, KPIs before/after, mapping table (invoice → ERP fields), and governance checklist (RBAC, audit logs, “prepare‑and‑propose” only).  
- Link to live docs (OpenAPI), JSON Schemas for payloads, and the test report showing rule coverage.

This plan proves you can build a safe, auditable AP intake lane with Docling at the core, realistic ERP adapters, and the reliability/observability leadership expects—even without paid enterprise sandboxes.
