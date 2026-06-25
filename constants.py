DEFAULT_INSTRUMENTS = [
    {"instId": "BTC-USDT-SWAP", "instType": "SWAP"},
    {"instId": "SOL-USDT-SWAP", "instType": "SWAP"},
]
DEFAULT_INST_IDS = [instrument["instId"] for instrument in DEFAULT_INSTRUMENTS]

INSTRUMENT_TYPES = ["SPOT", "SWAP", "FUTURES", "OPTION"]
MAX_INSTRUMENTS = 4
GRID_COLUMNS = 2

UI_POLL_INTERVAL_MS = 80
HTTP_FALLBACK_INTERVAL_SECONDS = 1.0
API_TICKERS_URL = "https://www.okx.com/api/v5/market/tickers"
API_INSTRUMENTS_URL = "https://www.okx.com/api/v5/public/instruments"
WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
WS_RECONNECT_DELAY_SECONDS = 1.5
WS_HEARTBEAT_IDLE_SECONDS = 20
WS_ACTIVE_GRACE_SECONDS = 3

DOUBLE_CLICK_MAX_SECONDS = 0.45
DOUBLE_CLICK_MAX_PIXELS = 8

COLOR_BG = "#0b0f14"
COLOR_PANEL = "#111821"
COLOR_PANEL_ALT = "#151f2a"
COLOR_BORDER = "#263241"
COLOR_TRANSPARENT = "#010101"
COLOR_FG_DEFAULT = "#e7edf4"
COLOR_FG_MUTED = "#8b98a7"
COLOR_FG_UP = "#18d47b"
COLOR_FG_DOWN = "#ff5f6d"
COLOR_FG_ERROR = "#ff8a65"
COLOR_ACCENT = "#2d8cff"

SETTINGS_DEFAULTS = {
    "instruments": DEFAULT_INSTRUMENTS,
    "alpha": 1.0,
    "bg": COLOR_BG,
    "panel": COLOR_PANEL,
    "panel_alt": COLOR_PANEL_ALT,
    "border": COLOR_BORDER,
    "fg_default": COLOR_FG_DEFAULT,
    "fg_muted": COLOR_FG_MUTED,
    "fg_up": COLOR_FG_UP,
    "fg_down": COLOR_FG_DOWN,
    "fg_error": COLOR_FG_ERROR,
    "accent": COLOR_ACCENT,
}
