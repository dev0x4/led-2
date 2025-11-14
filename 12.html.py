# server.py
# Flask + SocketIO server for ESP32 control
# Responsive UI, mobile-friendly bottom nav, debounce, no spam,
# effects (with targets), wifi list (in-memory), log to registered desktop clients only.

from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO
import socket
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

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

# ----------------------- UI HTML (embedded) -----------------------
UI_HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32 Dashboard</title>
<style>
:root{
  --bg-light:#f3f6f8;--bg-dark:#0b0c0e;
  --glass:rgba(255,255,255,0.7);--glass-dark:rgba(255,255,255,0.04);
  --accent:#00aaff;--accent2:#ff4fa5;--radius:20px;--blur:22px;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial;color:#111;background:var(--bg-light);transition:all .25s}
body.dark{background:var(--bg-dark);color:#fff}
.app{display:flex;height:100vh;overflow:hidden}
.sidebar{width:92px;padding:18px;background:var(--glass);backdrop-filter:blur(var(--blur));display:flex;flex-direction:column;align-items:center;border-right:1px solid rgba(0,0,0,0.06)}
body.dark .sidebar{background:var('var(--glass-dark)')}
.logo{width:56px;height:56px;border-radius:14px;background:linear-gradient(135deg,var(--accent),#0077cc);display:flex;align-items:center;justify-content:center;color:#fff;margin-bottom:16px}
.icon-btn{width:46px;height:46px;border-radius:12px;border:none;margin:8px 0;background:rgba(255,255,255,0.06);color:#fff;font-size:20px;cursor:pointer}
.icon-btn.active{transform:scale(1.12);background:var(--accent)}
.main{flex:1;padding:18px 22px;overflow:auto;position:relative}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
@media(max-width:900px){ .header{display:none} }
.card{background:var(--glass);backdrop-filter:blur(var(--blur));border-radius:20px;padding:18px;margin-bottom:14px;box-shadow:0 8px 26px rgba(0,0,0,0.08)}
body.dark .card{background:var('var(--glass-dark)')}
.title{font-weight:700;margin-bottom:10px}
.btn{padding:10px 14px;border-radius:12px;border:none;background:var(--accent2);color:#fff;font-weight:700;cursor:pointer}
.btn.secondary{background:rgba(255,255,255,0.12);color:inherit}
.slider{width:100%;height:12px;border-radius:8px;background:linear-gradient(90deg,var(--accent2),#fff5);-webkit-appearance:none;outline:none}
.slider::-webkit-slider-thumb{width:18px;height:18px;border-radius:50%;background:#fff;box-shadow:0 6px 18px rgba(0,0,0,0.18)}
.log-panel{width:360px;padding:16px;background:var(--glass);backdrop-filter:blur(var(--blur));border-left:1px solid rgba(255,255,255,0.24);overflow:auto}
body.dark .log-panel{background:var('var(--glass-dark)')}
.log-title{font-weight:800;margin-bottom:10px}
.log-box{height:60vh;overflow:auto;padding:12px;border-radius:10px;background:linear-gradient(180deg,rgba(0,0,0,0.04),rgba(0,0,0,0.02));font-family:monospace}
.bottom-nav{display:none}
@media(max-width:900px){
  .sidebar{display:none}
  .log-panel{display:none}
  .bottom-nav{display:flex;position:fixed;left:12px;right:12px;bottom:8px;justify-content:space-around;padding:8px 12px;border-radius:16px;background:var(--glass);backdrop-filter:blur(18px)}
}
.bottom-nav button{background:transparent;border:none;padding:8px;border-radius:12px;font-size:20px;cursor:pointer}
.bottom-nav button.active{background:var(--accent);color:#fff}
.tag{display:inline-block;padding:8px 12px;margin:6px;border-radius:12px;background:rgba(0,0,0,0.06);cursor:pointer}
.tag.active{background:var(--accent2);color:#fff}
.checkbox-group label{display:inline-block;margin:6px 10px 6px 0;font-size:15px;cursor:pointer}
.checkbox-group input{margin-right:6px;transform:scale(1.1)}
.kv{opacity:.8;font-size:13px}
</style>
</head>
<body class="{{ theme }}">
<div class="app">
  <div class="sidebar">
    <div class="logo">ESP</div>
    <button id="btn-led1" class="icon-btn active" title="LED1" onclick="showPage('led1')">💡</button>
    <button id="btn-led2" class="icon-btn" title="LED2" onclick="showPage('led2')">🔆</button>
    <button id="btn-wifi" class="icon-btn" title="WiFi" onclick="showPage('wifi')">📶</button>
    <button id="btn-effects" class="icon-btn" title="Effects" onclick="showPage('effects')">✨</button>
    <button id="btn-settings" class="icon-btn" title="Settings" onclick="showPage('settings')">⚙️</button>
  </div>

  <div class="main">
    <div class="header">
      <div class="app-title" id="appTitle">Bảng Điều Khiển ESP32</div>
      <div style="display:flex;gap:8px;align-items:center">
        <button id="btnRefresh" class="btn secondary">Lấy trạng thái</button>
        <button id="btnTheme" class="btn secondary">Giao diện</button>
        <button id="btnLang" class="btn secondary">Ngôn ngữ</button>
      </div>
    </div>

    <div class="card page" id="page-led1" style="display:block">
      <div class="title" id="title-led1">Đèn LED 1</div>
      <button id="toggle1" class="btn">Bật / Tắt</button>
      <div style="margin-top:12px;">Độ sáng hiện tại: <b id="val1">{{ pwm1 }}</b>%</div>
      <div style="margin-top:12px">
        <input id="slider1" class="slider" type="range" min="0" max="100" value="{{ pwm1 }}">
      </div>
    </div>

    <div class="card page" id="page-led2" style="display:none">
      <div class="title" id="title-led2">Đèn LED 2</div>
      <button id="toggle2" class="btn">Bật / Tắt</button>
      <div style="margin-top:12px;">Độ sáng hiện tại: <b id="val2">{{ pwm2 }}</b>%</div>
      <div style="margin-top:12px">
        <input id="slider2" class="slider" type="range" min="0" max="100" value="{{ pwm2 }}">
      </div>
    </div>

    <div class="card page" id="page-effects" style="display:none">
      <div class="title">Hiệu ứng LED</div>
      <div id="effectBox">
        <div class="tag" data-effect="none" onclick="chooseEffect('none')">Tắt</div>
        <div class="tag" data-effect="sos" onclick="chooseEffect('sos')">SOS</div>
        <div class="tag" data-effect="blink_fast" onclick="chooseEffect('blink_fast')">Nháy nhanh</div>
        <div class="tag" data-effect="blink_slow" onclick="chooseEffect('blink_slow')">Nháy chậm</div>
        <div class="tag" data-effect="fade" onclick="chooseEffect('fade')">Fade</div>
        <div class="tag" data-effect="breathing" onclick="chooseEffect('breathing')">Breathing</div>
      </div>
      
      <div class="title" style="margin-top:16px">Mục tiêu (Target)</div>
      <div class="checkbox-group">
        <label><input type="checkbox" id="eff-target-1" value="led1" checked> LED 1</label>
        <label><input type="checkbox" id="eff-target-2" value="led2" checked> LED 2</label>
      </div>

      <div style="margin-top:12px">Tốc độ: <input id="effectSpeed" type="range" min="1" max="10" value="5" class="slider"></div>
      <div style="margin-top:12px">
        <button class="btn" onclick="applyEffect()">Áp dụng</button>
        <button class="btn secondary" onclick="stopEffect()">Tắt</button>
      </div>
    </div>

    <div class="card page" id="page-wifi" style="display:none">
      <div class="title">WiFi đã lưu</div>
      <div id="wifiList">Đang tải...</div>
      <div style="margin-top:12px">
        <input id="newSsid" placeholder="SSID" style="padding:8px;border-radius:8px;width:46%">
        <input id="newPass" placeholder="Pass" style="padding:8px;border-radius:8px;width:46%">
        <button class="btn" onclick="addWifi()">Lưu</button>
      </div>
    </div>

    <div class="card page" id="page-settings" style="display:none">
      <div class="title">Cài đặt</div>
      <div class="kv">Ngôn ngữ: <span id="langLabel">Tiếng Việt</span></div>
      <div style="height:8px"></div>
      <div class="kv">Theme: <span id="themeLabel">{{ theme }}</span></div>
      
      <div style="margin-top:20px; display:flex; gap:10px;">
        <button id="btnThemeMobile" class="btn secondary">Giao diện</button>
        <button id="btnLangMobile" class="btn secondary">Ngôn ngữ</button>
      </div>
      <div style="margin-top:12px">
        <button class="btn secondary" onclick="refreshStatus()">Lấy trạng thái</button>
      </div>
    </div>
  </div>

  <div class="log-panel" id="logPanel">
    <div class="log-title">Realtime Log</div>
    <div id="log" class="log-box"></div>
  </div>
</div>

<div class="bottom-nav" id="bottomNav" style="display:none">
  <button id="m-led1" onclick="showPage('led1')">💡</button>
  <button id="m-led2" onclick="showPage('led2')">🔆</button>
  <button id="m-wifi" onclick="showPage('wifi')">📶</button>
  <button id="m-effects" onclick="showPage('effects')">✨</button>
  <button id="m-settings" onclick="showPage('settings')">⚙️</button>
</div>

<script src="https://cdn.socket.io/4.7.4/socket.io.min.js"></script>
<script>
const socket = io();
const isMobile = window.innerWidth <= 900;
if (isMobile) {
  document.getElementById('bottomNav').style.display = 'flex';
  const lp = document.getElementById('logPanel');
  if (lp) lp.style.display = 'none';
} else {
  socket.emit('register_log');
}

// page switching
function showPage(name){
  ['led1','led2','wifi','effects','settings'].forEach(p=>{
    const el = document.getElementById('page-'+p);
    if(el) el.style.display = (p===name)?'block':'none';
  });
  ['led1','led2','wifi','effects','settings'].forEach(p=>{
    const b = document.getElementById('btn-'+p); if(b) b.classList.remove('active');
    const mb = document.getElementById('m-'+p); if(mb) mb.classList.remove('active');
  });
  const b = document.getElementById('btn-'+name); if(b) b.classList.add('active');
  const mb = document.getElementById('m-'+name); if(mb) mb.classList.add('active');
}

// socket handlers
socket.on('connect', ()=> addLog('[socket] connected'));
socket.on('status', (data)=> {
  if ('pwm1' in data){ document.getElementById('val1').innerText = data.pwm1; slider1.value = data.pwm1; }
  if ('pwm2' in data){ document.getElementById('val2').innerText = data.pwm2; slider2.value = data.pwm2; }
  
  if ('effect' in data){ 
    highlightEffect(data.effect.name); 
    const targets = data.effect.targets || [];
    document.getElementById('eff-target-1').checked = targets.includes('led1');
    document.getElementById('eff-target-2').checked = targets.includes('led2');
  }
  addLog('[status] '+JSON.stringify(data));
});
socket.on('log', m=>{
  const box = document.getElementById('log');
  if(!box || window.innerWidth <= 900) return;
  const div = document.createElement('div'); div.textContent = m.msg; div.style.padding='6px'; div.style.borderBottom='1px solid #0002';
  box.appendChild(div); box.scrollTop = box.scrollHeight;
});

// LED toggle
document.getElementById('toggle1').onclick = ()=> {
  const cur = parseInt(document.getElementById('val1').innerText||'0');
  const v = (cur>0)?0:100;
  socket.emit('cmd',{pwm1: v});
};
document.getElementById('toggle2').onclick = ()=> {
  const cur = parseInt(document.getElementById('val2').innerText||'0');
  const v = (cur>0)?0:100;
  socket.emit('cmd',{pwm2: v});
};

// sliders
const slider1 = document.getElementById('slider1');
const slider2 = document.getElementById('slider2');
let timers = {};
function debounce(id,fn,ms=180){ clearTimeout(timers[id]); timers[id]=setTimeout(fn,ms); }

slider1.oninput = (e)=>{
  document.getElementById('val1').innerText = e.target.value;
  debounce('s1', ()=> {
    socket.emit('cmd',{pwm1: parseInt(e.target.value)});
  }, 220);
};
slider2.oninput = (e)=>{
  document.getElementById('val2').innerText = e.target.value;
  debounce('s2', ()=> {
    socket.emit('cmd',{pwm2: parseInt(e.target.value)});
  }, 220);
};

// effects
let chosenEffect = 'none';
function chooseEffect(n){ chosenEffect = n; highlightEffect(n); }

// SỬA LỖI UI: Dùng data-effect để so sánh, không dùng textContent
function highlightEffect(n){
  document.querySelectorAll('#effectBox .tag').forEach(el => {
    el.classList.toggle('active', el.dataset.effect === n);
  });
}

function applyEffect(){
  const speed = parseInt(document.getElementById('effectSpeed').value||5);
  let targets = [];
  if (document.getElementById('eff-target-1').checked) targets.push('led1');
  if (document.getElementById('eff-target-2').checked) targets.push('led2');
  
  if (chosenEffect !== 'none' && targets.length === 0) {
      alert('Bạn phải chọn ít nhất 1 đèn để áp dụng hiệu ứng!');
      return;
  }
  
  socket.emit('effect',{name: chosenEffect, speed: speed, targets: targets});
}
function stopEffect(){ 
  socket.emit('effect',{name: 'none', speed:5, targets: []}); 
  highlightEffect('none'); 
}

// wifi management
function refreshWifi(){
  fetch('/wifi/list').then(r=>r.json()).then(arr=>{
    const box = document.getElementById('wifiList');
    if(!arr || arr.length===0) box.innerHTML = '<div class="kv">Không có WiFi lưu</div>';
    else box.innerHTML = arr.map((w,i)=>`<div style="padding:8px;border-bottom:1px solid #0002"><b>${w.ssid}</b> <div class="kv">pass: ${w.pass || '(không có)'}</div><button class="btn secondary" onclick="delWifi(${i})">Xóa</button></div>`).join('');
  });
}
function addWifi(){
  const ss = document.getElementById('newSsid').value||'';
  const ps = document.getElementById('newPass').value||'';
  if(!ss) return alert('Nhập SSID');
  fetch('/wifi/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ssid:ss,pass:ps})})
    .then(()=>{ refreshWifi(); });
}
function delWifi(i){
  fetch('/wifi/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i})})
    .then(()=> refreshWifi());
}

// settings
const themeHandler = ()=> {
  const t = document.body.classList.contains('dark') ? 'light' : 'dark';
  document.body.className = t;
  socket.emit('theme', t);
};
const langHandler = ()=> {
  socket.emit('lang', 'toggle');
};

document.getElementById('btnRefresh').onclick = ()=> refreshStatus();
const btnThemeDesktop = document.getElementById('btnTheme');
const btnLangDesktop = document.getElementById('btnLang');
if (btnThemeDesktop) btnThemeDesktop.onclick = themeHandler;
if (btnLangDesktop) btnLangDesktop.onclick = langHandler;
document.getElementById('btnThemeMobile').onclick = themeHandler;
document.getElementById('btnLangMobile').onclick = langHandler;

// refresh status from server
function refreshStatus(){
  fetch('/cmd').then(r=>r.json()).then(d=>{
    if('pwm1' in d){ document.getElementById('val1').innerText = d.pwm1; slider1.value = d.pwm1; }
    if('pwm2' in d){ document.getElementById('val2').innerText = d.pwm2; slider2.value = d.pwm2; }
  });
}

// initialize
document.getElementById('btn-led1').onclick = () => showPage('led1');
document.getElementById('btn-led2').onclick = () => showPage('led2');
document.getElementById('btn-wifi').onclick = () => showPage('wifi');
document.getElementById('btn-effects').onclick = () => showPage('effects');
document.getElementById('btn-settings').onclick = () => showPage('settings');

refreshWifi();
refreshStatus();
showPage('led1');

// small log helper (desktop only)
function addLog(s){
  const box = document.getElementById('log');
  if(!box) return;
  const d = document.createElement('div'); d.textContent = s; d.style.padding='6px'; box.appendChild(d); box.scrollTop=box.scrollHeight;
}
</script>
</body>
</html>
"""

# ----------------------- Flask routes -----------------------
@app.route("/")
def index():
    return render_template_string(UI_HTML, pwm1=state["pwm1"], pwm2=state["pwm2"], theme=state["theme"])

# ESP32 GETs this to read desired command/state
@app.route("/cmd")
def cmd():
    # Trả về TOÀN BỘ TRẠNG THÁI (bao gồm cả effect)
    return jsonify(state)

# (Các route khác không thay đổi)

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
        # Tắt hiệu ứng nếu người dùng tự chỉnh slider
        if state["effect"]["name"] != "none":
            state["effect"] = {"name": "none", "speed": 5, "targets": []}
            changed = True # (vẫn là true)
        
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
        
        # Nếu bật hiệu ứng, set PWM về 100 để hiệu ứng rõ
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
    print(f"SERVER RUNNING: http://0.0.0.0:5000  (LAN: http://{local_ip}:5000)")
    socketio.run(app, host="0.0.0.0", port=5000)
