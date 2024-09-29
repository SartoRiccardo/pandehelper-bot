import re


def add_spaces(text: str) -> str:
    """Adds spaces to a text in PascalCase"""
    def repl(matchobj):
        return " " + matchobj.group(0)
    return re.sub("[A-Z]", repl, text).strip()


def get_page_idxs(
        page: int,
        items_page: int,
        items_page_srv: int
) -> tuple[int, int, int, int]:
    start_idx = (page-1) * items_page
    end_idx = page * items_page - 1
    req_page_start = start_idx // items_page_srv + 1
    req_page_end = end_idx // items_page_srv + 1
    return start_idx, end_idx, req_page_start, req_page_end
