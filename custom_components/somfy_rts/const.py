"""Constants for the Somfy RTS (pigpio) integration."""

DOMAIN = "somfy_rts"

CONF_GPIO = "gpio"

SUBENTRY_REMOTE = "remote"
CONF_REMOTE_ID = "remote_id"
CONF_ROLLING_CODE = "rolling_code"
CONF_REPETITIONS = "repetitions"
CONF_DEVICE_CLASS = "device_class"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8888
DEFAULT_GPIO = 4
DEFAULT_ROLLING_CODE = 1
DEFAULT_REPETITIONS = 2
DEFAULT_DEVICE_CLASS = "shutter"

MAX_REPETITIONS = 10

STORAGE_VERSION = 1
