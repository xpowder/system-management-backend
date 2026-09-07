"""List pagination that keeps JSON array bodies and exposes page metadata in headers."""

MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 500


def parse_list_page(limit, offset):
    if offset is None or int(offset) < 0:
        offset = 0
    else:
        offset = int(offset)
    if limit is None:
        limit = DEFAULT_PAGE_SIZE
    else:
        limit = int(limit)
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
