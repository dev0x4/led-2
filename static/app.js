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
  const v = (cur>0)?0:100; // toggle 100
  socket.emit('cmd',{pwm1: v});
};
document.getElementById('toggle2').onclick = ()=> {
  const cur = parseInt(document.getElementById('val2').innerText||'0');
  const v = (cur>0)?0:100;
  socket.emit('cmd',{pwm2: v});
};

// sliders with debounce & change-detection
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

// effects (NÂNG CẤP)
let chosenEffect = 'none';
function chooseEffect(n){ chosenEffect = n; highlightEffect(n); }
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

function addLog(s){
  const box = document.getElementById('log');
  if(!box) return;
  const d = document.createElement('div'); d.textContent = s; d.style.padding='6px'; box.appendChild(d); box.scrollTop=box.scrollHeight;
}
