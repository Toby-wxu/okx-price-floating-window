import json
import threading
import time

try:
    import websocket
except ImportError:
    websocket = None

from constants import (
    HTTP_FALLBACK_INTERVAL_SECONDS,
    WS_ACTIVE_GRACE_SECONDS,
    WS_HEARTBEAT_IDLE_SECONDS,
    WS_RECONNECT_DELAY_SECONDS,
    WS_URL,
)
from okx_client import fetch_tickers, ticker_to_change_pct, ticker_to_price
from settings import ensure_instruments


class PriceStream:
    """后台行情源：优先 WebSocket，同时保留 REST 兜底。"""

    def __init__(self, instruments, events):
        self.instruments = ensure_instruments(instruments)
        self.inst_ids = [instrument["instId"] for instrument in self.instruments]
        self.events = events
        self._stop_event = threading.Event()
        self._ws_thread = None
        self._http_thread = None
        self._ws_app = None
        self._last_message_at = 0
        self._last_ws_price_at = 0

    def start(self):
        self._http_thread = threading.Thread(
            target=self._run_http_fallback,
            args=("REST",),
            daemon=True,
        )
        self._http_thread.start()
        if websocket is not None:
            self._ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
            self._ws_thread.start()
        else:
            self.events.put({"type": "status", "state": "fallback", "text": "REST"})

    def stop(self):
        self._stop_event.set()
        if self._ws_app is not None:
            self._ws_app.close()

    def _run_websocket(self):
        while not self._stop_event.is_set():
            self._connect_websocket()
            if not self._stop_event.wait(WS_RECONNECT_DELAY_SECONDS):
                self.events.put({"type": "status", "state": "connecting", "text": "重连"})

    def _connect_websocket(self):
        def on_open(ws):
            self._last_message_at = time.monotonic()
            args = [
                {"channel": "tickers", "instId": inst_id}
                for inst_id in self.inst_ids
            ]
            ws.send(json.dumps({"op": "subscribe", "args": args}))
            self.events.put({"type": "status", "state": "connected", "text": "WS"})
            threading.Thread(target=self._heartbeat, args=(ws,), daemon=True).start()

        def on_message(_ws, message):
            self._last_message_at = time.monotonic()
            if message == "pong":
                return
            try:
                payload = json.loads(message)
            except ValueError:
                return

            if payload.get("event") == "error":
                self.events.put(
                    {
                        "type": "status",
                        "state": "error",
                        "text": payload.get("msg") or "订阅失败",
                    }
                )
                return

            for ticker in payload.get("data") or []:
                inst_id = ticker.get("instId")
                if inst_id not in self.inst_ids:
                    continue
                price = ticker_to_price(ticker)
                if price is None:
                    continue
                self.events.put(
                    {
                        "type": "price",
                        "source": "WS",
                        "inst_id": inst_id,
                        "price": price,
                        "change_pct": ticker_to_change_pct(ticker),
                    }
                )
                self._last_ws_price_at = time.monotonic()

        def on_error(_ws, _error):
            self.events.put({"type": "status", "state": "error", "text": "断线"})

        def on_close(_ws, _status_code, _message):
            self.events.put({"type": "status", "state": "connecting", "text": "重连"})

        self._ws_app = websocket.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        try:
            self._ws_app.run_forever(ping_interval=0)
        finally:
            self._ws_app = None

    def _heartbeat(self, ws):
        while not self._stop_event.is_set():
            if time.monotonic() - self._last_message_at >= WS_HEARTBEAT_IDLE_SECONDS:
                try:
                    ws.send("ping")
                except Exception:
                    return
            time.sleep(5)

    def _run_http_fallback(self, label):
        while not self._stop_event.is_set():
            if time.monotonic() - self._last_ws_price_at < WS_ACTIVE_GRACE_SECONDS:
                self._stop_event.wait(0.5)
                continue

            tickers = fetch_tickers(self.instruments)
            if tickers:
                for inst_id, ticker in tickers.items():
                    self.events.put(
                        {
                            "type": "price",
                            "source": label,
                            "inst_id": inst_id,
                            "price": ticker["price"],
                            "change_pct": ticker.get("change_pct"),
                        }
                    )
                self.events.put({"type": "status", "state": "fallback", "text": label})
            else:
                self.events.put({"type": "status", "state": "error", "text": "获取失败"})
            self._stop_event.wait(HTTP_FALLBACK_INTERVAL_SECONDS)
