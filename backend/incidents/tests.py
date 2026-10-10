
from django.db import connection
from django.test import TestCase

from .models import KnowledgeRecord
from .services import knowledge_search


class SystemHealthTests(TestCase):

    def test_database_connection_and_query(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_required_knowledge_table_exists(self):
        tables = connection.introspection.table_names()

        self.assertIn(
            KnowledgeRecord._meta.db_table,
            tables,
        )

    def test_pg_trgm_extension_is_installed(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_extension
                    WHERE extname = 'pg_trgm'
                )
                """
            )
            self.assertTrue(cursor.fetchone()[0])

    def test_trigram_gin_index_exists(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_indexes
                    WHERE tablename = %s
                      AND indexname = 'kb_title_trgm_idx'
                )
                """,
                [KnowledgeRecord._meta.db_table],
            )
            self.assertTrue(cursor.fetchone()[0])


class KnowledgeRecordHealthTests(TestCase):

    def test_knowledge_record_can_be_created_and_read(self):
        record = KnowledgeRecord.objects.create(
            title="Health check record",
            description="Verifies database write and read operations.",
            category="System",
            is_verified=True,
        )

        retrieved = KnowledgeRecord.objects.get(pk=record.pk)

        self.assertEqual(retrieved.title, "Health check record")
        self.assertTrue(retrieved.is_verified)

    def test_search_excludes_unverified_records(self):
        KnowledgeRecord.objects.create(
            title="Verified health check record",
            description="A verified record for the health check.",
            category="System",
            is_verified=True,
        )

        unverified = KnowledgeRecord.objects.create(
            title="Unverified health check record",
            description="An unverified record for the health check.",
            category="System",
            is_verified=False,
        )

        results = list(
            knowledge_search.search_knowledge(
                "Unverified health check record"
            )
        )

        self.assertNotIn(
            unverified.pk,
            [record.pk for record in results],
        )
