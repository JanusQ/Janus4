#!/usr/bin/env python3
import argparse
import select
import socket
import struct
import time


def make_sample(index: int, mode: str) -> bytes:
    if mode == "zero":
        i_val = 0
        q_val = 0
    elif mode == "ramp":
        i_val = index & 0x7fff
        q_val = (index * 3) & 0x7fff
    else:
        phase = index & 0x3f
        i_val = 12000 if phase < 32 else -12000
        q_val = 0

    word32 = ((q_val & 0xffff) << 16) | (i_val & 0xffff)
    return struct.pack("<Q", word32)


def parse_result(payload: bytes) -> str:
    if len(payload) < 8:
        return f"short payload: {payload.hex()}"

    word = struct.unpack("<Q", payload[:8])[0]
    low = word & 0xffffffff
    pred_state = low & 0x1
    actual_state = (low >> 1) & 0x1
    pred_correct = (low >> 2) & 0x1
    return (
        f"raw=0x{word:016x} low32=0x{low:08x} "
        f"pred_state={pred_state} actual_state={actual_state} "
        f"pred_correct={pred_correct}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send one ARTERY window over UDP and wait for the FPGA result."
    )
    parser.add_argument("--iface-ip", default="192.168.1.3")
    parser.add_argument("--fpga-ip", default="192.168.1.128")
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--samples", type=int, default=1024)
    parser.add_argument("--mode", choices=["zero", "ramp", "square"], default="ramp")
    parser.add_argument("--gap-us", type=float, default=50.0)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--interface", default=None)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if args.interface:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, args.interface.encode())
    sock.bind((args.iface_ip, args.port))
    sock.setblocking(False)

    target = (args.fpga_ip, args.port)
    print(
        f"send {args.samples} samples to {target[0]}:{target[1]}, "
        f"listen on {args.iface_ip}:{args.port}"
    )

    interval = args.gap_us / 1_000_000.0
    for index in range(args.samples):
        sock.sendto(make_sample(index, args.mode), target)
        if interval:
            time.sleep(interval)

    deadline = time.monotonic() + args.timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print("timeout: no UDP result received")
            return 1

        ready, _, _ = select.select([sock], [], [], remaining)
        if not ready:
            continue

        payload, addr = sock.recvfrom(2048)
        print(f"received {len(payload)} bytes from {addr[0]}:{addr[1]}")
        print(parse_result(payload))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
