from django.contrib import admin

from invoices.models import (
    Invoice,
    InvoiceLine,
    ProcessingRun,
    Supplier,
    SupplierTemplate,
)


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "vat_number", "country_code", "created_at")
    search_fields = ("name", "vat_number")
    list_filter = ("country_code",)


@admin.register(SupplierTemplate)
class SupplierTemplateAdmin(admin.ModelAdmin):
    list_display = ("supplier", "version", "is_active", "approved_at", "approved_by")
    list_filter = ("is_active",)
    search_fields = ("supplier__name", "approved_by")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "external_reference",
        "supplier",
        "invoice_date",
        "total_gross",
        "currency",
        "created_at",
    )
    search_fields = ("external_reference", "supplier__name")
    list_filter = ("currency",)
    date_hierarchy = "invoice_date"
    inlines = [InvoiceLineInline]


@admin.register(ProcessingRun)
class ProcessingRunAdmin(admin.ModelAdmin):
    list_display = ("invoice", "engine_version", "status", "completed_at")
    list_filter = ("status",)
    search_fields = ("invoice__external_reference", "engine_version")
