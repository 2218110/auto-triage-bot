# Auto-Triage Bot â€” Knowledge Search Investigation

**Status:** Initial retrieval implementation complete; further relevance evaluation required
**Database:** PostgreSQL 16
**Framework:** Django ORM
**Dataset:** 4,000 knowledge-base (KB) records
**Branch:** `feature/pg-trgm-similarity`

---

## 1. Objective

Build a knowledge-search service that can interpret natural-language IT incident descriptions and retrieve the most relevant KB records.

The intended workflow is:

1. A user describes an IT problem in their own words.
2. The search service retrieves up to five relevant KB records.
3. The bot presents the matching issue descriptions to the user.
4. The user confirms whether one of the suggested issues matches their problem.
5. If no suggestion matches, a clarification or alternative workflow can be implemented later.

The current scope is the **search service and retrieval quality**, not ticket creation, priority assignment, or the user interface.

The search service should support exact phrases, informal wording, paraphrases, and spelling mistakes while avoiding irrelevant results.

## 2. Initial investigation: trigram similarity

PostgreSQL's `pg_trgm` extension provides trigram similarity, which measures the similarity between strings based on their character trigrams.

The initial implementation searched KB titles using `TrigramSimilarity`.

The initial threshold was:

```python
SIMILARITY_THRESHOLD = 0.60
```

The initial implementation was simple, but title-only similarity did not provide enough retrieval quality for the natural-language queries being tested.

### Experiment 1: Title-only similarity

**Best observed similarity:** approximately `0.388`

**Result:** Insufficient for the tested natural-language queries.

The query often contained conversational wording that differed from the KB title. A strict title-only threshold could therefore exclude potentially useful KBs.

### Experiment 2: Description-only similarity

**Best observed similarity:** approximately `0.323`

**Result:** Insufficient.

Searching descriptions alone did not solve the problem. Longer descriptions contain additional words and contextual details that can reduce whole-string trigram similarity even when a KB is relevant.

### Experiment 3: Concatenated title and description

**Best observed similarity:** approximately `0.307`

**Result:** Rejected.

Combining the title and description into one string did not improve the observed score. The additional text did not provide a reliable improvement for the tested natural-language queries.

### Decision

We rejected the idea of relying on one whole-string trigram similarity score with a strict threshold of `0.60`.

The investigation showed that the initial threshold was unsuitable for the observed scores. It did not establish that trigram search itself was useless; it showed that the initial retrieval approach needed to change.

*Note: The three observed scores are experimental results from the investigation, not universal performance limits for PostgreSQL trigram similarity.*

---

## 3. Search architecture decision

We considered how to combine full-text search (FTS) and trigram similarity.

The selected design is:

**FTS first, trigram fallback second. No Reciprocal Rank Fusion (RRF).**

The reasons for this decision were:

- Full-text search is useful for finding records containing meaningful query terms.
- Trigram similarity can supplement retrieval when exact lexical matching is insufficient.
- FTS results should retain priority.
- The service should return no more than five records.
- Duplicate KBs must not occupy multiple result positions.
- We wanted a straightforward implementation that could be understood, tested, and improved incrementally.

### Current retrieval flow

```text
User query
    |
    v
Normalize whitespace
    |
    +---- Empty query? ---- Yes ----> Return []
    |
    v
Filter verified KB records
    |
    v
Full-text search (FTS)
    |
    v
Apply minimum FTS score: 0.0001
    |
    v
Order by score, then ID
    |
    +---- Five results? ---- Yes ----> Return FTS results
    |
    v
Trigram search over title and description
    |
    v
Keep maximum title/description similarity
    |
    v
Apply trigram threshold: 0.25
    |
    v
Append unique candidates after FTS results
    |
    v
Return at most five records
```

The fallback is triggered when FTS returns fewer than five records. It is **not currently triggered by measuring whether the FTS results are semantically good**.

This is an intentional simplification of the first implementation, and it remains a limitation.

---

## 4. Current search implementation

File:

`backend/incidents/services/knowledge_search.py`

### Configuration

```python
MAX_RESULTS = 5
CANDIDATE_LIMIT = 20
TRIGRAM_THRESHOLD = 0.25
```

The FTS minimum score is currently `0.0001`, applied directly in the FTS query.

### Stage 1: Full-text search

The service uses Django's PostgreSQL search expressions:

- `SearchQuery`
- `SearchVector`
- `SearchRank`

The query uses the English text-search configuration and `search_type="plain"`.

The search vector weights the title more heavily than the description:

- Title: weight `A`
- Description: weight `B`

The FTS query filters for:

```python
.filter(search_score__gt=0.0001)
```

Results are ordered by descending rank and then by record ID. The query retrieves at most five candidates.

If FTS returns five records, the service returns them immediately.

### Stage 2: Trigram fallback

If FTS returns fewer than five candidates, the service calculates:

```python
title_similarity = TrigramSimilarity("title", query)
description_similarity = TrigramSimilarity(
    "description",
    query,
)
```

It then selects the higher of the two scores:

```python
search_score=Greatest(
    title_similarity,
    description_similarity,
    output_field=FloatField(),
)
```

This allows the title and description to be evaluated independently rather than concatenated into one long string.

The fallback applies:

```python
.filter(search_score__gt=TRIGRAM_THRESHOLD)
```

with:

```python
TRIGRAM_THRESHOLD = 0.25
```

Up to 20 trigram candidates are fetched, ordered by descending similarity and then by ID.

The service appends unique trigram candidates after the FTS results until it reaches five results.

### Deduplication

The service uses record IDs to avoid duplicates:

```python
seen_ids = {record.pk for record in results}
```

FTS candidates retain their original positions. Trigram candidates are appended only when their IDs have not already been returned.

### Verified-only filtering

All retrieval stages start with:

```python
KnowledgeRecord.objects.filter(is_verified=True)
```

Unverified records must not be returned.

### Empty queries

The service strips surrounding whitespace and returns an empty list for blank input.

---

## 5. Investigation of zero-score false matches

A significant problem appeared during benchmark testing.

The nonsense query was:

```text
xyzqv blargh 92751
```

Despite containing no meaningful relationship to the KB dataset, the search initially returned five unrelated records.

The benchmark displayed scores such as:

```text
0.0000
```

The initial interpretation was that the query returned zero-score records.

A diagnostic inspection revealed the actual value:

```text
1e-20
```

This is equivalent to:

```text
0.00000000000000000001
```

It is extremely small, but it is still positive.

Consequently, this filter was too permissive:

```python
.filter(search_score__gt=0)
```

It accepted values such as `1e-20`, allowing irrelevant results into the response.

### Corrective change

The FTS filter was changed to:

```python
.filter(search_score__gt=0.0001)
```

The trigram fallback was separately configured to use its own threshold:

```python
.filter(search_score__gt=TRIGRAM_THRESHOLD)
```

where `TRIGRAM_THRESHOLD` is `0.25`.

The two thresholds serve different purposes and apply to different scoring systems. Their numerical values should not be interpreted as directly comparable relevance scores.

### Verification

After applying the FTS minimum score, the benchmark reported:

```text
No match: 'xyzqv blargh 92751'
Results: 0
No-match check: PASS
```

This corrected the observed false-match problem for the tested nonsense query.

---

## 6. Benchmark implementation

File:

`backend/incidents/management/commands/benchmark_search.py`

The benchmark invokes the actual production search service rather than maintaining a separate search implementation.

Current test queries:

| Test | Query | Purpose |
|---|---|---|
| Exact | `Windows Update fails to install` | Test direct lexical matching |
| Messy | `windows update keeps failing` | Test informal wording |
| Paraphrase | `my windows updates wont install` | Test alternative phrasing |
| Typo | `windows updates are faliing` | Test a spelling mistake |
| Printer | `my printer is not working` | Test a different incident category |
| No match | `xyzqv blargh 92751` | Test rejection of unrelated input |
| Empty | Empty string | Test blank-query handling |

The benchmark checks:

- Only verified records are returned.
- Results do not exceed five records.
- The nonsense query returns zero records.
- Empty input returns zero records.
- Returned titles and diagnostic scores are printed for manual inspection.
- Query latency is measured.

### Limitations of the benchmark

The benchmark currently measures each query once.

It does not yet provide:

- A labelled relevance dataset.
- Precision@5 or Recall@5.
- Median or percentile latency across repeated runs.
- A reliable measurement of semantic relevance.
- A general guarantee that all unrelated queries will return no results.

A benchmark can pass its basic checks while still returning less relevant KBs than desired. The result titles must continue to be reviewed.

---

## 7. Benchmark findings

The latest successful benchmark was run against:

```text
Database: auto_triage_test
KB records: 4000
```

### Observed results

| Query | Results | Observation |
|---|---:|---|
| Exact | 5 | Relevant Windows Update records |
| Messy | 5 | Relevant Windows Update records |
| Paraphrase | 5 | Relevant Windows Update records |
| Typo | 5 | Relevant Windows Update records |
| Printer | 5 | Printer-related records |
| No match | 0 | Expected behavior |
| Empty | 0 | Expected behavior |

The latest run completed all basic benchmark checks successfully.

### Relevance observation

The printer query returned titles such as:

- Windows cannot find the printer while working remotely
- Windows does not recognize the printer while working remotely
- Printer installation fails while working remotely
- Remote Desktop printer redirection fails while working remotely
- Network printer connection fails while working remotely

These results are printer-related, but the repeated remote-work context may not be relevant to every user reporting a printer issue.

This illustrates the distinction between returning records that share terms with the query and returning the best records for the user's actual problem.

### Latency observation

The latest successful run recorded approximately:

- Exact query: `363 ms`
- Messy query: `263 ms`
- Paraphrase: `209 ms`
- Typo query: `230 ms`
- Printer query: `172 ms`
- No-match query: `369 ms`

These are single-run measurements, not stable performance estimates. They should be treated as an initial baseline.

---

## 8. Database and schema changes

The `KnowledgeRecord` model was updated.

### Verification default

The field changed from:

```python
is_verified = models.BooleanField(default=False)
```

to:

```python
is_verified = models.BooleanField(default=True)
```

This matches the current project policy that KB modifications are restricted to admins and newly created KBs are considered verified under that workflow.

This default should only be retained while the ingestion and authorization policy ensures that untrusted KB records cannot be created through an unrestricted path.

### Description trigram index

The model now defines GIN trigram indexes for both title and description:

- `kb_title_trgm_idx`
- `kb_desc_trgm_idx`

The description index was added to support trigram queries against descriptions.

### Migrations

The project includes:

- `0006_knowledgerecord_description_trgm_idx`
- `0007_alter_knowledgerecord_is_verified`

Both migrations were applied to the test database during the investigation.

### Database state

The normal database, `auto_triage`, and the test database, `auto_triage_test`, were checked.

Both reported:

```text
Total: 4000
Verified: 4000
Unverified: 0
```

The test database's migration history initially showed migrations `0006` and `0007` as unapplied. These were subsequently identified as pending and scheduled for application to align the test schema with the current model.

---

## 9. Decisions made

| Decision | Reason |
|---|---|
| Reject title-only trigram search as the sole retrieval method | Insufficient observed similarity for tested natural-language queries |
| Reject description-only trigram search as the sole retrieval method | Insufficient observed similarity |
| Reject concatenated title/description trigram search | Did not improve the observed similarity |
| Use FTS first | Provides lexical retrieval with title weighting |
| Use trigram as fallback | Supplements FTS when fewer than five records are found |
| Do not use RRF | Explicitly excluded from the selected architecture |
| Return at most five records | Keeps the candidate list manageable for the future user-confirmation workflow |
| Filter unverified records | Prevents unapproved KBs from being retrieved |
| Use an FTS minimum score of `0.0001` | Rejects negligible scores observed during nonsense-query testing |
| Use a trigram threshold of `0.25` | Initial fallback threshold for further validation |
| Keep the benchmark simple | Makes current behavior easy to inspect and debug |

---

## 10. Known limitations

The current implementation is an initial retrieval baseline, not a completed semantic search solution.

1. **FTS count is used as the fallback trigger.** Five FTS results are returned even if they are weak or irrelevant. The service does not yet assess their semantic quality.

2. **Thresholds are preliminary.** The FTS minimum of `0.0001` and trigram threshold of `0.25` have not been calibrated against a comprehensive labelled dataset.

3. **Trigram similarity is not semantic understanding.** Similar wording and character patterns do not guarantee that two incidents describe the same problem.

4. **The benchmark is small.** Seven queries are useful for regression checks but insufficient to establish general retrieval quality.

5. **Relevance is currently reviewed manually.** There is no formal precision or recall measurement.

6. **Latency is not yet rigorously benchmarked.** Each query is timed once.

7. **Verification depends on access control.** Setting `is_verified=True` by default is safe only if the admin-only KB modification policy is enforced throughout the application.

---

## 11. Current checkpoint

The current implementation provides:

- Full-text search over title and description.
- Higher weighting for titles.
- A minimum FTS score of `0.0001`.
- Trigram fallback using the maximum of title and description similarity.
- A trigram threshold of `0.25`.
- FTS-first ordering.
- Deduplication by record ID.
- A maximum of five returned KB records.
- Verified-only retrieval.
- Empty-query handling.
- A benchmark management command.

The latest benchmark passed its basic checks, including zero results for the tested nonsense query.

**Current conclusion:** the search service is functional for the tested examples. The next meaningful improvement is to evaluate relevance across a broader set of realistic incident descriptions before changing the retrieval architecture or tuning thresholds further.
