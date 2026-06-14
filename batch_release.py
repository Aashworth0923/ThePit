"""
Thursday-aligned week splitting for the Batch Release feature.
"""

import calendar
from datetime import date, timedelta

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def get_month_weeks(year, month):
    """Return a list of 4 (start_date, end_date) date objects covering the
    given month, split on Thursday boundaries:

      Week 1: 1st of the month through the first Thursday (inclusive)
      Week 2: the Friday after Week 1 through the following Thursday
      Week 3: the Friday after Week 2 through the following Thursday
      Week 4: the Friday after Week 3 through the end of the month
    """
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])

    days_to_thu = (3 - first.weekday()) % 7  # Monday=0 ... Thursday=3
    first_thu = first + timedelta(days=days_to_thu)

    week1 = (first, first_thu)
    w2_start = first_thu + timedelta(days=1)
    w2_end = w2_start + timedelta(days=6)
    w3_start = w2_end + timedelta(days=1)
    w3_end = w3_start + timedelta(days=6)
    w4_start = w3_end + timedelta(days=1)
    week4 = (w4_start, last)

    return [week1, (w2_start, w2_end), (w3_start, w3_end), week4]
