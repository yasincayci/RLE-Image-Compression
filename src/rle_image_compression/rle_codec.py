from __future__ import annotations

import struct
from typing import Iterable, List, Sequence


RUN_MARKER = 1
LITERAL_MARKER = 0
MIN_RUN = 3
MAX_CHUNK = 65535


def encode_rle(values: Sequence[int]) -> bytes:
    output = bytearray()
    n = len(values)
    i = 0

    while i < n:
        run_len = 1
        while i + run_len < n and values[i + run_len] == values[i] and run_len < MAX_CHUNK:
            run_len += 1

        if run_len >= MIN_RUN:
            output.append(RUN_MARKER)
            output.append(values[i] & 0xFF)
            output.extend(struct.pack("<H", run_len))
            i += run_len
            continue

        literal_start = i
        i += run_len

        while i < n:
            lookahead = 1
            while i + lookahead < n and values[i + lookahead] == values[i] and lookahead < MIN_RUN:
                lookahead += 1

            if lookahead >= MIN_RUN:
                break

            i += lookahead
            if i - literal_start >= MAX_CHUNK:
                break

        literal_len = i - literal_start
        output.append(LITERAL_MARKER)
        output.extend(struct.pack("<H", literal_len))
        output.extend(values[literal_start:i])

    return bytes(output)


def decode_rle(payload: bytes, expected_count: int) -> List[int]:
    output: List[int] = []
    i = 0

    while i < len(payload):
        marker = payload[i]
        i += 1

        if marker == RUN_MARKER:
            value = payload[i]
            run_len = struct.unpack("<H", payload[i + 1 : i + 3])[0]
            i += 3
            output.extend([value] * run_len)
        elif marker == LITERAL_MARKER:
            lit_len = struct.unpack("<H", payload[i : i + 2])[0]
            i += 2
            output.extend(payload[i : i + lit_len])
            i += lit_len
        else:
            raise ValueError(f"Unknown marker in RLE payload: {marker}")

    if len(output) != expected_count:
        raise ValueError(f"Decoded value count mismatch: expected {expected_count}, got {len(output)}")

    return output


def compression_performance(original_size: int, compressed_size: int) -> float:
    if original_size == 0:
        return 0.0
    return 100.0 * (1.0 - (compressed_size / original_size))


def compression_rate(original_size: int, compressed_size: int) -> float:
    if original_size == 0:
        return 0.0
    return 100.0 * (compressed_size / original_size)
