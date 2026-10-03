from django.contrib.postgres.search import TrigramSimilarity
from django.test import TestCase

from .models import KnowledgeRecord
from .services import knowledge_search


class KnowledgeSearchTests(TestCase):

    def test_finds_verified_knowledge_record(self):
        KnowledgeRecord.objects.create(
            title="Windows Update fails to install",
            description="Troubleshooting Windows Update installation failures.",
            category="Windows & OS",
            is_verified=True,
        )

        results = list(
            knowledge_search.search_knowledge(
                "Windows Update fails to install"
            )
        )

        self.assertTrue(results)
        self.assertEqual(
            results[0].title,
            "Windows Update fails to install",
        )
        self.assertGreaterEqual(
            results[0].similarity,
            0.60,
        )

    def test_rejects_low_similarity_knowledge_record(self):
        KnowledgeRecord.objects.create(
            title="Windows Update fails to install",
            description="Troubleshooting Windows Update installation failures.",
            category="Windows & OS",
            is_verified=True,
        )

        results = knowledge_search.search_knowledge(
            "printer toner replacement"
        )

        self.assertFalse(results)

    def test_trigram_similarity_without_verified_filter(self):
        KnowledgeRecord.objects.create(
            title="Windows Update fails to install",
            description="Windows Update installation troubleshooting.",
            category="Windows & OS",
            is_verified=True,
        )

        query = "Windows Update fails to install"

        results = (
            KnowledgeRecord.objects
            .annotate(
                similarity=TrigramSimilarity("title", query)
            )
            .order_by("-similarity")
        )

        results = list(results[:5])

        print("\n" + "=" * 60)
        print("TRIGRAM DIAGNOSTIC")
        print("=" * 60)

        for result in results:
            print(
                f"Title: {result.title}\n"
                f"Similarity: {result.similarity:.4f}\n"
                f"Verified: {result.is_verified}\n"
            )

        self.assertTrue(results)