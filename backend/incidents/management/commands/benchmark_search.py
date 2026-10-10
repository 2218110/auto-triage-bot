
import time

from django.core.management.base import BaseCommand
from django.db import connection

from incidents.models import KnowledgeRecord
from incidents.services.knowledge_search import search_knowledge


QUERIES = {
    "Exact": "Windows Update fails to install",
    "Messy": "windows update keeps failing",
    "Paraphrase": "my windows updates wont install",
    "Typo": "windows updates are faliing",
    "Printer": "my printer is not working",
    "No match": "xyzqv blargh 92751",
    "Empty": "",
}

MAX_RESULTS = 5


class Command(BaseCommand):
    help = "Benchmark the knowledge search service"

    def handle(self, *args, **options):
        self.stdout.write(
            f"Database: {connection.settings_dict['NAME']}"
        )
        self.stdout.write(
            f"KB records: {KnowledgeRecord.objects.count()}"
        )
        self.stdout.write("")

        failures = []

        for label, query in QUERIES.items():
            start_time = time.perf_counter()

            results = list(search_knowledge(query))

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            self.stdout.write(f"{label}: {query!r}")
            self.stdout.write(
                f"Time: {elapsed_ms:.2f} ms | "
                f"Results: {len(results)}"
            )

            # Empty queries should return no results.
            if not query.strip():
                if results:
                    failures.append("Empty query returned results")
                    self.stdout.write("Empty query: FAIL")
                else:
                    self.stdout.write("Empty query: PASS")

                self.stdout.write("")
                continue

            # Only verified KBs should be returned.
            if all(record.is_verified for record in results):
                self.stdout.write("Verified KBs: PASS")
            else:
                failures.append(
                    f"{label}: unverified KB returned"
                )
                self.stdout.write("Verified KBs: FAIL")

            # Results should not exceed the configured limit.
            if len(results) <= MAX_RESULTS:
                self.stdout.write("Result limit: PASS")
            else:
                failures.append(
                    f"{label}: more than {MAX_RESULTS} results"
                )
                self.stdout.write("Result limit: FAIL")

            # This nonsense query should return no results.
            if label == "No match":
                if results:
                    failures.append(
                        "No match query returned results"
                    )
                    self.stdout.write("No-match check: FAIL")
                else:
                    self.stdout.write("No-match check: PASS")

            # Inspect titles and scores to judge relevance manually.
            for index, record in enumerate(results, start=1):
                score = getattr(record, "search_score", None)

                if score is None:
                    score_text = "N/A"
                else:
                    score_text = f"{float(score):.4f}"

                self.stdout.write(
                    f"{index}. {record.title} "
                    f"| score={score_text}"
                )

            self.stdout.write("")

        if failures:
            self.stderr.write(self.style.ERROR("BENCHMARK FAILED"))

            for failure in failures:
                self.stderr.write(f"- {failure}")

            raise SystemExit(1)

        self.stdout.write(
            self.style.SUCCESS("PASS: all basic checks")
        )
