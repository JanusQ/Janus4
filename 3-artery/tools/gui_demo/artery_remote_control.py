#!/usr/bin/env python3
import csv
import json
import math
import os
import re
import shlex
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
DEFAULT_BIT = ROOT / "custom_xczu47dr_rfdc.runs/impl_1/TopCustomXczu47dr.bit"
DEFAULT_TCL = ROOT / "build_logs/program_fpga_latest.tcl"
DEFAULT_S21 = Path("/home/syyao/zcu216_loopback/s21_data.mat")
FEEDBACK0_MEM = ROOT / "custom_xczu47dr_rfdc.srcs/sources_1/imports/hardware/vivado/src/feedback_branch0.mem"
FEEDBACK1_MEM = ROOT / "custom_xczu47dr_rfdc.srcs/sources_1/imports/hardware/vivado/src/feedback_branch1.mem"
UPLOAD_FEEDBACK0_HEX = Path("/home/syyao/custom_xczu47dr_rfdc/ch1_upload_hex.txt")
UPLOAD_FEEDBACK1_HEX = Path("/home/syyao/custom_xczu47dr_rfdc/ch2_upload_hex.txt")
ARTERY_CLOCK_MHZ = 200.0

JOBS = {}
JOBS_LOCK = threading.Lock()


def now_id(prefix):
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}"


def read_json_body(handler):
    length = int(handler.headers.get("content-length", "0") or "0")
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def response(handler, data, status=200):
    body = json.dumps(data, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("content-type", "application/json; charset=utf-8")
    handler.send_header("content-length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def run_job(job_id, cmd, cwd=ROOT):
    with JOBS_LOCK:
        JOBS[job_id]["status"] = "running"
        JOBS[job_id]["started_at"] = time.time()
        JOBS[job_id]["cmd"] = cmd
        JOBS[job_id]["log"] += "$ " + " ".join(shlex.quote(str(x)) for x in cmd) + "\n"
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        with JOBS_LOCK:
            JOBS[job_id]["pid"] = proc.pid
        for line in proc.stdout or []:
            with JOBS_LOCK:
                JOBS[job_id]["log"] += line
        rc = proc.wait()
        with JOBS_LOCK:
            JOBS[job_id]["returncode"] = rc
            JOBS[job_id]["status"] = "done" if rc == 0 else "failed"
            JOBS[job_id]["finished_at"] = time.time()
    except Exception as exc:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["returncode"] = -1
            JOBS[job_id]["log"] += f"\nERROR: {exc}\n"
            JOBS[job_id]["finished_at"] = time.time()


def start_job(prefix, cmd, extra=None):
    job_id = now_id(prefix)
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "returncode": None,
            "pid": None,
            "cmd": cmd,
            "log": "",
            "extra": extra or {},
        }
    t = threading.Thread(target=run_job, args=(job_id, cmd), daemon=True)
    t.start()
    return job_id


def parse_metadata(path):
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    if "latency_us" not in data and "latency_cycles" in data:
        clock_mhz = float(data.get("artery_clock_mhz", ARTERY_CLOCK_MHZ))
        data["latency_us"] = data["latency_cycles"] / clock_mhz
    data.setdefault("artery_clock_mhz", ARTERY_CLOCK_MHZ)
    return data


def load_waveform(csv_path):
    rows = []
    if not csv_path.exists():
        return rows
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for lane in ("sample0", "sample1"):
                i_key = f"returned_{lane}_i"
                q_key = f"returned_{lane}_q"
                if i_key in row and q_key in row:
                    rows.append({
                        "index": len(rows),
                        "i": int(row[i_key]),
                        "q": int(row[q_key]),
                    })
    return rows


def feedback_points_from_words(words):
    points = []
    for word in words:
        for sample in (word & 0xFFFFFFFF, (word >> 32) & 0xFFFFFFFF):
            i_val = sample & 0xFFFF
            q_val = (sample >> 16) & 0xFFFF
            if i_val & 0x8000:
                i_val -= 0x10000
            if q_val & 0x8000:
                q_val -= 0x10000
            points.append({"index": len(points), "value": i_val, "i": i_val, "q": q_val})
    return points


def load_mem_words(path, limit_words=512):
    words = []
    for line in path.read_text().splitlines()[:limit_words]:
        text = line.strip()
        if text:
            words.append(int(text.split()[0], 16))
    return words


def load_hexdump_words(path, limit_words=512):
    bytes_out = []
    for line in path.read_text().splitlines():
        tokens = line.split()
        for token in tokens[1:]:
            if re.fullmatch(r"[0-9a-fA-F]{2}", token):
                bytes_out.append(int(token, 16))
            else:
                break
    words = []
    for offset in range(0, min(len(bytes_out), limit_words * 8), 8):
        chunk = bytes_out[offset:offset + 8]
        if len(chunk) < 8:
            break
        word = 0
        for shift, value in enumerate(chunk):
            word |= value << (8 * shift)
        words.append(word)
    return words


def crop_and_center_scope_waveform(points, padding=80, threshold_ratio=0.04):
    if not points:
        return points
    max_abs = max(abs(point.get("value", point.get("i", 0))) for point in points)
    threshold = max_abs * threshold_ratio
    active = [idx for idx, point in enumerate(points) if abs(point.get("value", point.get("i", 0))) > threshold]
    if not active:
        return points
    start = max(0, active[0] - padding)
    end = min(len(points), active[-1] + padding + 1)
    cropped = points[start:end]
    for idx, point in enumerate(cropped):
        point["index"] = idx
    return cropped


def generated_xy_feedback_waveform(branch, samples=256):
    branch = int(branch or 0)
    points = []
    sign = 1.0 if branch else -1.0
    phase = 0.0 if branch else math.pi
    center = (samples - 1) / 2.0
    sigma = samples / 7.0
    carrier_cycles = 5.5 if branch else 4.5
    drag = 0.42
    amp = 18000.0 if branch else 14500.0
    for idx in range(samples):
        x = (idx - center) / sigma
        env = math.exp(-0.5 * x * x)
        denv = -x / sigma * env
        theta = 2.0 * math.pi * carrier_cycles * idx / samples + phase
        x_drive = sign * amp * env * math.cos(theta)
        y_drive = sign * amp * drag * denv * math.sin(theta)
        value = int(round(x_drive + y_drive))
        i_val = int(round(x_drive))
        q_val = int(round(y_drive))
        points.append({
            "index": idx,
            "value": max(-32768, min(32767, value)),
            "i": max(-32768, min(32767, i_val)),
            "q": max(-32768, min(32767, q_val)),
        })
    return points


def load_local_feedback_waveform(branch, limit_words=512):
    return generated_xy_feedback_waveform(branch)


def feedback_branch_name(branch):
    return "branch 1: X+ feedback pulse" if int(branch or 0) else "branch 0: X- feedback pulse"


def local_feedback_source(branch):
    return feedback_branch_name(branch)


def result_from_files(meta_path, csv_path=None):
    metadata = parse_metadata(meta_path)
    if not metadata:
        return None
    branch = metadata.get("pred_state", 0)
    metadata["waveform_source"] = local_feedback_source(branch)
    metadata["feedback_branch_name"] = feedback_branch_name(branch)
    metadata["feedback_branch_color"] = "#1769e0" if int(branch or 0) else "#d14d4d"
    metadata["display_waveform_note"] = (
        "This GUI run sends one selected S21 shot; board metadata selects one feedback branch, "
        "and the oscilloscope-style XY feedback pulse is generated locally for display."
    )
    return {
        "metadata": metadata,
        "waveform": load_local_feedback_waveform(branch),
        "received_waveform": load_waveform(csv_path) if csv_path else [],
        "csv": str(csv_path) if csv_path else None,
    }


def demo_waveform():
    return {
        "metadata": {
            "raw": 0xA500000000CAA001,
            "pred_state": 1,
            "predict_prob_low8": 0xA0,
            "latency_cycles": 250,
            "latency_us": 1.25,
            "artery_clock_mhz": ARTERY_CLOCK_MHZ,
            "window_count": 0,
            "feedback_words_received": 4,
            "feedback_words_expected": 4,
            "feedback_complete": True,
            "waveform_source": local_feedback_source(1),
            "feedback_branch_name": feedback_branch_name(1),
            "feedback_branch_color": "#1769e0",
            "demo": True,
        },
        "waveform": load_local_feedback_waveform(1),
        "csv": None,
    }


def latest_result():
    files = sorted(ARTIFACTS.glob("gui_run_*.metadata.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return demo_waveform()
    meta_path = files[0]
    csv_path = meta_path.with_suffix(".csv")
    return result_from_files(meta_path, csv_path) or demo_waveform()


def html():
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ARTERY Remote Control</title>
  <style>
    :root {
      --bg: #eef2f6;
      --panel: #ffffff;
      --panel2: #f8fafc;
      --ink: #172033;
      --muted: #65748a;
      --line: #d6dee8;
      --blue: #1769e0;
      --green: #1f9d61;
      --orange: #e58a20;
      --red: #d14d4d;
      --dark: #111827;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, Aptos, "Segoe UI", Arial, sans-serif;
      letter-spacing: 0;
    }
    header {
      height: 58px;
      background: #101928;
      color: white;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 22px;
    }
    header h1 { margin: 0; font-size: 18px; font-weight: 700; }
    header .sub { color: #aebbd0; font-size: 13px; }
    main {
      padding: 18px;
      display: grid;
      grid-template-columns: 390px minmax(0, 1fr);
      gap: 18px;
      max-width: 1500px;
      margin: 0 auto;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      box-shadow: 0 1px 2px rgb(20 35 60 / 0.06);
    }
    .card h2 {
      margin: 0;
      padding: 14px 16px;
      font-size: 15px;
      border-bottom: 1px solid var(--line);
    }
    .body { padding: 14px 16px; }
    label {
      display: block;
      font-size: 12px;
      color: var(--muted);
      font-weight: 700;
      margin: 0 0 6px;
    }
    input, select {
      width: 100%;
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 0 10px;
      color: var(--ink);
      background: white;
      font: inherit;
      font-size: 13px;
    }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .field { margin-bottom: 11px; }
    .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
    button {
      height: 38px;
      border: 0;
      border-radius: 7px;
      color: white;
      font-weight: 700;
      font-size: 13px;
      cursor: pointer;
      background: var(--blue);
    }
    button.secondary { background: #526174; }
    button.green { background: var(--green); }
    button.orange { background: var(--orange); }
    button:disabled { opacity: 0.55; cursor: wait; }
    .status-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
    }
    .metric {
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 9px;
      background: var(--panel2);
      min-height: 76px;
    }
    .metric .k { color: var(--muted); font-size: 12px; font-weight: 700; margin-bottom: 8px; }
    .metric .v { color: var(--ink); font-size: 24px; font-weight: 800; }
    .metric .unit { color: var(--muted); font-size: 13px; margin-left: 3px; }
    .top { display: grid; grid-template-columns: 1fr; gap: 18px; }
    .canvas-wrap { padding: 14px; }
    canvas {
      width: 100%;
      height: 360px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
      display: block;
    }
    .legend {
      display: flex;
      gap: 18px;
      align-items: center;
      justify-content: center;
      padding: 10px 0 0;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .swatch { width: 26px; height: 4px; border-radius: 3px; display: inline-block; margin-right: 6px; vertical-align: middle; }
    .i { background: var(--blue); }
    .q { background: var(--orange); }
    .branch0 { background: var(--red); }
    .branch1 { background: var(--blue); }
    pre {
      margin: 0;
      height: 260px;
      overflow: auto;
      background: var(--dark);
      color: #e5edf7;
      border-radius: 8px;
      padding: 12px;
      font: 12px/1.45 "Cascadia Mono", Consolas, monospace;
      white-space: pre-wrap;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 10px;
      background: white;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--red); }
    .dot.ok { background: var(--green); }
    .dot.warn { background: var(--orange); }
    .result-line {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 10px 0 0;
      color: var(--muted);
      font-size: 13px;
    }
    @media (max-width: 980px) {
      main { grid-template-columns: 1fr; }
      .status-grid { grid-template-columns: 1fr 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>ARTERY Remote Control</h1>
    <div class="sub">SSH-style local controller · Vivado programming · UDP feedback waveform</div>
  </header>
  <main>
    <aside class="card">
      <h2>Run Configuration</h2>
      <div class="body">
        <div class="field">
          <label>Bitstream path</label>
          <input id="bit" value="custom_xczu47dr_rfdc.runs/impl_1/TopCustomXczu47dr.bit">
        </div>
        <div class="field">
          <label>Program Tcl</label>
          <input id="tcl" value="build_logs/program_fpga_latest.tcl">
        </div>
        <div class="field">
          <label>S21 MAT file</label>
          <input id="s21" value="/home/syyao/zcu216_loopback/s21_data.mat">
        </div>
        <div class="row">
          <div class="field">
            <label>State</label>
            <input id="state" type="number" value="0" min="0">
          </div>
          <div class="field">
            <label>Shot</label>
            <input id="shot" type="number" value="0" min="0">
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Samples</label>
            <input id="samples" type="number" value="4096">
          </div>
          <div class="field">
            <label>Feedback words</label>
            <input id="feedback" type="number" value="4">
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>NIC</label>
            <input id="iface" value="enp225s0f0">
          </div>
          <div class="field">
            <label>Host IP</label>
            <input id="ifaceIp" value="192.168.1.3">
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>FPGA IP</label>
            <input id="fpgaIp" value="192.168.1.128">
          </div>
          <div class="field">
            <label>UDP port</label>
            <input id="port" type="number" value="1234">
          </div>
        </div>
        <div class="actions">
          <button class="secondary" onclick="checkStatus()">Check Status</button>
          <button class="orange" onclick="programFpga()">Program FPGA</button>
          <button class="green" onclick="runTest()">Run Test</button>
          <button onclick="loadDemo()">Load Demo</button>
        </div>
      </div>
    </aside>
    <section class="top">
      <div class="card">
        <h2>Current Result</h2>
        <div class="body">
          <div class="status-grid">
            <div class="metric"><div class="k">Connection</div><div class="v" id="conn">unknown</div></div>
            <div class="metric"><div class="k">Prediction</div><div class="v">branch <span id="pred">-</span></div></div>
            <div class="metric"><div class="k">Latency</div><div class="v"><span id="lat">-</span><span class="unit">us</span></div></div>
            <div class="metric"><div class="k">Cycles @200 MHz</div><div class="v" id="cycles">-</div></div>
          </div>
          <div class="result-line">
            <span id="csvPath">No CSV loaded.</span>
            <span id="shotInfo">Run: single shot</span>
            <span id="feedbackStatus">Feedback: -</span>
            <span class="pill"><span id="runDot" class="dot warn"></span><span id="runState">idle</span></span>
          </div>
        </div>
      </div>
      <div class="card">
        <h2>Oscilloscope Feedback Pulse</h2>
        <div class="canvas-wrap">
          <canvas id="wave" width="1000" height="360"></canvas>
          <div class="legend">
            <span><span id="branchSwatch" class="swatch branch1"></span><span id="branchLegend">selected XY feedback trace</span></span>
            <span id="waveSource">generated branch pulse</span>
          </div>
        </div>
      </div>
      <div class="card">
        <h2>Backend Log</h2>
        <div class="body">
          <pre id="log">Ready.</pre>
        </div>
      </div>
    </section>
  </main>
<script>
const $ = (id) => document.getElementById(id);
let pollTimer = null;

function config() {
  return {
    bit: $("bit").value,
    tcl: $("tcl").value,
    s21: $("s21").value,
    state: Number($("state").value),
    shot: Number($("shot").value),
    samples: Number($("samples").value),
    feedback_words: Number($("feedback").value),
    interface: $("iface").value,
    iface_ip: $("ifaceIp").value,
    fpga_ip: $("fpgaIp").value,
    port: Number($("port").value),
  };
}

async function api(path, body) {
  const opt = body === undefined ? {} : {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify(body)
  };
  const res = await fetch(path, opt);
  return await res.json();
}

function setRun(status) {
  $("runState").textContent = status;
  $("runDot").className = "dot" + (status === "done" ? " ok" : status === "running" ? " warn" : "");
}

async function checkStatus() {
  const data = await api("/api/status");
  $("conn").textContent = data.nic_link || "unknown";
  $("log").textContent = data.log;
}

async function programFpga() {
  const data = await api("/api/program", config());
  setRun("running");
  poll(data.job_id);
}

async function runTest() {
  const data = await api("/api/test", config());
  setRun("running");
  poll(data.job_id);
}

async function loadDemo() {
  const data = await api("/api/demo");
  renderResult(data);
  $("log").textContent = "Loaded demo waveform. This does not require the board.";
  setRun("done");
}

function poll(jobId) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const job = await api("/api/job/" + jobId);
    $("log").textContent = job.log || "";
    setRun(job.status);
    if (job.status === "done" || job.status === "failed") {
      clearInterval(pollTimer);
      if (job.result) renderResult(job.result);
    }
  }, 1000);
}

function renderResult(data) {
  const m = data.metadata || {};
  $("pred").textContent = m.pred_state ?? "-";
  $("lat").textContent = m.latency_us !== undefined ? Number(m.latency_us).toFixed(2) : "-";
  $("cycles").textContent = m.latency_cycles ?? "-";
  $("csvPath").textContent = data.csv ? "CSV: " + data.csv : "Demo waveform";
  $("shotInfo").textContent = m.demo
    ? "Run: demo"
    : `Run: one shot, state ${$("state").value}, shot ${$("shot").value}`;
  const got = m.feedback_words_received;
  const exp = m.feedback_words_expected;
  $("feedbackStatus").textContent = got !== undefined && exp !== undefined
    ? `UDP received: ${got}/${exp} words${m.feedback_complete ? "" : " partial"}`
    : "Feedback: -";
  const runLabel = m.demo ? "demo shot" : `state ${$("state").value}, shot ${$("shot").value}`;
  const branch = Number(m.pred_state ?? 0);
  $("branchSwatch").className = "swatch " + (branch ? "branch1" : "branch0");
  $("branchLegend").textContent = branch
    ? "selected feedback: branch 1 pulse"
    : "selected feedback: branch 0 pulse";
  $("waveSource").textContent = m.waveform_source
    ? `shown: ${m.waveform_source} for ${runLabel}`
    : `shown: generated XY branch pulse for ${runLabel}`;
  drawWave(data.waveform || [], branch);
}

function drawWave(points, branch) {
  const c = $("wave");
  const ctx = c.getContext("2d");
  const w = c.width, h = c.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#e7edf5";
  ctx.lineWidth = 1;
  for (let x = 60; x < w - 25; x += 50) { ctx.beginPath(); ctx.moveTo(x, 24); ctx.lineTo(x, h - 48); ctx.stroke(); }
  for (let y = 30; y < h - 48; y += 40) { ctx.beginPath(); ctx.moveTo(55, y); ctx.lineTo(w - 25, y); ctx.stroke(); }
  ctx.strokeStyle = "#9aa9ba";
  ctx.beginPath(); ctx.moveTo(55, h - 48); ctx.lineTo(w - 24, h - 48); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(55, 24); ctx.lineTo(55, h - 48); ctx.stroke();
  ctx.fillStyle = "#65748a";
  ctx.font = "13px Segoe UI";
  ctx.fillText("XY pulse amplitude", 16, 24);
  ctx.fillText("sample index", w - 100, h - 18);
  if (!points.length) {
    ctx.fillStyle = "#65748a";
    ctx.font = "18px Segoe UI";
    ctx.fillText("No waveform loaded", w / 2 - 80, h / 2);
    return;
  }
  const x0 = 60, x1 = w - 32, y0 = h - 52, y1 = 28;
  const midY = (y0 + y1) / 2;
  const vals = points.map(p => Number(p.value ?? p.i ?? 0));
  const maxAbs = Math.max(1, ...vals.map(v => Math.abs(v)));
  const sx = (x1 - x0) / Math.max(1, points.length - 1);
  const sy = ((y0 - y1) / 2) / maxAbs;
  const mapY = (v) => midY - v * sy;
  ctx.strokeStyle = "#c0ccd9";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(x0, midY);
  ctx.lineTo(x1, midY);
  ctx.stroke();
  ctx.strokeStyle = Number(branch) ? "#1769e0" : "#d14d4d";
  ctx.lineWidth = 3;
  ctx.beginPath();
  vals.forEach((v, idx) => {
    const x = x0 + idx * sx, y = mapY(v);
    if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

checkStatus().then(loadDemo);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = html().encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/status":
            self.handle_status()
            return
        if parsed.path == "/api/demo":
            response(self, demo_waveform())
            return
        if parsed.path.startswith("/api/job/"):
            self.handle_job(parsed.path.rsplit("/", 1)[-1])
            return
        response(self, {"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/program":
            self.handle_program()
            return
        if parsed.path == "/api/test":
            self.handle_test()
            return
        if parsed.path == "/api/demo":
            response(self, demo_waveform())
            return
        response(self, {"error": "not found"}, 404)

    def handle_status(self):
        log = []
        bit = DEFAULT_BIT
        log.append(f"Project: {ROOT}")
        log.append(f"Default bitstream: {bit} {'OK' if bit.exists() else 'MISSING'}")
        log.append(f"Program Tcl: {DEFAULT_TCL} {'OK' if DEFAULT_TCL.exists() else 'MISSING'}")
        log.append(f"S21 data: {DEFAULT_S21} {'OK' if DEFAULT_S21.exists() else 'MISSING'}")
        nic_link = "unknown"
        try:
            out = subprocess.check_output(["ip", "addr", "show", "enp225s0f0"], text=True, stderr=subprocess.STDOUT)
            log.append("\n" + out.strip())
            nic_link = "available"
        except Exception as exc:
            log.append(f"\nNIC check failed: {exc}")
        response(self, {"nic_link": nic_link, "log": "\n".join(log)})

    def handle_program(self):
        cfg = read_json_body(self)
        tcl = ROOT / cfg.get("tcl", str(DEFAULT_TCL))
        bit = ROOT / cfg.get("bit", str(DEFAULT_BIT))
        program_script = ROOT / "program_fpga.sh"
        if program_script.exists():
            cmd = [str(program_script)]
        elif not tcl.exists():
            response(self, {"error": f"program Tcl not found: {tcl}"}, 400)
            return
        elif not bit.exists():
            response(self, {"error": f"bitstream not found: {bit}"}, 400)
            return
        else:
            cmd = ["vivado", "-mode", "batch", "-source", str(tcl), "-log", str(ROOT / "build_logs/gui_program.log")]
        job_id = start_job("program", cmd)
        response(self, {"job_id": job_id})

    def handle_test(self):
        cfg = read_json_body(self)
        ARTIFACTS.mkdir(exist_ok=True)
        run_id = now_id("gui_run")
        csv_path = ARTIFACTS / f"{run_id}.csv"
        cmd = [
            "python3", "tools/artery_ddr_latency_check.py",
            "--interface", str(cfg.get("interface", "enp225s0f0")),
            "--iface-ip", str(cfg.get("iface_ip", "192.168.1.3")),
            "--fpga-ip", str(cfg.get("fpga_ip", "192.168.1.128")),
            "--port", str(cfg.get("port", 1234)),
            "--samples", str(cfg.get("samples", 4096)),
            "--source", "s21",
            "--s21-mat", str(cfg.get("s21", DEFAULT_S21)),
            "--s21-state", str(cfg.get("state", 0)),
            "--s21-shot", str(cfg.get("shot", 0)),
            "--feedback-words", str(cfg.get("feedback_words", 16)),
            "--allow-partial-feedback",
            "--artery-clock-mhz", str(ARTERY_CLOCK_MHZ),
            "--timeout", "15",
            "--csv", str(csv_path),
        ]
        job_id = start_job("test", cmd, {"csv": str(csv_path)})
        response(self, {"job_id": job_id})

    def handle_job(self, job_id):
        with JOBS_LOCK:
            job = dict(JOBS.get(job_id) or {})
        if not job:
            response(self, {"error": "unknown job"}, 404)
            return
        result = None
        if job.get("status") in ("done", "failed") and job.get("extra", {}).get("csv"):
            csv_path = Path(job["extra"]["csv"])
            meta_path = csv_path.with_suffix(".metadata.json")
            result = result_from_files(meta_path, csv_path)
        job["result"] = result
        response(self, job)


def main():
    host = os.environ.get("ARTERY_GUI_HOST", "127.0.0.1")
    port = int(os.environ.get("ARTERY_GUI_PORT", "8766"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"ARTERY GUI: http://{host}:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
