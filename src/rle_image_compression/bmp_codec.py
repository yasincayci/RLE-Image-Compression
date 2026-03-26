from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple


Matrix = List[List[int]]


@dataclass
class IndexedBMP:
    width: int
    height: int
    bpp: int
    pixel_data_offset: int
    header_bytes: bytes
    pixels: Matrix


def _row_stride(width: int, bpp: int) -> int:
    bits_per_row = width * bpp
    return ((bits_per_row + 31) // 32) * 4


def _encode_row(row: Sequence[int], bpp: int) -> bytes:
    if bpp == 8:
        return bytes(row)
    if bpp == 4:
        out = bytearray()
        for i in range(0, len(row), 2):
            hi = row[i] & 0x0F
            lo = row[i + 1] & 0x0F if i + 1 < len(row) else 0
            out.append((hi << 4) | lo)
        return bytes(out)
    if bpp == 1:
        out = bytearray()
        current = 0
        count = 0
        for value in row:
            current = (current << 1) | (value & 0x01)
            count += 1
            if count == 8:
                out.append(current)
                current = 0
                count = 0
        if count > 0:
            current <<= 8 - count
            out.append(current)
        return bytes(out)
    raise ValueError(f"Unsupported bpp: {bpp}")


def _decode_row(data: bytes, width: int, bpp: int) -> List[int]:
    if bpp == 8:
        return list(data[:width])
    if bpp == 4:
        out: List[int] = []
        for byte in data:
            out.append((byte >> 4) & 0x0F)
            if len(out) < width:
                out.append(byte & 0x0F)
            if len(out) >= width:
                break
        return out
    if bpp == 1:
        out: List[int] = []
        for byte in data:
            for bit in range(7, -1, -1):
                out.append((byte >> bit) & 0x01)
                if len(out) >= width:
                    return out
        return out
    raise ValueError(f"Unsupported bpp: {bpp}")


def write_indexed_bmp(path: Path, pixels: Matrix, bpp: int, palette: Sequence[Tuple[int, int, int]]) -> None:
    height = len(pixels)
    width = len(pixels[0])

    colors_used = 1 << bpp
    if len(palette) < colors_used:
        raise ValueError(f"Palette must have at least {colors_used} entries for {bpp}-bit BMP")

    stride = _row_stride(width, bpp)
    pixel_data = bytearray()

    for y in range(height - 1, -1, -1):
        row_bytes = _encode_row(pixels[y], bpp)
        pixel_data.extend(row_bytes)
        padding = stride - len(row_bytes)
        if padding:
            pixel_data.extend(b"\x00" * padding)

    file_header_size = 14
    dib_header_size = 40
    palette_size = colors_used * 4
    offset = file_header_size + dib_header_size + palette_size

    file_size = offset + len(pixel_data)
    image_size = len(pixel_data)

    bf_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, offset)
    bi_header = struct.pack(
        "<IIIHHIIIIII",
        dib_header_size,
        width,
        height,
        1,
        bpp,
        0,
        image_size,
        2835,
        2835,
        colors_used,
        colors_used,
    )

    palette_bytes = bytearray()
    for r, g, b in palette[:colors_used]:
        palette_bytes.extend([b & 0xFF, g & 0xFF, r & 0xFF, 0])

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(bf_header)
        f.write(bi_header)
        f.write(palette_bytes)
        f.write(pixel_data)


def read_indexed_bmp(path: Path) -> IndexedBMP:
    data = path.read_bytes()

    if data[:2] != b"BM":
        raise ValueError("Not a BMP file")

    pixel_data_offset = struct.unpack("<I", data[10:14])[0]
    dib_size = struct.unpack("<I", data[14:18])[0]
    if dib_size < 40:
        raise ValueError("Unsupported DIB header")

    width = struct.unpack("<I", data[18:22])[0]
    height = struct.unpack("<I", data[22:26])[0]
    planes = struct.unpack("<H", data[26:28])[0]
    bpp = struct.unpack("<H", data[28:30])[0]
    compression = struct.unpack("<I", data[30:34])[0]

    if planes != 1 or compression != 0:
        raise ValueError("Only uncompressed indexed BMP files are supported")

    if bpp not in (1, 4, 8):
        raise ValueError("Only 1, 4, and 8-bit BMP files are supported")

    stride = _row_stride(width, bpp)
    pixels: Matrix = [[0 for _ in range(width)] for _ in range(height)]

    offset = pixel_data_offset
    for y in range(height - 1, -1, -1):
        row_data = data[offset : offset + stride]
        pixels[y] = _decode_row(row_data, width, bpp)
        offset += stride

    header_bytes = data[:pixel_data_offset]
    return IndexedBMP(
        width=width,
        height=height,
        bpp=bpp,
        pixel_data_offset=pixel_data_offset,
        header_bytes=header_bytes,
        pixels=pixels,
    )


def build_bmp_from_header_and_pixels(header_bytes: bytes, pixels: Matrix, bpp: int) -> bytes:
    width = len(pixels[0])
    height = len(pixels)
    stride = _row_stride(width, bpp)

    pixel_data = bytearray()
    for y in range(height - 1, -1, -1):
        row = _encode_row(pixels[y], bpp)
        pixel_data.extend(row)
        padding = stride - len(row)
        if padding:
            pixel_data.extend(b"\x00" * padding)

    output = bytearray(header_bytes)

    # Update BMP size and image geometry fields to keep the output valid.
    file_size = len(output) + len(pixel_data)
    struct.pack_into("<I", output, 2, file_size)

    # BITMAPINFOHEADER width/height fields.
    if len(output) >= 26:
        struct.pack_into("<I", output, 18, width)
        struct.pack_into("<I", output, 22, height)

    if len(output) >= 38:
        struct.pack_into("<I", output, 34, len(pixel_data))

    output.extend(pixel_data)
    return bytes(output)
