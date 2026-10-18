"""Tests for the RTS encoder.

The module is loaded straight from its file so these tests run without
Home Assistant installed.
"""

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).parent.parent / "custom_components" / "somfy_rts" / "rts.py"
_spec = importlib.util.spec_from_file_location("rts", _PATH)
rts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rts)


# Reference frames produced by the homebridge-somfy-rts-v2 encoder, so a
# remote migrated from Homebridge keeps working without re-pairing.
@pytest.mark.parametrize(
    ("button", "code", "remote_id", "expected"),
    [
        (rts.Button.UP, 131, 0x787E20, "a7878704245a22"),
        (rts.Button.DOWN, 393, 0x7C3C3C, "a7e5e46d516d11"),
        (rts.Button.MY, 1, 0x123456, "a7bdbdbceadecc"),
        (rts.Button.PROG, 65535, 0xABCDEF, "a723dc23cc01aa"),
    ],
)
def test_build_frame_matches_reference(button, code, remote_id, expected):
    assert rts.build_frame(button, code, remote_id).hex() == expected


def test_checksum_is_zero_after_deobfuscation():
    frame = bytearray(rts.build_frame(rts.Button.UP, 42, 0x112233))
    for i in range(len(frame) - 1, 0, -1):
        frame[i] ^= frame[i - 1]
    checksum = 0
    for byte in frame:
        checksum ^= byte ^ (byte >> 4)
    assert checksum & 0x0F == 0


@pytest.mark.parametrize("code", [-1, 0x10000])
def test_build_frame_rejects_bad_rolling_code(code):
    with pytest.raises(ValueError):
        rts.build_frame(rts.Button.UP, code, 0x123456)


@pytest.mark.parametrize("remote_id", [0, 0x1000000])
def test_build_frame_rejects_bad_remote_id(remote_id):
    with pytest.raises(ValueError):
        rts.build_frame(rts.Button.UP, 1, remote_id)


def test_build_pulses_structure():
    frame = rts.build_frame(rts.Button.UP, 1, 0x123456)
    pulses = rts.build_pulses(frame, 2)

    # wakeup (2) + first frame (2*2 hw sync + 2 sw sync + 112 data + 1 gap)
    # + repeat frame (7*2 hw sync + 2 sw sync + 112 data + 1 gap)
    assert len(pulses) == 2 + (4 + 2 + 112 + 1) + (14 + 2 + 112 + 1)
    assert pulses[0] == (True, rts.WAKEUP_HIGH_US)
    assert pulses[-1] == (False, rts.INTERFRAME_GAP_US)


def test_build_pulses_manchester_first_bit():
    # 0xA7 starts with a 1 bit: low then high.
    frame = rts.build_frame(rts.Button.UP, 1, 0x123456)
    pulses = rts.build_pulses(frame, 1)
    data_start = 2 + 4 + 2
    assert pulses[data_start] == (False, rts.HALF_SYMBOL_US)
    assert pulses[data_start + 1] == (True, rts.HALF_SYMBOL_US)


def test_build_pulses_rejects_zero_repetitions():
    with pytest.raises(ValueError):
        rts.build_pulses(b"\x00" * 7, 0)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0x787E20", 0x787E20), ("7896608", 7896608), (12345, 12345), (" 0xabcdef ", 0xABCDEF)],
)
def test_parse_remote_id(value, expected):
    assert rts.parse_remote_id(value) == expected


@pytest.mark.parametrize("value", ["0", "0x1000000", "nope"])
def test_parse_remote_id_rejects(value):
    with pytest.raises(ValueError):
        rts.parse_remote_id(value)
