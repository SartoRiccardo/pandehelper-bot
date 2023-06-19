from datetime import datetime
from typing import Any


class Cache:
    def __init__(self, value: Any, expire: datetime):
        self._value = value
        self._expire = expire

    @property
    def value(self) -> Any:
        return self._value

    @property
    def valid(self) -> bool:
        return self._expire >= datetime.now()
