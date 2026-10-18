"""Somfy RTS frame and waveform encoding.

Pure Python, no Home Assistant imports, so it can be unit tested on its own.

Protocol reference: https://pushstack.wordpress.com/somfy-rts-protocol/
"""

from __future__ import annotations

from enum import IntEnum

FRAME_KEY = 0xA7

MAX_REMOTE_ID = 0xFFFFFF
MAX_ROLLING_CODE = 0xFFFF

# Pulse timings in microseconds.
WAKEUP_HIGH_US = 9415
WAKEUP_LOW_US = 89565
HW_SYNC_US = 2560
SW_SYNC_HIGH_US = 4550
SW_SYNC_LOW_US = 640
HALF_SYMBOL_US = 640
INTERFRAME_GAP_US = 30415

# The first frame carries 2 hardware sync pulses, every repeated frame 7.
FIRST_FRAME_HW_SYNCS = 2
REPEAT_FRAME_HW_SYNCS = 7


class Button(IntEnum):
    """Somfy RTS button codes."""

    MY = 0x1
    UP = 0x2
    DOWN = 0x4
    PROG = 0x8


def build_frame(button: Button, rolling_code: int, remote_id: int) -> bytes:
    """Return the 7-byte obfuscated frame for one button press.

    Layout before obfuscation:
      [0] key, [1] button << 4 | checksum, [2..3] rolling code (big endian),
      [4..6] remote address (little endian).
    """
    if not 0 <= rolling_code <= MAX_ROLLING_CODE:
        raise ValueError(f"rolling code out of range: {rolling_code}")
    if not 0 < remote_id <= MAX_REMOTE_ID:
        raise ValueError(f"remote id out of range: {remote_id}")

    frame = [
        FRAME_KEY,
        (int(button) << 4) & 0xF0,
        (rolling_code >> 8) & 0xFF,
        rolling_code & 0xFF,
        remote_id & 0xFF,
        (remote_id >> 8) & 0xFF,
        (remote_id >> 16) & 0xFF,
    ]

    checksum = 0
    for byte in frame:
        checksum ^= byte ^ (byte >> 4)
    frame[1] |= checksum & 0x0F

    for i in range(1, len(frame)):
        frame[i] ^= frame[i - 1]

    return bytes(frame)


def build_pulses(frame: bytes, repetitions: int) -> list[tuple[bool, int]]:
    """Return the transmitter waveform as (level, duration_us) pairs.

    Bits are Manchester encoded: a rising edge in the middle of the symbol
    is a 1, a falling edge is a 0.
    """
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")

    pulses: list[tuple[bool, int]] = [
        (True, WAKEUP_HIGH_US),
        (False, WAKEUP_LOW_US),
    ]

    for rep in range(repetitions):
        syncs = FIRST_FRAME_HW_SYNCS if rep == 0 else REPEAT_FRAME_HW_SYNCS
        for _ in range(syncs):
            pulses.append((True, HW_SYNC_US))
            pulses.append((False, HW_SYNC_US))

        pulses.append((True, SW_SYNC_HIGH_US))
        pulses.append((False, SW_SYNC_LOW_US))

        for i in range(len(frame) * 8):
            bit = (frame[i // 8] >> (7 - i % 8)) & 1
            if bit:
                pulses.append((False, HALF_SYMBOL_US))
                pulses.append((True, HALF_SYMBOL_US))
            else:
                pulses.append((True, HALF_SYMBOL_US))
                pulses.append((False, HALF_SYMBOL_US))

        pulses.append((False, INTERFRAME_GAP_US))

    return pulses


def parse_remote_id(value: str | int) -> int:
    """Parse a remote id given as int, decimal string or 0x-prefixed hex."""
    if isinstance(value, int):
        remote_id = value
    else:
        text = value.strip().lower()
        remote_id = int(text, 16) if text.startswith("0x") else int(text, 10)
    if not 0 < remote_id <= MAX_REMOTE_ID:
        raise ValueError(f"remote id out of range: {remote_id}")
    return remote_id
