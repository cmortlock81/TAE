import re
from decimal import Decimal


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
