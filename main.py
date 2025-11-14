# main.py
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO
import socket
import threading
import time

app = Flask(__name__)
# Giữ nguyên async_mode="gevent" để tương thích với Render
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gunicorn") 

# ----------------------- Shared state -----------------------
state = {
    "pwm1": 0,
    "pwm2": 0,
    "theme": "light",
    "lang": "vi",
    "effect": {"name": "none", "speed": 5, "targets": []},
    "saved_wifi": []  # list of {"ssid": "...", "pass": "..."}
}

_prev_state = dict(state)
log_clients = set()
_log_lock = threading.Lock()

def send_status_if_changed():
    """Emit 'status' only when state fields changed compared to snapshot."""
    global _prev_state
    changed = {}
    for k in ("pwm1", "pwm2", "effect", "theme", "lang"):
        if state.get(k) != _prev_state.get(k):
            changed[k] = state.get(k)
    if changed:
        socketio.emit("status", changed)
        _prev_state.update(changed)

def server_log(msg):
    """Print and send log to registered log clients only."""
    ts = time.strftime("%H:%M:%S")
    line = f"{ts}  —  {msg}"
    print(line)
    with _log_lock:
        bad = []
        for sid in list(log_clients):
            try:
                socketio.emit("log", {"msg": line}, room=sid)
            except Exception:
                bad.append(sid)
        for s in bad:
            if s in log_clients:
                log_clients.remove(s)

# ----------------------- Flask routes -----------------------
@app.route("/")
def index():
    # SỬA: Thay đổi từ render_template_string sang render_template
    return render_template("index.html", 
                           pwm1=state["pwm1"], 
                           pwm2=state["pwm2"], 
                           theme=state["theme"])

# ESP32 GETs this to read desired command/state
@app.route("/cmd")
def cmd():
    return jsonify(state)

@app.route("/whoami")
def whoami():
    return jsonify({"host": request.host})

@app.route("/status", methods=["POST"])
def status_post():
    data = request.get_json(silent=True)
    if not data:
        return "Bad Request", 400
    socketio.emit("status", data)
    server_log(f"ESP32 status: {data}")
    return "OK", 200

@app.route("/wifi/list")
def wifi_list():
    return jsonify(state["saved_wifi"])

@app.route("/wifi/add", methods=["POST"])
def wifi_add():
    j = request.get_json(silent=True) or {}
    ssid = j.get("ssid","")
    pw = j.get("pass","")
    if ssid:
        state["saved_wifi"].append({"ssid": ssid, "pass": pw})
        server_log(f"Saved WiFi: {ssid}")
        return "OK", 200
    return "Bad", 400

@app.route("/wifi/delete", methods=["POST"])
def wifi_delete():
    j = request.get_json(silent=True) or {}
    idx = j.get("index", None)
    if idx is None:
        return "Bad", 400
    try:
        idx = int(idx)
        if idx < 0 or idx >= len(state["saved_wifi"]):
            return "Bad", 400
        item = state["saved_wifi"].pop(idx)
        server_log(f"Deleted WiFi: {item.get('ssid')}")
        return "OK", 200
    except Exception:
        return "Bad", 400

# ----------------------- SocketIO handlers -----------------------
@socketio.on("register_log")
def on_register_log():
    sid = request.sid
    log_clients.add(sid)
    server_log(f"Client {sid} registered for logs")

@socketio.on("unregister_log")
def on_unregister_log():
    sid = request.sid
    if sid in log_clients: log_clients.remove(sid)
    server_log(f"Client {sid} unregistered for logs")

@socketio.on("cmd")
def on_cmd(data):
    changed = False
    if "pwm1" in data:
        new = int(data["pwm1"])
        if state["pwm1"] != new:
            state["pwm1"] = max(0, min(100, new))
            changed = True
    if "pwm2" in data:
        new = int(data["pwm2"])
        if state["pwm2"] != new:
            state["pwm2"] = max(0, min(100, new))
            changed = True
    if changed:
        server_log(f"UI cmd -> {data}")
        if state["effect"]["name"] != "none":
            state["effect"] = {"name": "none", "speed": 5, "targets": []}
            changed = True
        send_status_if_changed()

@socketio.on("theme")
def on_theme(t):
    state["theme"] = t
    server_log(f"Theme -> {t}")
    send_status_if_changed()

@socketio.on("lang")
def on_lang(l):
    if l == "toggle":
        state["lang"] = "en" if state.get("lang","vi")=="vi" else "vi"
    else:
        state["lang"] = l
    server_log(f"Lang -> {state['lang']}")
    send_status_if_changed()

@socketio.on("effect")
def on_effect(d):
    name = d.get("name", "none")
    speed = int(d.get("speed", 5))
    targets = d.get("targets", [])
    
    if (state["effect"].get("name") != name or
        state["effect"].get("speed") != speed or
        state["effect"].get("targets") != targets):
        
        state["effect"] = {"name": name, "speed": speed, "targets": targets}
        server_log(f"Effect -> {state['effect']}")
        
        if name != "none":
            if "led1" in targets and state["pwm1"] == 0: state["pwm1"] = 100
            if "led2" in targets and state["pwm2"] == 0: state["pwm2"] = 100
        send_status_if_changed()

# ----------------------- Run Server -----------------------
if __name__ == "__main__":
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"
    
    port = 5000
    host = "0.0.0.0"
    print(f"SERVER RUNNING: http://{host}:{port}  (LAN: http://{local_ip}:{port})")
    
    # Sửa: Chạy socketio với port và host
    socketio.run(app, host=host, port=port)

