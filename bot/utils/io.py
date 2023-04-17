from typing import Dict, List, Any
import json


def get_race_rounds() -> List[Dict[str, Any]]:
    fin = open("ct_ticket_tracker/files/json/rounds-race.json")
    data = json.loads(fin.read())
    fin.close()
    return data


def get_tag_list() -> List[str]:
    fin = open("ct_ticket_tracker/files/json/tags.json")
    data = json.loads(fin.read())
    fin.close()
    return data.keys()


def get_tag(tag_name: str) -> str or None:
    fin = open("ct_ticket_tracker/files/json/tags.json")
    data = json.loads(fin.read())
    if tag_name not in data.keys():
        return None
    fin.close()
    return data[tag_name]
