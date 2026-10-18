"""Send RTS waveforms through a pigpio daemon."""

from __future__ import annotations

import logging
import threading
import time

import pigpio

_LOGGER = logging.getLogger(__name__)

# pigpio merges generic pulses from time 0, so long waveforms are added in
# chunks, each prefixed with a delay pulse that moves it after the previous one.
_CHUNK_SIZE = 200
_TX_POLL_S = 0.01


class TransmitterError(Exception):
    """Raised when pigpiod cannot be reached or refuses a waveform."""


class PigpioTransmitter:
    """A 433.42 MHz transmitter on one GPIO pin, driven by pigpiod.

    All methods block and must run in an executor thread.
    """

    def __init__(self, host: str, port: int, gpio: int) -> None:
        self._host = host
        self._port = port
        self._gpio = gpio
        self._mask = 1 << gpio
        self._pi: pigpio.pi | None = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        """Connect to pigpiod and configure the pin as a low output."""
        with self._lock:
            self._connect_locked()

    def close(self) -> None:
        """Disconnect from pigpiod."""
        with self._lock:
            if self._pi is not None:
                self._pi.stop()
                self._pi = None

    def send(self, pulses: list[tuple[bool, int]]) -> None:
        """Transmit a waveform of (level, duration_us) pairs and wait for it."""
        with self._lock:
            try:
                self._send_locked(pulses)
            except (OSError, pigpio.error) as err:
                # Drop the connection so the next press reconnects.
                if self._pi is not None:
                    self._pi.stop()
                    self._pi = None
                raise TransmitterError(str(err)) from err

    def _connect_locked(self) -> pigpio.pi:
        if self._pi is not None and self._pi.connected:
            return self._pi
        pi = pigpio.pi(self._host, self._port, show_errors=False)
        if not pi.connected:
            raise TransmitterError(
                f"cannot connect to pigpiod at {self._host}:{self._port}"
            )
        pi.set_mode(self._gpio, pigpio.OUTPUT)
        pi.write(self._gpio, 0)
        self._pi = pi
        return pi

    def _send_locked(self, pulses: list[tuple[bool, int]]) -> None:
        pi = self._connect_locked()
        pi.wave_clear()

        offset = 0
        for start in range(0, len(pulses), _CHUNK_SIZE):
            chunk = []
            if offset:
                chunk.append(pigpio.pulse(0, 0, offset))
            for level, duration in pulses[start : start + _CHUNK_SIZE]:
                if level:
                    chunk.append(pigpio.pulse(self._mask, 0, duration))
                else:
                    chunk.append(pigpio.pulse(0, self._mask, duration))
                offset += duration
            pi.wave_add_generic(chunk)

        wave_id = pi.wave_create()
        if wave_id < 0:
            raise TransmitterError(f"pigpiod could not create waveform ({wave_id})")
        try:
            pi.wave_send_once(wave_id)
            while pi.wave_tx_busy():
                time.sleep(_TX_POLL_S)
        finally:
            pi.wave_delete(wave_id)
            pi.write(self._gpio, 0)
        _LOGGER.debug("Sent %d pulses on GPIO %d", len(pulses), self._gpio)
