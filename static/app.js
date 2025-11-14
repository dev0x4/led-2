let lastPWM1 = -1;
let lastPWM2 = -1;

function showPage(id) {
    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    document.getElementById(id).classList.add("active");

    document.querySelectorAll(".sidebar .icon").forEach(i => i.classList.remove("active"));
    document.getElementById("btn-"+id).classList.add("active");
}

/* THEME */
function setTheme(t) {
    document.body.className = t;
}

/* SEND PWM WITH CHANGE DETECTION */
function sendPWM(n, v) {
    fetch("/set", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ ["pwm"+n]: v })
    });
}

/* PWM INPUT */
document.getElementById("slider1").oninput = e => {
    if (e.target.value != lastPWM1) {
        lastPWM1 = e.target.value;
        document.getElementById("val1").innerText = lastPWM1;
        sendPWM(1, lastPWM1);
    }
};

document.getElementById("slider2").oninput = e => {
    if (e.target.value != lastPWM2) {
        lastPWM2 = e.target.value;
        document.getElementById("val2").innerText = lastPWM2;
        sendPWM(2, lastPWM2);
    }
};

function toggleLED(n){
    sendPWM(n, 100);
}

/* SYNC FROM SERVER */
async function sync() {
    let r = await fetch("/cmd");
    let j = await r.json();

    if (j.pwm1 != lastPWM1) {
        lastPWM1 = j.pwm1;
        slider1.value = j.pwm1;
        val1.innerText = j.pwm1;
    }

    if (j.pwm2 != lastPWM2) {
        lastPWM2 = j.pwm2;
        slider2.value = j.pwm2;
        val2.innerText = j.pwm2;
    }

    setTimeout(sync, 800);
}

sync();
