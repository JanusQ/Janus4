#!/usr/bin/env python3
import argparse
import csv
import socket
import struct
import time
from pathlib import Path

import matplotlib.pyplot as plt

from artery_udp_check import make_sample


def receive_result(sock: socket.socket, timeout: float):
    sock.settimeout(timeout)
    payload, addr = sock.recvfrom(2048)
    if len(payload) < 8:
        raise RuntimeError(f"short UDP result from {addr}: {payload.hex()}")

    word = struct.unpack("<Q", payload[:8])[0]
    low = word & 0xFFFFFFFF
    return {
        "src_ip": addr[0],
        "src_port": addr[1],
        "raw": word,
        "low32": low,
        "pred_state": low & 0x1,
        "actual_state": (low >> 1) & 0x1,
        "pred_correct": (low >> 2) & 0x1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated ARTERY UDP windows and plot results.")
    parser.add_argument("--interface", default="enp225s0f0")
    parser.add_argument("--iface-ip", default="192.168.1.3")
    parser.add_argument("--fpga-ip", default="192.168.1.128")
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--samples", type=int, default=1024)
    parser.add_argument("--windows", type=int, default=20)
    parser.add_argument("--mode", choices=["zero", "ramp", "square"], default="ramp")
    parser.add_argument("--gap-us", type=float, default=100.0)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--out-dir", default="artifacts")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"artery_udp_results_{stamp}.csv"
    png_path = out_dir / f"artery_udp_results_{stamp}.png"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if args.interface:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, args.interface.encode())
    sock.bind((args.iface_ip, args.port))

    target = (args.fpga_ip, args.port)
    interval = args.gap_us / 1_000_000.0
    rows = []

    for win in range(args.windows):
        start = time.monotonic()
        for sample in range(args.samples):
            sock.sendto(make_sample(sample, args.mode), target)
            if interval:
                time.sleep(interval)

        result = receive_result(sock, args.timeout)
        result["window"] = win
        result["latency_ms"] = (time.monotonic() - start) * 1000.0
        rows.append(result)
        print(
            f"window={win:03d} raw=0x{result['raw']:016x} "
            f"pred={result['pred_state']} actual={result['actual_state']} "
            f"correct={result['pred_correct']} latency_ms={result['latency_ms']:.2f}"
        )

    fieldnames = [
        "window",
        "raw",
        "low32",
        "pred_state",
        "actual_state",
        "pred_correct",
        "latency_ms",
        "src_ip",
        "src_port",
    ]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    x = [r["window"] for r in rows]
    fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
    axes[0].step(x, [r["pred_state"] for r in rows], where="mid", label="pred_state")
    axes[0].step(x, [r["actual_state"] for r in rows], where="mid", label="actual_state")
    axes[0].set_ylim(-0.2, 1.2)
    axes[0].set_ylabel("state")
    axes[0].legend(loc="upper right")

    axes[1].bar(x, [r["pred_correct"] for r in rows], color="#2f6f4e")
    axes[1].set_ylim(0, 1.2)
    axes[1].set_ylabel("correct")

    axes[2].plot(x, [r["latency_ms"] for r in rows], marker="o", color="#2f5f9f")
    axes[2].set_ylabel("latency ms")
    axes[2].set_xlabel("1024-sample window")
    axes[2].grid(True, alpha=0.3)

    fig.suptitle("ARTERY UDP Result Windows")
    fig.tight_layout()
    fig.savefig(png_path, dpi=160)

    print(f"CSV: {csv_path}")
    print(f"PNG: {png_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
