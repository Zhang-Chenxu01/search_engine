from elasticsearch import Elasticsearch

from app.core.config import settings

_es_client: Elasticsearch | None = None


def get_es_client() -> Elasticsearch:
    global _es_client
    if _es_client is None:
        _es_client = Elasticsearch(
            settings.ELASTICSEARCH_URL,
            request_timeout=30,
            max_retries=3,
            retry_on_timeout=True,
        )
    return _es_client
