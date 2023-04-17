import datetime


FIRST_CT_START = datetime.datetime.strptime('2022-08-09 22', '%Y-%m-%d %H')
EVENT_DURATION = 7


def get_ct_number_during(time: datetime.datetime, breakpoint_on_event_start: bool = True) -> int:
    """Gets the CT number during a certain datetime.

    :param time: the time to get the number for.
    :param breakpoint_on_event_start: If `True`, a new CT "starts" only when the next event starts.
    Otherwise, it starts as soon as the current event ends. In other words, if `True`, the break period
    will count as part of the last CT, if `False` it will count as the next.
    :return:
    """
    start = FIRST_CT_START
    if not breakpoint_on_event_start:
        start -= datetime.timedelta(days=EVENT_DURATION)
    return int((time-start).days / (EVENT_DURATION*2)) + 1


def get_current_ct_number(breakpoint_on_event_start: bool = True) -> int:
    return get_ct_number_during(datetime.datetime.now(), breakpoint_on_event_start)
