
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity,
)
from django.db.models import FloatField
from django.db.models.functions import Greatest

from incidents.models import KnowledgeRecord


MAX_RESULTS = 5
CANDIDATE_LIMIT = 20
TRIGRAM_THRESHOLD = 0.25


def search_knowledge(query):
    """
    Search verified KB records using full-text search first.

    If FTS returns fewer than five results, supplement them
    with unique trigram matches above the similarity threshold.

    FTS results always retain priority.
    """

    query = (query or "").strip()

    if not query:
        return []

    verified_records = KnowledgeRecord.objects.filter(
        is_verified=True
    )

    # Stage 1: Full-text search.
    search_query = SearchQuery(
        query,
        config="english",
        search_type="plain",
    )

    search_vector = (
        SearchVector(
            "title",
            config="english",
            weight="A",
        )
        + SearchVector(
            "description",
            config="english",
            weight="B",
        )
    )

    fts_candidates = list(
        verified_records.annotate(
            search_score=SearchRank(
                search_vector,
                search_query,
            )
        )
        .filter(search_score__gt=0.0001)
        .order_by("-search_score", "id")[:MAX_RESULTS]
    )

    # FTS already filled all five result slots.
    if len(fts_candidates) >= MAX_RESULTS:
        return fts_candidates

    # Stage 2: Trigram search supplements FTS.
    title_similarity = TrigramSimilarity(
        "title",
        query,
    )

    description_similarity = TrigramSimilarity(
        "description",
        query,
    )

    trigram_candidates = list(
        verified_records.annotate(
            title_similarity=title_similarity,
            description_similarity=description_similarity,
        )
        .annotate(
            search_score=Greatest(
                title_similarity,
                description_similarity,
                output_field=FloatField(),
            )
        )
        .filter(
            search_score__gt=TRIGRAM_THRESHOLD
        )
        .order_by("-search_score", "id")[:CANDIDATE_LIMIT]
    )

    # Preserve FTS ordering and avoid duplicate KB records.
    results = list(fts_candidates)
    seen_ids = {record.pk for record in results}

    for record in trigram_candidates:
        if record.pk in seen_ids:
            continue

        results.append(record)
        seen_ids.add(record.pk)

        if len(results) >= MAX_RESULTS:
            break

    return results
