# app/utils/net.py
from flask import request

def get_client_ip():
    # honor proxies/load balancers if present
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        # first ip in list is original client
        return xff.split(',')[0].strip()
    return request.headers.get('X-Real-IP') or request.remote_addr or None

def parse_coord(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def clamp_lat_lng(lat, lng):
    if lat is not None and not (-90.0 <= lat <= 90.0):
        lat = None
    if lng is not None and not (-180.0 <= lng <= 180.0):
        lng = None
    return lat, lng