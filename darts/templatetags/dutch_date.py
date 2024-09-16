from django import template
from django.utils import timezone
import datetime
import pytz

register = template.Library()

# Dictionary to translate month names to Dutch
MONTHS_DUTCH = {
    1: 'januari', 2: 'februari', 3: 'maart', 4: 'april',
    5: 'mei', 6: 'juni', 7: 'juli', 8: 'augustus',
    9: 'september', 10: 'oktober', 11: 'november', 12: 'december'
}

# Dictionary to translate weekday names to Dutch
WEEKDAYS_DUTCH = {
    0: 'maandag', 1: 'dinsdag', 2: 'woensdag', 3: 'donderdag',
    4: 'vrijdag', 5: 'zaterdag', 6: 'zondag'
}

@register.filter
def dutch_date(value):
    if not isinstance(value, datetime.date):
        return value

    day = value.day
    month = MONTHS_DUTCH[value.month]
    year = value.year
    weekday = WEEKDAYS_DUTCH[value.weekday()]

    return f"{weekday} {day} {month} {year}"

@register.filter
def dutch_datetime(value):
    if not isinstance(value, datetime.datetime):
        return value
    
    value = timezone.localtime(value, timezone=pytz.timezone('Europe/Brussels'))

    day = value.day
    month = MONTHS_DUTCH[value.month]
    year = value.year
    time = value.strftime('%H:%M')

    return f"{day} {month} {year}, {time}"

@register.filter
def dutch_time(value):
    if not isinstance(value, datetime.datetime):
        return value

    value = timezone.localtime(value, timezone=pytz.timezone('Europe/Brussels'))

    return value.strftime('%H:%M')