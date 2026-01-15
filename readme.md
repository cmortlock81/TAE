tedious_engine/
├── manage.py
│
├── tedious_engine/                 ← Project config
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── invoices/                       ← Core app (THIS is the product)
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                  ← Database schema (IP)
│   ├── migrations/
│   │   └── __init__.py
│   │
│   ├── engine/                     ← Deterministic engine (logic)
│   │   ├── __init__.py
│   │   ├── extract.py              ← PDF text extraction
│   │   ├── detect.py               ← Supplier detection
│   │   ├── regex.py                ← Regex execution logic
│   │   ├── calculate.py            ← Totals, VAT, validation
│   │   ├── persist.py              ← DB wiring (atomic writes)
│   │   └── process.py              ← Orchestrator
│   │
│   ├── management/
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── process_invoice.py  ← CLI entry point
│   │
│   ├── services/                   ← (optional, future-safe)
│   │   └── __init__.py
│   │
│   └── tests/
│       ├── __init__.py
│       ├── test_engine.py
│       └── test_schema.py
│
└── requirements.txt

## Docker Compose (local development)

Start the stack:

```bash
docker compose up --build
```

Create a superuser:

```bash
docker compose exec web python manage.py createsuperuser
```

Run migrations manually:

```bash
docker compose exec web python manage.py migrate
```

Run the invoice processing command:

```bash
docker compose exec web python manage.py process_invoice --help
```

The app is available at:

```
http://localhost:8000
```

"""
Tedious Engine v3.2
Deterministic Invoice Extraction Engine
Database-Driven Templates + Validation + Full Audit Lineage
"""

# ============================================================
# STANDARD LIBS
# ============================================================

import re
from decimal import Decimal
import pdfplumber

# ============================================================
# DJANGO IMPORTS
# ============================================================

from django.db import models, transaction
from django.utils import timezone

# ============================================================
# SECTION 1: DATABASE SCHEMA (UNCHANGED STRUCTURE, ENFORCED USE)
# ============================================================

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    vat_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    country_code = models.CharField(max_length=2, default="GB")
    created_at = models.DateTimeField(auto_now_add=True)


class SupplierTemplate(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    version = models.PositiveIntegerField()
    regex_config = models.JSONField(help_text="Approved deterministic extraction rules")
    is_active = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        unique_together = ("supplier", "version")


class Invoice(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    external_reference = models.CharField(max_length=255)
    invoice_date = models.DateField(null=True, blank=True)
    total_net = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_vat = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_gross = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="GBP")
    created_at = models.DateTimeField(auto_now_add=True)


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)


class ProcessingRun(models.Model):
    STATUS_CHOICES = (
        ("SUCCESS", "Success"),
        ("WARNING", "Success with Warning"),
        ("FAILED", "Failed Validation"),
    )

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    engine_version = models.CharField(max_length=50)
    used_template = models.ForeignKey(SupplierTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    notes = models.TextField(null=True, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)


ENGINE_VERSION = "v3.2"
DEFAULT_TOLERANCE = Decimal("0.05")

# ============================================================
# SECTION 2: CORE ENGINE LOGIC
# ============================================================

def extract_text_from_pdf(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    return text


def detect_supplier_and_template(text):
    """Identify supplier and load active approved template."""
    for supplier in Supplier.objects.all():
        template = SupplierTemplate.objects.filter(supplier=supplier, is_active=True).first()
        if not template:
            continue
        check = template.regex_config.get("check")
        if check and re.search(check, text, re.IGNORECASE):
            return supplier, template
    return None, None


def run_regex_extraction(text, template):
    cfg = template.regex_config

    def _search(pattern):
        match = re.search(pattern, text)
        return match.group(1) if match else None

    invoice_no = _search(cfg.get("inv_no"))
    declared_gross = _search(cfg.get("total"))

    lines = []
    for match in re.findall(cfg.get("line_pattern"), text):
        desc, qty, rate = match
        qty = Decimal(qty)
        rate = Decimal(rate)
        lines.append({
            "description": desc.strip(),
            "quantity": qty,
            "unit_price": rate,
            "line_total": qty * rate
        })

    net = sum(l["line_total"] for l in lines)
    vat = net * Decimal("0.20")
    gross = net + vat

    return {
        "external_reference": invoice_no or "UNKNOWN",
        "net": net,
        "vat": vat,
        "gross": gross,
        "declared_gross": Decimal(declared_gross) if declared_gross else None,
        "lines": lines,
    }

# ============================================================
# SECTION 3: VALIDATION + PERSISTENCE
# ============================================================

def persist_engine_output(supplier, template, extracted):
    with transaction.atomic():
        invoice = Invoice.objects.create(
            supplier=supplier,
            external_reference=extracted["external_reference"],
            total_net=extracted["net"],
            total_vat=extracted["vat"],
            total_gross=extracted["gross"],
        )

        for line in extracted["lines"]:
            InvoiceLine.objects.create(
                invoice=invoice,
                description=line["description"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                line_total=line["line_total"],
            )

        declared = extracted.get("declared_gross")
        calculated = extracted.get("gross")

        status = "SUCCESS"
        notes = ""

        if declared is not None:
            diff = abs(declared - calculated)
            if diff > DEFAULT_TOLERANCE:
                status = "FAILED"
                notes = f"Declared gross mismatch: £{diff}"
            elif diff > Decimal("0.01"):
                status = "WARNING"
                notes = f"Minor gross discrepancy: £{diff}"

        ProcessingRun.objects.create(
            invoice=invoice,
            engine_version=ENGINE_VERSION,
            used_template=template,
            status=status,
            notes=notes,
        )

        return invoice

# ============================================================
# SECTION 4: EXECUTION ENTRY POINT
# ============================================================

def process_invoice_pdf(filepath):
    text = extract_text_from_pdf(filepath)
    supplier, template = detect_supplier_and_template(text)

    if not supplier or not template:
        raise ValueError("No approved supplier template found")

    extracted = run_regex_extraction(text, template)
    return persist_engine_output(supplier, template, extracted)



Create a clean Django project
django-admin startproject tedious_engine
cd tedious_engine
python manage.py startapp invoices
Move the schema into invoices/models.py
Exactly as written
No tweaks, no “improvements”
Split the engine into an engine/ module
invoices/
├── engine/
│   ├── extract.py
│   ├── regex.py
│   ├── persist.py
│   └── process.py
Create one Django management command
python manage.py process_invoice path/to/sample.pdf
