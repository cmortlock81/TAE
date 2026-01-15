from decimal import Decimal

from django.db import transaction

from invoices.models import Invoice, InvoiceLine, ProcessingRun

ENGINE_VERSION = "v3.2"
DEFAULT_TOLERANCE = Decimal("0.05")


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
