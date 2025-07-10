# =============================================================
# File: engine/holidays.py – Fixed dt.date bug
# =============================================================
import pandas as pd

def load_holiday_calendar(uploaded_file_object=None, adhoc=None):
    holidays = set()

    if uploaded_file_object is not None:
        holiday_df = pd.read_csv(uploaded_file_object)
        dates = pd.to_datetime(holiday_df.iloc[:, 0], format='%d-%b-%Y', errors='coerce').dropna()
        holidays.update(dates.map(lambda x: x.date()))

    if adhoc:
        adhoc_dates = pd.to_datetime(adhoc, errors='coerce').dropna()
        holidays.update(adhoc_dates.map(lambda x: x.date()))

    return holidays

def is_business_day(date, holidays):
    date_only = date.date() if hasattr(date, "date") else date
    return date.weekday() < 5 and date_only not in holidays
