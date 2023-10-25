from dataclasses import dataclass, field


@dataclass
class Tilestrat:
    forum_id: int = field(repr=False)
    thread_id: int = field(repr=False)
    tile_code: str
    event_num: int
    challenge_type: int
    boss: int or None
