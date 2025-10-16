# --- app/utils/api.py ---
from datetime import datetime, timedelta

def api_ok(message, data=None):
    now = datetime.utcnow() + timedelta(hours=7)  # UTC+7
    api_time_unix = int(now.timestamp())
    api_time_human = now.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "status": True,
        "message": message,
        "data": {
            **(data or {}),
            # "API_TIME": api_time_unix,
            "API_TIME_HUMAN": api_time_human
        }
    }

def api_error(message, data=None):
    now = datetime.utcnow() + timedelta(hours=7)  # UTC+7
    api_time_unix = int(now.timestamp())
    api_time_human = now.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "status": False,
        "message": message,
        "data": {
            **(data or {}),
            # "API_TIME": api_time_unix,
            "API_TIME_HUMAN": api_time_human
        }
    }