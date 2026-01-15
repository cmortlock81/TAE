from django.core.management.base import BaseCommand

from invoices.engine.process import process_invoice_pdf


class Command(BaseCommand):
    help = "Process an invoice PDF"

    def add_arguments(self, parser):
        parser.add_argument('filepath', type=str)

    def handle(self, *args, **options):
        filepath = options['filepath']
        process_invoice_pdf(filepath)
        self.stdout.write(self.style.SUCCESS('Invoice processed successfully'))
