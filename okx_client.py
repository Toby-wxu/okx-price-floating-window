import requests

from constants import API_INSTRUMENTS_URL, API_TICKERS_URL, INSTRUMENT_TYPES
from settings import ensure_instruments


def ticker_to_price(ticker):
    last = ticker.get("last")
    if last is None or last == "":
        return None
    try:
        return float(last)
    except (TypeError, ValueError):
        return None


def ticker_to_change_pct(ticker):
    price = ticker_to_price(ticker)
    open24h = ticker.get("open24h")
    if price is None or open24h in (None, ""):
        return None
    try:
        open_price = float(open24h)
    except (TypeError, ValueError):
        return None
    if open_price == 0:
        return None
    return (price - open_price) / open_price * 100


def fetch_tickers(instruments):
    instrument_list = ensure_instruments(instruments)
    types_by_inst_id = {
        instrument["instId"]: instrument["instType"]
        for instrument in instrument_list
    }
    target_ids = set(types_by_inst_id)
    tickers = {}

    for inst_type in sorted(set(types_by_inst_id.values())):
        try:
            response = requests.get(
                API_TICKERS_URL,
                params={"instType": inst_type},
                timeout=(5, 10),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError):
            continue

        if data.get("code") != "0":
            continue

        for ticker in data.get("data") or []:
            inst_id = ticker.get("instId")
            if inst_id not in target_ids:
                continue
            price = ticker_to_price(ticker)
            if price is None:
                continue
            tickers[inst_id] = {
                "price": price,
                "change_pct": ticker_to_change_pct(ticker),
            }
    return tickers


def search_instruments(query, limit=10):
    query = (query or "").strip().upper()
    if not query:
        return []

    matches = []
    seen = set()
    for inst_type in INSTRUMENT_TYPES:
        try:
            response = requests.get(
                API_INSTRUMENTS_URL,
                params={"instType": inst_type},
                timeout=(3, 6),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError):
            continue

        if data.get("code") != "0":
            continue

        for item in data.get("data") or []:
            inst_id = str(item.get("instId") or "").upper()
            if not inst_id or inst_id in seen:
                continue
            haystack = " ".join(
                str(item.get(key) or "").upper()
                for key in ("instId", "baseCcy", "quoteCcy", "instFamily", "uly")
            )
            if query not in haystack:
                continue
            matches.append({"instId": inst_id, "instType": inst_type})
            seen.add(inst_id)

    matches.sort(
        key=lambda item: (
            0 if item["instId"].startswith(query) else 1,
            INSTRUMENT_TYPES.index(item["instType"]),
            item["instId"],
        )
    )
    return matches[:limit]
