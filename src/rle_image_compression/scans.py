from __future__ import annotations

from functools import lru_cache
from typing import Iterable, List, Sequence, Tuple


Matrix = List[List[int]]


def flatten_row_major(pixels: Matrix) -> List[int]:
    # Row-row rotate (serpentine): even rows L->R, odd rows R->L.
    output: List[int] = []
    for y, row in enumerate(pixels):
        if y % 2 == 0:
            output.extend(row)
        else:
            output.extend(reversed(row))
    return output


def unflatten_row_major(values: Sequence[int], width: int, height: int) -> Matrix:
    output = [[0 for _ in range(width)] for _ in range(height)]
    idx = 0
    for y in range(height):
        if y % 2 == 0:
            for x in range(width):
                output[y][x] = values[idx]
                idx += 1
        else:
            for x in range(width - 1, -1, -1):
                output[y][x] = values[idx]
                idx += 1
    return output


def flatten_col_major(pixels: Matrix) -> List[int]:
    height = len(pixels)
    width = len(pixels[0])
    output: List[int] = []
    for x in range(width):
        # Col-col rotate (serpentine): even cols T->B, odd cols B->T.
        if x % 2 == 0:
            for y in range(height):
                output.append(pixels[y][x])
        else:
            for y in range(height - 1, -1, -1):
                output.append(pixels[y][x])
    return output


def unflatten_col_major(values: Sequence[int], width: int, height: int) -> Matrix:
    output = [[0 for _ in range(width)] for _ in range(height)]
    idx = 0
    for x in range(width):
        if x % 2 == 0:
            for y in range(height):
                output[y][x] = values[idx]
                idx += 1
        else:
            for y in range(height - 1, -1, -1):
                output[y][x] = values[idx]
                idx += 1
    return output


@lru_cache(maxsize=8)
def _zigzag_order(block_size: int) -> List[Tuple[int, int]]:
    order: List[Tuple[int, int]] = []
    for s in range(2 * block_size - 1):
        if s % 2 == 0:
            r = min(s, block_size - 1)
            c = s - r
            while r >= 0 and c < block_size:
                order.append((r, c))
                r -= 1
                c += 1
        else:
            c = min(s, block_size - 1)
            r = s - c
            while c >= 0 and r < block_size:
                order.append((r, c))
                r += 1
                c -= 1
    return order


def _iter_blocks(width: int, height: int, block_size: int) -> Iterable[Tuple[int, int]]:
    for by in range(0, height, block_size):
        for bx in range(0, width, block_size):
            yield bx, by


def flatten_block_zigzag(pixels: Matrix, block_size: int = 64) -> List[int]:
    # Process each block independently, then apply zigzag only inside that block.
    height = len(pixels)
    width = len(pixels[0])
    if width % block_size != 0 or height % block_size != 0:
        raise ValueError("Image size must be divisible by block size for zigzag scan")

    output: List[int] = []
    order = _zigzag_order(block_size)
    for bx, by in _iter_blocks(width, height, block_size):
        for oy, ox in order:
            output.append(pixels[by + oy][bx + ox])
    return output


def unflatten_block_zigzag(values: Sequence[int], width: int, height: int, block_size: int = 64) -> Matrix:
    # Rebuild each block independently using the same per-block zigzag order.
    if width % block_size != 0 or height % block_size != 0:
        raise ValueError("Image size must be divisible by block size for zigzag scan")

    output = [[0 for _ in range(width)] for _ in range(height)]
    order = _zigzag_order(block_size)
    idx = 0
    for bx, by in _iter_blocks(width, height, block_size):
        for oy, ox in order:
            output[by + oy][bx + ox] = values[idx]
            idx += 1
    return output
