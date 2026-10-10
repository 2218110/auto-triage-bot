import os
import csv

from django.conf import settings
from django.core.management.base import BaseCommand

from incidents.models import KnowledgeRecord


class Command(BaseCommand):

    def handle(self, *args, **options):

        csv_path = os.path.join(
            settings.BASE_DIR,
            "data",
            "it_kb_4000_real_issues.csv"
        )

        self.stdout.write(
            self.style.SUCCESS("Starting KB import...")
        )

        self.stdout.write(
            self.style.SUCCESS(f"CSV found: {csv_path}")
        )

        # Get titles that already exist in the database
        existing_titles = set(
            KnowledgeRecord.objects.values_list(
                "title",
                flat=True
            )
        )

        records = []

        with open(
            csv_path,
            newline="",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                # Skip records that already exist
                if row["title"] in existing_titles:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping duplicate: {row['title']}"
                        )
                    )
                    continue

                record = KnowledgeRecord(
                    title=row["title"],
                    description=row["description"],
                    category=row["category"],
                    is_verified=row["is_verified"].strip().lower() == 'true' # this will help to enter the Boolean Value in DB
                )

                records.append(record)

                # Prevent duplicates inside the CSV itself
                existing_titles.add(row["title"])

        total_records = len(records)

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {total_records} new KB records."
            )
        )

        batch_size = 500

        for start in range(0, total_records, batch_size):

            batch = records[start:start + batch_size]

            KnowledgeRecord.objects.bulk_create(batch)

            imported = min(
                start + batch_size,
                total_records
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {imported} / {total_records} records"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"KB import completed successfully! "
                f"Total new records imported: {total_records}"
            )
        )