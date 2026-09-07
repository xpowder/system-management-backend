"""List pagination that keeps JSON array bodies and exposes page metadata in headers."""

MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 500


def _as_int(value, default):
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_list_page(limit, offset):
    offset = _as_int(offset, 0)
    if offset < 0:
        offset = 0
    limit = _as_int(limit, DEFAULT_PAGE_SIZE)
    if limit < 1:
        limit = 1
    if limit > MAX_PAGE_SIZE:
        limit = MAX_PAGE_SIZE
    return limit, offset


def apply_pagination_headers(response, *, total, limit, offset, returned):
    response['X-Total-Count'] = str(total)
    response['X-Limit'] = str(limit)
    response['X-Offset'] = str(offset)
    response['X-Has-More'] = 'true' if (offset + returned) < total else 'false'
    return response
