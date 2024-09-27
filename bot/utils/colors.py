
class Color:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def red(text: str) -> str: return f"{Color.FAIL}{text}{Color.ENDC}"
def blue(text: str) -> str: return f"{Color.OKBLUE}{text}{Color.ENDC}"
def cyan(text: str) -> str: return f"{Color.OKCYAN}{text}{Color.ENDC}"
def green(text: str) -> str: return f"{Color.OKGREEN}{text}{Color.ENDC}"
def yellow(text: str) -> str: return f"{Color.WARNING}{text}{Color.ENDC}"
def purple(text: str) -> str: return f"{Color.HEADER}{text}{Color.ENDC}"
def bold(text: str) -> str: return f"{Color.BOLD}{text}{Color.ENDC}"
def underline(text: str) -> str: return f"{Color.UNDERLINE}{text}{Color.ENDC}"
