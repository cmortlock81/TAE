import re

from invoices.models import Supplier, SupplierTemplate


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
