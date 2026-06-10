"""Item pipelines for NKU crawler.

Output is JSONL by default; MySQL pipeline can be added later.
"""

import hashlib
import json
import os
from datetime import datetime

from scrapy import Spider
from scrapy.utils.project import get_project_settings


class JsonlWriterPipeline:
    """Write items to a JSONL file, one JSON object per line."""

    def open_spider(self, spider: Spider) -> None:
        settings = get_project_settings()
        output_dir = settings.get("OUTPUT_DIR", "data/jsonl")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{spider.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        self.filepath = os.path.join(output_dir, filename)
        self.file = open(self.filepath, "w", encoding="utf-8")
        spider.logger.info("JSONL output: %s", self.filepath)

    def close_spider(self, spider: Spider) -> None:
        self.file.close()
        spider.logger.info("JSONL file closed: %s", self.filepath)

    def process_item(self, item: dict, spider: Spider) -> dict:
        # Convert non-serializable types
        for key in ("crawl_time", "publish_time"):
            val = item.get(key)
            if isinstance(val, datetime):
                item[key] = val.isoformat()
        line = json.dumps(dict(item), ensure_ascii=False) + "\n"
        self.file.write(line)
        return item


class SnapshotPipeline:
    """Save raw HTML to disk as snapshot files."""

    def open_spider(self, spider: Spider) -> None:
        settings = get_project_settings()
        self.snapshot_dir = settings.get("SNAPSHOT_DIR", "data/snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def process_item(self, item: dict, spider: Spider) -> dict:
        raw_html: str | None = item.get("raw_html")
        if not raw_html:
            return item

        url: str = item.get("url", "")
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        filename = f"{url_hash}.html"
        filepath = os.path.join(self.snapshot_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(raw_html)

        item["snapshot_path"] = filepath
        spider.logger.debug("Snapshot saved: %s", filepath)
        return item
