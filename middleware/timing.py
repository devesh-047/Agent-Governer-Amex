"""Latency tracking middleware.

Measures processing time for API requests, especially useful for
verifying the <100ms latency requirement for action-requests.
"""

import time
import logging
from typing import Callable

from fastapi import Request, Response

logger = logging.getLogger(__name__)

async def add_process_time_header(request: Request, call_next: Callable) -> Response:
    """Middleware to add X-Process-Time header and log request latency."""
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    
    # Format to milliseconds (e.g. 15.23ms)
    process_time_ms = process_time * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
    
    # Log requests that take longer than 100ms
    if process_time_ms > 100:
        logger.warning(f"Slow request: {request.method} {request.url.path} took {process_time_ms:.2f}ms")
    else:
        logger.info(f"Request: {request.method} {request.url.path} took {process_time_ms:.2f}ms")
        
    return response
