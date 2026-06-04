import requests

GATEWAY_URL = "http://127.0.0.1:3100"

def get_qr():
    try:
        r = requests.post(f"{GATEWAY_URL}/sessions/qr")
        return r.json()
    except:
        return {"status": "error"}

def get_status():
    try:
        r = requests.get(f"{GATEWAY_URL}/sessions/status")
        return r.json()
    except:
        return {"status": "offline"}

def reconnect():
    try:
        r = requests.post(f"{GATEWAY_URL}/sessions/reconnect")
        return r.json()
    except:
        return {"status": "failed"}