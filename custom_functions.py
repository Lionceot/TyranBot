from json import load as json_load, dump as json_dump
from pytz import timezone
from datetime import datetime

from custom_errors import InvalidTimeString


def get_codes_data():
    with open("json/codes.json", "r", encoding="utf-8") as code_file:
        codes = json_load(code_file)
    return codes


def time_now(tz: str = "Europe/Paris"):
    """
        Return current time
    """
    return datetime.now(tz=timezone(tz))


def get_parameter(param):
    """
        Get config parameters
    """
    with open("json/config.json", "r", encoding="utf-8") as config_file:
        config = json_load(config_file)

    if isinstance(param, str):
        try:
            return config[param]
        except KeyError:
            return "KeyError"

    else:
        items = []
        for item in param:
            if item in config:
                items.append(config[item])
            else:
                items.append(None)
        return items


def var_set(param, value):
    """
        Allow to edit config parameters
    """
    with open("json/config.json", "r", encoding="utf-8") as config_file:
        config = json_load(config_file)

    if isinstance(param, str):
        config[param] = value

    elif isinstance(param, list):
        for i in range(len(param)):
            config[param[i]] = value[i]

    else:
        raise Exception("Invalid param type")

    with open("json/config.json", "w", encoding="utf-8") as config_file:
        json_dump(config, config_file, indent=2)


def add_event(timestamp: int, data: dict):
    with open("json/events.json", "r", encoding="utf-8") as event_file:
        events = json_load(event_file)

    if timestamp in events:
        events[timestamp].append(data)
    else:
        events[timestamp] = [data]

    with open("json/config.json", "w", encoding="utf-8") as event_file:
        json_dump(events, event_file, indent=2)


def get_text(reference: str, lang: str):
    """
        Used to get the corresponding text in language asked
    """
    # make it open the corresponding file and return the associated text (return reference if error)
    #   if lang == "", open english file
    return reference


def key_with_lowest_value(dico: dict):
    min_value = None
    min_key = None
    for item in dico.items():
        try:
            if item[1] < min_value:
                min_value = item[1]
                min_key = item[0]

        except TypeError:
            min_value = item[1]
            min_key = item[0]
    return min_key


def sort_dict_by_value(d, reverse=False):
    return dict(sorted(d.items(), key=lambda x: x[1], reverse=reverse))


def string_to_time(raw_time: str):
    time_dict = {
        "s": 1,  # second
        "m": 60,  # minute
        "h": 3600,  # hour
        "d": 3600 * 24,  # day
        "w": 3600 * 24 * 7,  # week
        "y": 3600 * 24 * 7 * 28 * 12,  # year
    }
    times = raw_time.split(' ')
    total = 0

    for time in times:
        if time == '':
            continue
        indicator = time[-1]

        if indicator not in time_dict:
            raise InvalidTimeString(reason="Invalid indicator", raw_input=raw_time)

        try:
            number = eval(time[:-1])

        except SyntaxError:
            raise InvalidTimeString(reason="Invalid time", raw_input=raw_time)

        if number < 0:
            raise InvalidTimeString(reason="Negative time isn't allowed", raw_input=raw_time)

        total += number * time_dict[indicator]

    return total


def time_to_string(raw_time: int):
    result = ""

    if raw_time >= 3600 * 24 * 365:
        year_amt = raw_time // (3600 * 24 * 365)
        raw_time -= year_amt * (3600 * 24 * 365)
        result += f"{year_amt}y "

    if raw_time >= 3600 * 24 * 7:
        week_amt = raw_time // (3600 * 24 * 7)
        raw_time -= week_amt * (3600 * 24 * 7)
        result += f"{week_amt}w "

    if raw_time >= 3600 * 24:
        day_amt = raw_time // (3600 * 24)
        raw_time -= day_amt * (3600 * 24)
        result += f"{day_amt}d "

    if raw_time >= 3600:
        hour_amt = raw_time // 3600
        raw_time -= hour_amt * 3600
        result += f"{hour_amt}h "

    if raw_time > 60:
        minute_amt = raw_time // 60
        raw_time -= minute_amt * 60
        result += f"{minute_amt}m "

    if raw_time > 1:
        second_amt = raw_time
        raw_time -= second_amt
        result += f"{second_amt}s "

    return result[:-1]
