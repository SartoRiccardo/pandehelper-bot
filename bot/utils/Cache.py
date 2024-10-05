from datetime import datetime, timedelta
from typing import Any


class Cache:
    def __init__(self, value: Any, expire: datetime | timedelta):
        self._value = value
        if isinstance(expire, datetime):
            self._expire = expire
        else:
            self._expire = datetime.now() + expire

    @property
    def value(self) -> Any:
        return self._value

    @property
    def valid(self) -> bool:
        return self._expire >= datetime.now()

    @staticmethod
    def empty() -> "Cache":
        return Cache(None, datetime.fromtimestamp(0))
