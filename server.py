from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# PWM state
pwm1 = 0
pwm2 = 0

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/cmd")
def cmd():
    return jsonify({
        "pwm1": pwm1,
        "pwm2": pwm2
    })

@app.route("/set", methods=["POST"])
def set_pwm():
    global pwm1, pwm2
    data = request.json
    if "pwm1" in data: pwm1 = data["pwm1"]
    if "pwm2" in data: pwm2 = data["pwm2"]
    return "OK"

@app.route("/status", methods=["POST"])
def status():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
