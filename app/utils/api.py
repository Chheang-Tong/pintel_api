# --- app/utils/api.py ---
import time

def api_ok(message, data=None):
    return {
        "status": True,
        "message": message,
        "data": {
            **(data or {}),
            "API_TIME": int(time.time())
        }
    }

def api_error(message, data=None):
    return {
        "status": False,
        "message": message,
        "data": {
            **(data or {}),
            "API_TIME": int(time.time())
        }
    }