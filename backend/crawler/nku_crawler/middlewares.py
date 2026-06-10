"""Custom middlewares for NKU crawler."""

from typing import Generator, Optional

from scrapy import Request, Spider
from scrapy.http import Response


class NkuCrawlerMiddleware:
    """Optional middleware for request/response processing.

    Currently a placeholder; can be extended for:
    - Custom retry logic
    - Response preprocessing
    - Request fingerprinting
    """

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Response:
        return response
