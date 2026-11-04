# Copyright 2026 MSPbots.ai
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for tool handlers: client construction and list pagination.

The vendor's own pagination contract could not be confirmed without a
partner API key (design doc "Open questions"), so `paginate` applies a
cursor/limit contract (AC6) on top of whatever the vendor's GET returns in
one shot. If the real vendor paging shape differs once a test account is
available, only this function's internals change — the tool-facing contract
(limit/cursor/has_more) does not.
"""

from ..client import AxcientClient
from ..errors import error_envelope
from ..middleware import current_api_key

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

# Defensive fallback: the credential middleware already returns 401 before any
# tool runs when X-Axcient-Api-Key is missing (AC2), so client_or_none()
# should never actually return None in production. Kept per SOP's
# not_configured code, which exists for exactly this "should be unreachable"
# case.
NO_TOKEN = error_envelope(
    "not_configured",
    "No Axcient API key in request context. Send the X-Axcient-Api-Key header.",
    False,
)


def client_or_none() -> AxcientClient | None:
    api_key = current_api_key()
    if not api_key:
        return None
    return AxcientClient(api_key)


def paginate(items: list, limit: int | None, cursor: str | None) -> tuple[list, bool, str | None]:
    """Slice `items` into one page per the limit/cursor contract (AC6).

    Returns (page, has_more, next_cursor). `next_cursor` is None when there is
    no further page.
    """
    size = min(max(int(limit), 1), MAX_LIMIT) if limit else DEFAULT_LIMIT
    offset = 0
    if cursor:
        try:
            offset = max(int(cursor), 0)
        except ValueError:
            offset = 0
    page = items[offset : offset + size]
    has_more = offset + size < len(items)
    next_cursor = str(offset + size) if has_more else None
    return page, has_more, next_cursor
