from invoices.engine.detect import detect_supplier_and_template
from invoices.engine.extract import extract_text_from_pdf
from invoices.engine.persist import persist_engine_output
from invoices.engine.regex import run_regex_extraction


def process_invoice_pdf(filepath):
    text = extract_text_from_pdf(filepath)
    supplier, template = detect_supplier_and_template(text)

    if not supplier or not template:
        raise ValueError("No approved supplier template found")

    extracted = run_regex_extraction(text, template)
    return persist_engine_output(supplier, template, extracted)
