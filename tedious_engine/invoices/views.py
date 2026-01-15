import tempfile

from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import redirect, render

from invoices.engine.process import process_invoice_pdf
from invoices.models import Invoice, ProcessingRun, Supplier


STATUS_LABELS = {
    "SUCCESS": "Success",
    "WARNING": "Warning",
    "FAILED": "Failed",
}


def dashboard(request):
    if request.method == "POST":
        uploaded = request.FILES.get("invoice_file")
        if not uploaded:
            messages.error(request, "Select a PDF to upload.")
            return redirect("dashboard")

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
                for chunk in uploaded.chunks():
                    temp_file.write(chunk)
                temp_file.flush()
                process_invoice_pdf(temp_file.name)
            messages.success(request, "Invoice uploaded and processed.")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Upload failed: {exc}")
        return redirect("dashboard")

    totals = {
        "suppliers": Supplier.objects.count(),
        "invoices": Invoice.objects.count(),
        "processing_runs": ProcessingRun.objects.count(),
    }

    total_gross = (
        Invoice.objects.aggregate(total=Sum("total_gross")).get("total") or 0
    )

    recent_invoices = (
        Invoice.objects.select_related("supplier")
        .order_by("-created_at")
        .only("id", "external_reference", "supplier__name", "created_at", "total_gross")
    )[:5]

    status_counts = ProcessingRun.objects.values("status").annotate(count=Count("id"))
    status_summary = [
        {
            "label": STATUS_LABELS.get(item["status"], item["status"]),
            "count": item["count"],
        }
        for item in status_counts
    ]

    context = {
        "totals": totals,
        "total_gross": total_gross,
        "recent_invoices": recent_invoices,
        "status_summary": status_summary,
    }
    return render(request, "invoices/dashboard.html", context)
