from django.db import models
from django.utils import timezone


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
