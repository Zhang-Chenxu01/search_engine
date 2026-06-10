"""Elasticsearch index management for NKU search engine.

Usage:
    python -m indexer.create_indices          # create both indices
    python -m indexer.create_indices --force  # delete and recreate if exist
"""

import argparse
import logging
import sys

from elasticsearch import Elasticsearch

from app.search.es_client import get_es_client

logger = logging.getLogger(__name__)

PAGES_INDEX = "nku_pages_v1"
DOCUMENTS_INDEX = "nku_documents_v1"

IK_MAX_WORD = "ik_max_word"
IK_SMART = "ik_smart"

PAGES_MAPPING: dict = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "ik_max_word_analyzer": {
                    "type": "custom",
                    "tokenizer": IK_MAX_WORD,
                },
                "ik_smart_analyzer": {
                    "type": "custom",
                    "tokenizer": IK_SMART,
                },
            }
        },
    },
    "mappings": {
        "properties": {
            "page_id":       {"type": "long"},
            "url":           {"type": "keyword"},
            "title":         {"type": "text", "analyzer": "ik_max_word_analyzer", "search_analyzer": "ik_smart_analyzer"},
            "content":       {"type": "text", "analyzer": "ik_max_word_analyzer", "search_analyzer": "ik_smart_analyzer"},
            "source_site":   {"type": "keyword"},
            "category":      {"type": "keyword"},
            "publish_time":  {"type": "date", "format": "yyyy-MM-dd HH:mm:ss"},
            "crawl_time":    {"type": "date", "format": "yyyy-MM-dd HH:mm:ss"},
            "anchor_text":   {"type": "text", "analyzer": "ik_max_word_analyzer", "search_analyzer": "ik_smart_analyzer"},
            "snapshot_path": {"type": "keyword"},
            "pagerank":      {"type": "float"},
        }
    },
}

DOCUMENTS_MAPPING: dict = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "ik_max_word_analyzer": {
                    "type": "custom",
                    "tokenizer": IK_MAX_WORD,
                },
                "ik_smart_analyzer": {
                    "type": "custom",
                    "tokenizer": IK_SMART,
                },
            }
        },
    },
    "mappings": {
        "properties": {
            "attachment_id":  {"type": "long"},
            "file_url":      {"type": "keyword"},
            "file_name":     {"type": "text", "analyzer": "ik_max_word_analyzer", "search_analyzer": "ik_smart_analyzer"},
            "file_type":     {"type": "keyword"},
            "file_text":     {"type": "text", "analyzer": "ik_max_word_analyzer", "search_analyzer": "ik_smart_analyzer"},
            "parent_page_id": {"type": "long"},
            "parent_title":  {"type": "text", "analyzer": "ik_max_word_analyzer", "search_analyzer": "ik_smart_analyzer"},
            "parent_url":    {"type": "keyword"},
            "crawl_time":    {"type": "date", "format": "yyyy-MM-dd HH:mm:ss"},
        }
    },
}


def index_exists(es: Elasticsearch, name: str) -> bool:
    return bool(es.indices.exists(index=name))


def create_index(
    es: Elasticsearch,
    name: str,
    mapping: dict,
    force: bool = False,
) -> bool:
    if index_exists(es, name):
        if not force:
            logger.warning("Index '%s' already exists. Use --force to recreate.", name)
            return False
        logger.info("Deleting existing index '%s'...", name)
        es.indices.delete(index=name)

    es.indices.create(index=name, body=mapping)
    logger.info("Index '%s' created successfully.", name)
    return True


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Create Elasticsearch indices for NKU search engine.")
    parser.add_argument("--force", action="store_true", help="Delete and recreate indices if they already exist.")
    args = parser.parse_args()

    es = get_es_client()

    try:
        if not es.ping():
            logger.error("Cannot connect to Elasticsearch. Check ELASTICSEARCH_URL.")
            sys.exit(1)
        logger.info("Connected to Elasticsearch.")
    except Exception as exc:
        logger.error("Elasticsearch connection failed: %s", exc)
        sys.exit(1)

    created = 0
    for idx_name, mapping in [
        (PAGES_INDEX, PAGES_MAPPING),
        (DOCUMENTS_INDEX, DOCUMENTS_MAPPING),
    ]:
        if create_index(es, idx_name, mapping, force=args.force):
            created += 1

    logger.info("Done. %d index(es) created.", created)


if __name__ == "__main__":
    main()
