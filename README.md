# Somfy RTS (pigpio) for Home Assistant

Control Somfy RTS shutters, blinds and awnings from Home Assistant with a cheap
433.42 MHz transmitter wired to a Raspberry Pi GPIO pin. No bridge, no cloud.

The integration talks to the [pigpio](https://abyz.me.uk/rpi/pigpio/) daemon
over TCP and uses its DMA waveforms for exact pulse timing, so Home Assistant
itself needs no hardware access. It works on Home Assistant OS, in Docker and
on Core.

## Features

- One virtual RTS remote per shutter, each with its own id and rolling code
- A cover entity per remote: open (Up), close (Down) and stop (My)
- **My position** and **Prog (pairing)** buttons
- A diagnostic sensor with the next rolling code
- Rolling codes are saved before every transmission, so a crash never makes a
  remote reuse a code
- Import remotes from another controller (for example a Homebridge plugin)
  without re-pairing the motors

RTS is one-way: the motors never report back. The cover state is whatever
Home Assistant last sent.

## Hardware

- A Raspberry Pi with a 433 MHz transmitter module, data pin on a free GPIO
  (GPIO 4 by default), powered from 3.3 V or 5 V.
- Somfy uses **433.42 MHz**, not the common 433.92 MHz. Swap the module's
  crystal for a 433.42 MHz one, or expect very short range.
- A 17.3 cm wire antenna on the module helps a lot.

## Install pigpiod

pigpiod must run on the Pi that has the transmitter.

**Raspberry Pi OS (Home Assistant in Docker or Core):**

```bash
sudo apt install pigpio
sudo systemctl enable --now pigpiod
```

By default pigpiod listens on all interfaces. To allow only local
connections, add `-l` to its start options, for example with
`sudo systemctl edit pigpiod`.

Only one program can drive the GPIO through pigpio at a time. Stop anything
else that uses the pigpio C library directly (for example a Homebridge plugin)
before starting pigpiod.

**Home Assistant OS:** install a pigpio add-on from the community add-on
repositories and start it.

## Install the integration

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=grohj&repository=Home-Assistant-Somfy-RTS&category=integration)

**HACS:** use the button above, or add
`https://github.com/grohj/Home-Assistant-Somfy-RTS` as a custom repository
(⋮ → *Custom repositories*, type *Integration*). Download
**Somfy RTS (pigpio)** and restart Home Assistant.

**Manual:** copy `custom_components/somfy_rts` into your Home Assistant
`config/custom_components/` folder and restart.

## Set up

1. **Settings → Devices & services → Add integration → Somfy RTS (pigpio).**
   Enter the pigpiod host (`localhost` when Home Assistant runs on the same
   Pi), port (`8888`) and the transmitter GPIO.
2. On the integration, choose **Add remote** for every shutter.

### Pair a new shutter

1. Add a remote and keep the suggested id and rolling code.
2. On the shutter's existing Somfy remote, hold **PROG** for about 2 seconds
   until the shutter jogs up and down.
3. Within a few seconds press the new remote's **Prog (pairing)** button in
   Home Assistant. The shutter jogs again: it is paired.

### Import an existing remote

To keep using a virtual remote from another controller, enter its id and its
**next** rolling code when adding the remote. Stop the old controller first
and never run both: each keeps its own counter and the motor ignores codes it
has already seen.

From **homebridge-somfy-rts-v2** (or similar Pi-Somfy based plugins): the id
is the `id` in the plugin config, and the next rolling code is the number in
`somfy_rts_<id>.txt` in the Homebridge storage folder.

## Notes

- **Frame repetitions:** more repetitions improve range but make every press
  slightly longer. 1 to 3 is typical.
- **Stop uses My.** On a moving motor, My stops it. On a motor at rest, My
  moves it to its stored favourite position.
- The remote id and rolling code cannot be edited after creation, because
  changing them would unpair the motor.

## Credits

The RTS protocol was documented by
[pushstack](https://pushstack.wordpress.com/somfy-rts-protocol/). Pulse
timings follow the well-tested [Pi-Somfy](https://github.com/Nickduino/Pi-Somfy)
and [Somfy_Remote](https://github.com/Nickduino/Somfy_Remote) projects by
Nickduino.

## License

MIT
