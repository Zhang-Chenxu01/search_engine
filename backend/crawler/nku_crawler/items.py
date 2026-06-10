"""Scrapy Item definitions for NKU crawler."""

import scrapy


class PageItem(scrapy.Item):
    url = scrapy.Field()
    normalized_url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    raw_html = scrapy.Field()
    source_site = scrapy.Field()
    category = scrapy.Field()
    publish_time = scrapy.Field()
    anchor_texts = scrapy.Field()
    out_links = scrapy.Field()
    attachment_links = scrapy.Field()
    crawl_time = scrapy.Field()
    content_hash = scrapy.Field()
    snapshot_path = scrapy.Field()
    status_code = scrapy.Field()
