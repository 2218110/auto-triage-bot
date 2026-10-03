import time

from django.test import TestCase
from django.contrib.postgres.search import TrigramSimilarity

from .models import KnowledgeRecord
from .services import knowledge_search


class KnowledgeSearchTests(TestCase):

    def test_search_performance(self):
        query = "Windows update has been stuck since this morning..."

        start = time.perf_counter()

        results = knowledge_search.search_knowledge(query)
        results = list(results)

        elapsed = time.perf_counter() - start

        print(f"\nSearch time: {elapsed:.6f}s")
        print(f"Results found: {len(results)}")

        if results:
            print("Top result:")
            print(f"Title: {results[0].title}")
            print(f"Similarity: {results[0].similarity:.4f}")

    def test_trigram_similarity_without_verified_filter(self):
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