# core/management/commands/import_stockitems.py
import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import StockItem


# Fallback hardcoded data for 58 items (MESS ST26.xlsx equivalent)
STOCK_ITEMS_DATA = [
    ("Tamatar", "Sabzi", "kg"),
    ("Aloo", "Sabzi", "kg"),
    ("Lal Aloo", "Sabzi", "kg"),
    ("Mircha", "Sabzi", "kg"),
    ("Matar", "Sabzi", "kg"),
    ("Pattagobhi", "Sabzi", "kg"),
    ("Shimla Mirch", "Sabzi", "kg"),
    ("Gobhi", "Sabzi", "kg"),
    ("Gajar", "Sabzi", "kg"),
    ("Dhaniya", "Sabzi", "kg"),
    ("Palak", "Sabzi", "kg"),
    ("Lahsun", "Sabzi", "kg"),
    ("Pyaz", "Sabzi", "kg"),
    ("Kohda", "Sabzi", "kg"),
    ("Boda", "Sabzi", "kg"),
    ("Chawal", "Grocery", "kg"),
    ("Atta", "Grocery", "kg"),
    ("Maida", "Grocery", "kg"),
    ("Moti Dal", "Dal", "kg"),
    ("Kabuli Chana", "Dal/Pulses", "kg"),
    ("Safed Matar", "Dal/Pulses", "kg"),
    ("Matar Dal", "Dal/Pulses", "kg"),
    ("Mungfali", "Grocery", "kg"),
    ("Jeera", "Masala", "kg"),
    ("Dhaniya Powder", "Masala", "kg"),
    ("Haldi Powder", "Masala", "kg"),
    ("Mircha Powder", "Masala", "kg"),
    ("Deggi Mirch", "Masala", "kg"),
    ("Sabji Masala", "Masala", "kg"),
    ("Meat Masala", "Masala", "kg"),
    ("Garam Masala", "Masala", "kg"),
    ("Chaat Masala", "Masala", "kg"),
    ("Aamchur", "Masala", "kg"),
    ("Laung", "Masala", "kg"),
    ("Pisa Sarso", "Masala", "kg"),
    ("Hara Namak", "Masala", "kg"),
    ("Namak", "Grocery", "kg"),
    ("Chini", "Grocery", "kg"),
    ("Chai", "Grocery", "kg"),
    ("Biscuit", "Grocery", "packet"),
    ("Namkeen", "Grocery", "packet"),
    ("Papad", "Grocery", "packet"),
    ("Pani Puri / Puri", "Grocery", "packet"),
    ("Ararot", "Grocery", "kg"),
    ("Baking Powder", "Grocery", "packet"),
    ("Kaju", "Dry Fruit", "kg"),
    ("Kishmish", "Dry Fruit", "kg"),
    ("Paneer", "Dairy", "kg"),
    ("Milk", "Dairy", "litre"),
    ("Butter", "Dairy", "kg"),
    ("Refined Oil", "Oil", "litre"),
    ("LPG Gas", "Kitchen", "kg"),
    ("Nirma Powder", "Cleaning", "kg"),
    ("Soap", "Cleaning", "piece"),
    ("Lighter", "Kitchen", "piece"),
    ("Chura", "Grocery", "kg"),
    ("Rang Gulal", "Other", "packet"),
    ("Peela Rang", "Other", "packet"),
]


CATEGORY_TO_UNIT = {
    "Sabzi": "kg",
    "Grocery": "kg",
    "Dal": "kg",
    "Dal/Pulses": "kg",
    "Masala": "kg",
    "Dry Fruit": "kg",
    "Dairy": "kg",
    "Oil": "litre",
    "Kitchen": "piece",
    "Cleaning": "kg",
    "Other": "packet",
    "Dairy": "litre",  # Milk, Butter
}


class Command(BaseCommand):
    help = "Import stock items from Excel file or use built-in 58 items list"

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Path to Excel file (.xlsx). If not provided, uses built-in 58 items list.',
        )
        parser.add_argument(
            '--sheet',
            type=str,
            default='Stock Items',
            help='Sheet name in Excel file (default: "Stock Items")',
        )
        parser.add_argument(
            '--skip-header',
            type=int,
            default=1,
            help='Number of header rows to skip (default: 1)',
        )

    def handle(self, *args, **options):
        file_path = options['file']
        sheet_name = options['sheet']
        skip_header = options['skip_header']

        if file_path:
            self.stdout.write(f"Importing from Excel file: {file_path}")
            items_data = self.import_from_excel(file_path, sheet_name, skip_header)
        else:
            self.stdout.write("No Excel file provided. Using built-in 58 items list.")
            items_data = STOCK_ITEMS_DATA

        if not items_data:
            self.stdout.write(self.style.ERROR("No items to import"))
            return

        created = 0
        updated = 0
        skipped = 0
        errors = []

        with transaction.atomic():
            for item_data in items_data:
                try:
                    name, category, unit = item_data
                    name = name.strip()
                    category = category.strip()
                    unit = unit.strip().lower() if unit else ''

                    # Determine unit from category if not provided
                    if not unit:
                        unit = CATEGORY_TO_UNIT.get(category, 'kg')

                    # Check if item already exists (case-insensitive name match)
                    existing = StockItem.objects.filter(name__iexact=name).first()

                    if existing:
                        # Update existing item
                        existing.category = category
                        existing.unit = unit
                        existing.save()
                        updated += 1
                        self.stdout.write(f"  Updated: {name} ({category}) - {unit}")
                    else:
                        StockItem.objects.create(
                            name=name,
                            category=category,
                            unit=unit,
                            min_level=0,
                        )
                        created += 1
                        self.stdout.write(f"  Created: {name} ({category}) - {unit}")

                except Exception as e:
                    error_msg = f"Error processing '{name}': {str(e)}"
                    errors.append(error_msg)
                    self.stdout.write(self.style.ERROR(f"  Error: {error_msg}"))

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(self.style.SUCCESS("IMPORT SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"Total items processed: {len(items_data)}")
        self.stdout.write(self.style.SUCCESS(f"New items created: {created}"))
        self.stdout.write(self.style.SUCCESS(f"Existing items updated: {updated}"))
        self.stdout.write(self.style.WARNING(f"Items skipped/errors: {len(errors)}"))

        if errors:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("ERRORS:"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))

    def import_from_excel(self, file_path, sheet_name, skip_header):
        """Import items from Excel file."""
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True)
        except FileNotFoundError:
            raise CommandError(f"File not found: {file_path}")
        except Exception as e:
            raise CommandError(f"Failed to open Excel file: {str(e)}")

        # Select sheet
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        else:
            self.stdout.write(self.style.WARNING(f"Sheet '{sheet_name}' not found. Using active sheet: {wb.active.title}"))
            ws = wb.active

        # Get headers
        headers = []
        header_row = None
        for row_idx in range(1, skip_header + 2):
            row_cells = list(ws[row_idx])
            if any(cell.value for cell in row_cells):
                header_row = row_idx
                for cell in row_cells:
                    headers.append(str(cell.value).strip() if cell.value else '')
                break

        if not header_row:
            raise CommandError("Could not find header row")

        # Map column names to indices
        expected = {
            'stock item name': 'name',
            'stock item name (hinglish)': 'name',
            'category': 'category',
        }
        col_map = {}
        for idx, header in enumerate(headers):
            header_lower = header.lower().strip()
            if header_lower in expected:
                col_map[expected[header_lower]] = idx

        if 'name' not in col_map:
            raise CommandError(f"Could not find 'Stock Item Name' column. Found headers: {headers}")

        # Process data rows
        items_data = []
        for row_idx, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1):
            # Skip blank rows
            if not any(cell for cell in row if cell is not None and str(cell).strip()):
                continue

            def get_cell(idx):
                if idx < len(row) and row[idx] is not None:
                    val = str(row[idx]).strip()
                    return val if val else ''
                return ''

            name = get_cell(col_map.get('name', -1))
            category = get_cell(col_map.get('category', -1))

            if not name:
                continue

            # Skip "Note" or similar rows
            if name.lower().startswith('note') or name.lower() == 'note':
                continue

            # Determine unit from category
            category_clean = category.strip()
            unit = CATEGORY_TO_UNIT.get(category_clean, 'kg')

            items_data.append((name, category_clean, unit))

        return items_data