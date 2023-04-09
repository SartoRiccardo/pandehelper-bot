from typing import Dict, List, Any
import json


def get_race_rounds() -> List[Dict[str, Any]]:
    fin = open("ct_ticket_tracker/files/json/rounds-race.json")
    data = json.loads(fin.read())
    fin.close()
    return data
