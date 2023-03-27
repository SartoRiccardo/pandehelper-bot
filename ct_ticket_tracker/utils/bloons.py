import datetime


FIRST_CT_START = datetime.datetime.strptime('2022-08-09 22', '%Y-%m-%d %H')
EVENT_DURATION = 7


def get_ct_number_during(time: datetime.datetime) -> int:
    return int((time-FIRST_CT_START).days / (EVENT_DURATION*2)) + 1
