import re


def add_spaces(text: str) -> str:
    """Adds spaces to a text in PascalCase"""
    def repl(matchobj):
        return " " + matchobj.group(0)
    return re.sub("[A-Z]", repl, text).strip()
