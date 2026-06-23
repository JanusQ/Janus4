#!/usr/bin/env python3
import argparse
import csv
import json
import math
from pathlib import Path
import select
import socket
import struct
import time


MAGIC = 0x5741564544445230  # "WAVEDDR0"


def pack_iq(i_val: int, q_val: int) -> int:
    return ((q_val & 0xFFFF) << 16) | (i_val & 0xFFFF)


def iq_word(index: int, mode: str) -> int:
    if mode == "zero":
        i_val = 0
        q_val = 0
    elif mode == "square":
        phase = index & 0x3F
        i_val = 12000 if phase < 32 else -12000
        q_val = 0
    else:
        i_val = index & 0x7FFF
        q_val = (index * 3) & 0x7FFF
    return pack_iq(i_val, q_val)


def synthetic_iq_words(samples: int, mode: str) -> list[int]:
    return [iq_word(index, mode) for index in range(samples)]


def quantize_to_i16(values, scale: float) -> list[int]:
    out = []
    for value in values:
        q = int(round(float(value) * scale))
        out.append(max(-32768, min(32767, q)))
    return out


def load_s21_iq_words(path: Path, samples: int, state_index: int, shot_index: int, scale: float | None) -> list[int]:
    try:
        import numpy as np
        import scipy.io as sio
    except ImportError as exc:
        raise SystemExit("S21 mode requires numpy and scipy: " + str(exc)) from exc

    mat = sio.loadmat(path)
    if "data" not in mat:
        raise SystemExit(f"{path} does not contain variable 'data'")

    data = mat["data"]
    if data.ndim != 4 or data.shape[-1] < 2:
        raise SystemExit(f"unexpected S21 data shape {data.shape}; expected (state, shot, sample, iq)")
    if state_index < 0 or state_index >= data.shape[0]:
        raise SystemExit(f"--s21-state out of range 0..{data.shape[0] - 1}")
    if shot_index < 0 or shot_index >= data.shape[1]:
        raise SystemExit(f"--s21-shot out of range 0..{data.shape[1] - 1}")
    if samples > data.shape[2]:
        raise SystemExit(f"--samples {samples} exceeds S21 trace length {data.shape[2]}")

    trace = np.asarray(data[state_index, shot_index, :samples, :2], dtype=float)
    if scale is None:
        peak = float(np.max(np.abs(trace)))
        scale = 28000.0 / peak if peak > 0.0 and math.isfinite(peak) else 1.0

    i_vals = quantize_to_i16(trace[:, 0], scale)
    q_vals = quantize_to_i16(trace[:, 1], scale)
    return [pack_iq(i_val, q_val) for i_val, q_val in zip(i_vals, q_vals)]


def beat128_from_words(words: list[int], start_sample: int) -> int:
    value = 0
    for lane in range(4):
        value |= words[start_sample + lane] << (32 * lane)
    return value


def load_feedback_packet_words(path: Path | None, fallback_words: int, branch: int) -> list[int]:
    if path is None:
        return [feedback_packet_word(i, branch) for i in range(fallback_words)]

    data = []
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        if len(parts) == 1 and len(parts[0]) == 16:
            data.append(int(parts[0], 16))
            continue
        tokens = parts[1:] if len(parts) > 1 else parts
        data.extend(int(token, 16) for token in tokens)
    if data and any(value > 0xFF for value in data):
        return data
    if len(data) % 8:
        raise SystemExit(f"{path}: byte count must be a multiple of 8")

    words = []
    for offset in range(0, len(data), 8):
        word = 0
        for shift, value in enumerate(data[offset:offset + 8]):
            word |= value << (8 * shift)
        words.append(word)
    return words


def feedback_word(index: int, branch: int) -> int:
    # Branch 0 is idle. Branch 1 is a deterministic DRAG-like pi-pulse proxy.
    # Each 32-bit sample packs Q[31:16] and I[15:0].
    if branch == 0:
        i_val = 0
        q_val = 0
    else:
        center = 15.5
        sigma = 5.0
        x = (index - center) / sigma
        amp = int(round(12000.0 * pow(2.718281828459045, -0.5 * x * x)))
        deriv = int(round(-0.35 * (index - center) / (sigma * sigma) * amp))
        i_val = max(-32768, min(32767, amp))
        q_val = max(-32768, min(32767, deriv))
    return ((q_val & 0xFFFF) << 16) | (i_val & 0xFFFF)


def feedback_packet_word(pair_index: int, branch: int) -> int:
    sample0 = feedback_word(pair_index * 2, branch)
    sample1 = feedback_word(pair_index * 2 + 1, branch)
    return ((sample1 & 0xFFFFFFFF) << 32) | (sample0 & 0xFFFFFFFF)


def feedback_beat128(start_word: int, branch: int) -> int:
    lo = feedback_packet_word(start_word, branch)
    hi = feedback_packet_word(start_word + 1, branch)
    return (hi << 64) | lo


def send_u64(sock: socket.socket, target, value: int, gap_s: float) -> None:
    sock.sendto(struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF), target)
    if gap_s:
        time.sleep(gap_s)


def send_u128_as_instr(sock: socket.socket, target, value: int, gap_s: float) -> None:
    send_u64(sock, target, value & 0xFFFFFFFFFFFFFFFF, gap_s)
    send_u64(sock, target, (value >> 64) & 0xFFFFFFFFFFFFFFFF, gap_s)


def send_ddr128_write(sock: socket.socket, target, addr: int, value: int, gap_s: float) -> None:
    send_u64(sock, target, MAGIC, gap_s)
    send_u64(sock, target, addr, gap_s)
    send_u64(sock, target, value & 0xFFFFFFFFFFFFFFFF, gap_s)
    send_u64(sock, target, (value >> 64) & 0xFFFFFFFFFFFFFFFF, gap_s)


def make_play_instr(channel: int, addr: int, byte_len: int) -> int:
    opcode = 0x2
    low = ((byte_len & 0xFFFFFFFF) << 32) | ((channel & 0xF) << 4) | opcode
    return ((addr & 0xFFFFFFFFFFFFFFFF) << 64) | low


def make_end_instr(auto_start: bool = True, loop: bool = False) -> int:
    opcode = 0x3
    channel = 0xF if auto_start else 0x0
    low = ((1 if loop else 0) << 8) | (channel << 4) | opcode
    return low


def parse_result(payload: bytes, artery_clock_mhz: float) -> dict:
    word = struct.unpack("<Q", payload[:8])[0]
    packet_type = (word >> 56) & 0xFF
    pred_state = word & 0x1
    actual_state = (word >> 1) & 0x1
    pred_correct = (word >> 2) & 0x1
    predict_prob_low8 = (word >> 8) & 0xFF
    latency_cycles = (word >> 16) & 0xFFFFFF
    window_count = (word >> 40) & 0xFFFF
    return {
        "raw": word,
        "packet_type": packet_type,
        "pred_state": pred_state,
        "actual_state": actual_state,
        "pred_correct": pred_correct,
        "predict_prob_low8": predict_prob_low8,
        "latency_cycles": latency_cycles,
        "latency_us": latency_cycles / artery_clock_mhz,
        "artery_clock_mhz": artery_clock_mhz,
        "window_count": window_count,
        "actual_state_note": "not reliable in early-feedback mode",
        "pred_correct_note": "transport check only; not algorithm accuracy",
    }


def parse_feedback_word(payload: bytes) -> tuple[int, int]:
    word = struct.unpack("<Q", payload[:8])[0]
    sample0 = word & 0xFFFFFFFF
    sample1 = (word >> 32) & 0xFFFFFFFF
    return sample0, sample1


def s16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def unpack_iq(sample: int) -> tuple[int, int]:
    return s16(sample), s16(sample >> 16)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write IQ samples to DDR, play them into ARTERY, and read UDP latency result."
    )
    parser.add_argument("--iface-ip", default="192.168.1.3")
    parser.add_argument("--fpga-ip", default="192.168.1.128")
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--interface", default="enp225s0f0")
    parser.add_argument("--samples", type=int, default=4096)
    parser.add_argument("--ddr-addr", type=lambda x: int(x, 0), default=0)
    parser.add_argument("--play-start-sample", type=int, default=0)
    parser.add_argument("--source", choices=["s21", "synthetic"], default="s21")
    parser.add_argument("--mode", choices=["zero", "ramp", "square"], default="ramp")
    parser.add_argument("--s21-mat", default="/home/syyao/zcu216_loopback/s21_data.mat")
    parser.add_argument("--s21-state", type=int, default=0)
    parser.add_argument("--s21-shot", type=int, default=0)
    parser.add_argument("--s21-scale", type=float, default=76.92307692307692)
    parser.add_argument("--gap-us", type=float, default=50.0)
    parser.add_argument("--post-write-wait-ms", type=float, default=20.0)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--feedback-words", type=int, default=4)
    parser.add_argument("--feedback0-addr", type=lambda x: int(x, 0), default=0x10000)
    parser.add_argument("--feedback1-addr", type=lambda x: int(x, 0), default=0x20000)
    parser.add_argument("--feedback0-hex", default="custom_xczu47dr_rfdc.srcs/sources_1/imports/hardware/vivado/src/feedback_branch0.mem")
    parser.add_argument("--feedback1-hex", default="custom_xczu47dr_rfdc.srcs/sources_1/imports/hardware/vivado/src/feedback_branch1.mem")
    parser.add_argument("--preload-feedback", action="store_true")
    parser.add_argument("--preload-wait-ms", type=float, default=20.0)
    parser.add_argument("--allow-partial-feedback", action="store_true")
    parser.add_argument("--artery-clock-mhz", type=float, default=200.0)
    parser.add_argument("--csv", default="artifacts/artery_ddr_feedback_waveform.csv")
    args = parser.parse_args()

    if args.samples % 8:
        raise SystemExit("--samples must be a multiple of 8 for the 256-bit DDR writer")
    if args.play_start_sample % 4:
        raise SystemExit("--play-start-sample must be a multiple of 4 for the 128-bit DDR writer")
    if args.play_start_sample < 0 or args.play_start_sample >= args.samples:
        raise SystemExit("--play-start-sample must be inside the uploaded sample range")
    if args.feedback_words % 2:
        raise SystemExit("--feedback-words must be even because DDR writes are 128-bit")
    if args.feedback_words % 4:
        raise SystemExit("--feedback-words must be a multiple of 4 for the 256-bit DDR writer")

    feedback_expected = [
        load_feedback_packet_words(Path(args.feedback0_hex) if args.feedback0_hex else None, args.feedback_words, 0),
        load_feedback_packet_words(Path(args.feedback1_hex) if args.feedback1_hex else None, args.feedback_words, 1),
    ]
    for branch, words in enumerate(feedback_expected):
        if len(words) < args.feedback_words:
            raise SystemExit(f"feedback branch {branch} has {len(words)} words, need {args.feedback_words}")

    if args.source == "s21":
        iq_words = load_s21_iq_words(Path(args.s21_mat), args.samples, args.s21_state, args.s21_shot, args.s21_scale)
        print(
            f"S21 source: mat={args.s21_mat}, state={args.s21_state}, shot={args.s21_shot}, "
            f"samples={args.samples}"
        )
    else:
        iq_words = synthetic_iq_words(args.samples, args.mode)
        print(f"synthetic source: mode={args.mode}, samples={args.samples}")

    byte_len = args.samples * 4
    feedback_byte_len = args.feedback_words * 8
    gap_s = args.gap_us / 1_000_000.0
    target = (args.fpga_ip, args.port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if args.interface:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, args.interface.encode())
    sock.bind((args.iface_ip, args.port))
    sock.setblocking(False)

    print(f"write {args.samples} IQ samples ({byte_len} bytes) to DDR addr 0x{args.ddr_addr:x}")
    for sample in range(0, args.samples, 8):
        addr = args.ddr_addr + sample * 4
        low_128 = beat128_from_words(iq_words, sample)
        high_128 = beat128_from_words(iq_words, sample + 4)
        send_ddr128_write(sock, target, addr, low_128, gap_s)
        send_ddr128_write(sock, target, addr + 16, high_128, gap_s)

    print(
        f"write branch pulse waveforms: branch0 addr=0x{args.feedback0_addr:x}, "
        f"branch1 addr=0x{args.feedback1_addr:x}, {feedback_byte_len} bytes each"
    )
    for branch, base_addr in ((0, args.feedback0_addr), (1, args.feedback1_addr)):
        for word_index in range(0, args.feedback_words, 4):
            addr = base_addr + word_index * 8
            low_128 = ((feedback_expected[branch][word_index + 1] & 0xFFFFFFFFFFFFFFFF) << 64) | (
                feedback_expected[branch][word_index] & 0xFFFFFFFFFFFFFFFF
            )
            high_128 = ((feedback_expected[branch][word_index + 3] & 0xFFFFFFFFFFFFFFFF) << 64) | (
                feedback_expected[branch][word_index + 2] & 0xFFFFFFFFFFFFFFFF
            )
            send_ddr128_write(sock, target, addr, low_128, gap_s)
            send_ddr128_write(sock, target, addr + 16, high_128, gap_s)

    if args.post_write_wait_ms > 0:
        time.sleep(args.post_write_wait_ms / 1000.0)

    play_addr = args.ddr_addr + args.play_start_sample * 4
    play_byte_len = byte_len - args.play_start_sample * 4
    if args.preload_feedback:
        print(
            "preload feedback branches first: PLAY ch2/ch3, END(auto-start); "
            f"wait {args.preload_wait_ms:g} ms before ch1"
        )
        send_u128_as_instr(sock, target, make_play_instr(channel=2, addr=args.feedback0_addr, byte_len=feedback_byte_len), gap_s)
        send_u128_as_instr(sock, target, make_play_instr(channel=3, addr=args.feedback1_addr, byte_len=feedback_byte_len), gap_s)
        send_u128_as_instr(sock, target, make_end_instr(auto_start=True), gap_s)
        if args.preload_wait_ms > 0:
            time.sleep(args.preload_wait_ms / 1000.0)
        print(
            "send PLAY ch1(IQ), END(auto-start); "
            f"ch1 starts at sample {args.play_start_sample} addr=0x{play_addr:x}, bytes={play_byte_len}"
        )
        send_u128_as_instr(sock, target, make_play_instr(channel=1, addr=play_addr, byte_len=play_byte_len), gap_s)
    else:
        print(
            "send PLAY ch1(IQ), END(auto-start); "
            f"ch1 starts at sample {args.play_start_sample} addr=0x{play_addr:x}, bytes={play_byte_len}"
        )
        send_u128_as_instr(sock, target, make_play_instr(channel=1, addr=play_addr, byte_len=play_byte_len), gap_s)
    send_u128_as_instr(sock, target, make_end_instr(auto_start=True), gap_s)

    deadline = time.monotonic() + args.timeout
    metadata = None
    feedback_words = []
    pre_metadata_words = []
    while metadata is None or len(feedback_words) < args.feedback_words:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if metadata is not None and args.allow_partial_feedback and feedback_words:
                print(
                    f"timeout with partial feedback: metadata=yes, "
                    f"feedback_words={len(feedback_words)}/{args.feedback_words}; saving partial result"
                )
                break
            print(
                f"timeout: metadata={'yes' if metadata else 'no'}, "
                f"feedback_words={len(feedback_words)}/{args.feedback_words}"
            )
            return 1
        ready, _, _ = select.select([sock], [], [], remaining)
        if not ready:
            continue
        payload, addr = sock.recvfrom(2048)
        if len(payload) < 8:
            print(f"ignore short UDP payload from {addr}: {payload.hex()}")
            continue
        result = parse_result(payload, args.artery_clock_mhz)
        if result["packet_type"] == 0xA5:
            metadata = result
            print(f"received metadata from {addr[0]}:{addr[1]}")
            print(
                "metadata raw=0x{raw:016x} window={window_count} latency={latency_cycles} cycles "
                "({latency_us:.2f} us @{artery_clock_mhz:.1f}MHz) pred={pred_state} actual={actual_state} "
                "correct={pred_correct} prob_low8=0x{predict_prob_low8:02x}".format(**result)
            )
            print("note: actual/correct fields are not used as accuracy in early-feedback mode")
            continue

        word = struct.unpack("<Q", payload[:8])[0]
        if metadata is None:
            pre_metadata_words.append(word)
            continue
        if pre_metadata_words:
            feedback_words.extend(pre_metadata_words)
            pre_metadata_words = []
        if len(feedback_words) < args.feedback_words:
            feedback_words.append(word)

    metadata["feedback_words_received"] = len(feedback_words)
    metadata["feedback_words_expected"] = args.feedback_words
    metadata["feedback_complete"] = len(feedback_words) >= args.feedback_words
    expected_words = feedback_expected[metadata["pred_state"]][:len(feedback_words)]
    bad_feedback = 0
    first_samples = []
    rows = []
    for idx, word in enumerate(feedback_words):
        sample0 = word & 0xFFFFFFFF
        sample1 = (word >> 32) & 0xFFFFFFFF
        exp_word = expected_words[idx]
        exp_sample0 = exp_word & 0xFFFFFFFF
        exp_sample1 = (exp_word >> 32) & 0xFFFFFFFF
        sample0_i, sample0_q = unpack_iq(sample0)
        sample1_i, sample1_q = unpack_iq(sample1)
        exp_sample0_i, exp_sample0_q = unpack_iq(exp_sample0)
        exp_sample1_i, exp_sample1_q = unpack_iq(exp_sample1)
        if len(first_samples) < 4:
            first_samples.extend([sample0, sample1])
        if word != expected_words[idx]:
            bad_feedback += 1
        rows.append({
            "word_index": idx,
            "selected_branch": metadata["pred_state"],
            "returned_raw": f"0x{word:016x}",
            "expected_raw": f"0x{exp_word:016x}",
            "match": int(word == exp_word),
            "returned_sample0": f"0x{sample0:08x}",
            "returned_sample0_i": sample0_i,
            "returned_sample0_q": sample0_q,
            "returned_sample1": f"0x{sample1:08x}",
            "returned_sample1_i": sample1_i,
            "returned_sample1_q": sample1_q,
            "expected_sample0": f"0x{exp_sample0:08x}",
            "expected_sample0_i": exp_sample0_i,
            "expected_sample0_q": exp_sample0_q,
            "expected_sample1": f"0x{exp_sample1:08x}",
            "expected_sample1_i": exp_sample1_i,
            "expected_sample1_q": exp_sample1_q,
        })

    metadata["feedback_match_words"] = len(feedback_words) - bad_feedback
    metadata["feedback_bad_words"] = bad_feedback

    csv_path = Path(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    meta_path = csv_path.with_suffix(".metadata.json")
    meta_path.write_text(json.dumps(metadata, indent=2) + "\n")

    print(
        f"feedback waveform: {len(feedback_words)} UDP words, "
        f"selected_branch={metadata['pred_state']}, bad_words={bad_feedback}, "
        f"csv={csv_path}, metadata={meta_path}"
    )
    print("first_samples=" + ",".join(f"0x{x:08x}" for x in first_samples[:4]))
    if bad_feedback != 0 and not args.allow_partial_feedback:
        return 2
    if len(feedback_words) < args.feedback_words and not args.allow_partial_feedback:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
