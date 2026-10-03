from django.contrib.postgres.search import TrigramSimilarity
from ..models import KnowledgeRecord

SIMILARITY_THRESHOLD = 0.60

def search_knowledge(query):

    search_results = KnowledgeRecord.objects.annotate(similarity = TrigramSimilarity("title",query)).filter(similarity__gte = SIMILARITY_THRESHOLD,is_verified = True).order_by('-similarity')
    return search_results