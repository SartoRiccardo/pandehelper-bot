import datetime


FIRST_CT_START = datetime.datetime.strptime('2022-08-09 22', '%Y-%m-%d %H')
EVENT_DURATION = 7


def get_ct_number_during(time: datetime.datetime) -> int:
    event = 1
    event_start = FIRST_CT_START
    while event_start + datetime.timedelta(days=EVENT_DURATION*2) < time:
        event_start += datetime.timedelta(days=EVENT_DURATION*2)
        event += 1
    return event
