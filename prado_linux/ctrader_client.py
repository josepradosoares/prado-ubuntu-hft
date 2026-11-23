"""cTrader Open API Client (JSON over WebSocket port 5036 + OAuth 2.0 + RateLimit Manager).

Follows Spotware cTrader Open API official specification:
- Demo WS : wss://demo.ctraderapi.com:5036
- Live WS : wss://live.ctraderapi.com:5036
- OAuth2  : https://openapi.ctrader.com/apps (Client ID / Secret)
            https://id.ctrader.com/my/settings/openapi/grantingaccess/
            https://openapi.ctrader.com/apps/token
- RateLimits: 50 req/s (realtime/orders/account), 5 req/s (historical)
"""
from __future__ import annotations

from collections import deque
import json
import random
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request

from prado_linux.flow_math import TICK_FLAG_BUY, TICK_FLAG_SELL, TickRecord

CTRADER_DEMO_WS_URL = "wss://demo.ctraderapi.com:5036"
CTRADER_LIVE_WS_URL = "wss://live.ctraderapi.com:5036"
CTRADER_PORTAL_APPS_URL = "https://openapi.ctrader.com/apps"
CTRADER_OAUTH_AUTH_URL = "https://id.ctrader.com/my/settings/openapi/grantingaccess/"
CTRADER_OAUTH_TOKEN_URL = "https://openapi.ctrader.com/apps/token"

PRICE_SCALE = 100_000.0
DEFAULT_LOT_SIZE_CENTS = 10_000_000  # 100,000 units * 100 centicents

# Official ProtoPayloadType / ProtoOAPayloadType enum IDs
PT_ERROR_RES = 50
PT_HEARTBEAT_EVENT = 51

PT_APPLICATION_AUTH_REQ = 2100
PT_APPLICATION_AUTH_RES = 2101
PT_ACCOUNT_AUTH_REQ = 2102
PT_ACCOUNT_AUTH_RES = 2103
PT_NEW_ORDER_REQ = 2106
PT_AMEND_POSITION_SLTP_REQ = 2110
PT_CLOSE_POSITION_REQ = 2111
PT_ASSET_LIST_REQ = 2112
PT_ASSET_LIST_RES = 2113
PT_SYMBOLS_LIST_REQ = 2114
PT_SYMBOLS_LIST_RES = 2115
PT_SYMBOL_BY_ID_REQ = 2116
PT_SYMBOL_BY_ID_RES = 2117
PT_TRADER_REQ = 2121
PT_TRADER_RES = 2122
PT_TRADER_UPDATE_EVENT = 2123
PT_RECONCILE_REQ = 2124
PT_RECONCILE_RES = 2125
PT_EXECUTION_EVENT = 2126
PT_SUBSCRIBE_SPOTS_REQ = 2127
PT_SUBSCRIBE_SPOTS_RES = 2128
PT_UNSUBSCRIBE_SPOTS_REQ = 2129
PT_UNSUBSCRIBE_SPOTS_RES = 2130
PT_SPOT_EVENT = 2131
PT_ORDER_ERROR_EVENT = 2132
PT_DEAL_LIST_REQ = 2133
PT_DEAL_LIST_RES = 2134
PT_GET_TRENDBARS_REQ = 2137
PT_GET_TRENDBARS_RES = 2138
PT_OA_ERROR_RES = 2142
PT_GET_TICKDATA_REQ = 2145
PT_GET_TICKDATA_RES = 2146
PT_ACCOUNTS_TOKEN_INVALIDATED_EVENT = 2147
PT_CLIENT_DISCONNECT_EVENT = 2148
PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ = 2149
PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_RES = 2150
PT_REFRESH_TOKEN_REQ = 2173
PT_REFRESH_TOKEN_RES = 2174
PT_GET_POSITION_UNREALIZED_PNL_REQ = 2187
PT_GET_POSITION_UNREALIZED_PNL_RES = 2188

ORDER_TYPE_MARKET = 1
TRADE_SIDE_BUY = 1
TRADE_SIDE_SELL = 2

EXECUTION_ORDER_ACCEPTED = 2
EXECUTION_ORDER_FILLED = 3
EXECUTION_ORDER_REJECTED = 7
EXECUTION_ORDER_PARTIAL_FILL = 11

POSITION_STATUS_OPEN = 1
POSITION_STATUS_CLOSED = 2

QUOTE_TYPE_BID = 1
QUOTE_TYPE_ASK = 2

TRENDBAR_PERIOD_BY_GRANULARITY: dict[int, int] = {
    60: 1,       # M1
    300: 5,      # M5
    900: 7,      # M15
    1800: 8,     # M30
    3600: 9,     # H1
    14400: 10,   # H4
    86400: 12,   # D1
    2592000: 14, # MN1
}

HISTORICAL_PAYLOAD_TYPES = frozenset({
    PT_GET_TRENDBARS_REQ,
    PT_GET_TICKDATA_REQ,
    PT_DEAL_LIST_REQ,
})

REALTIME_PER_SEC_BUDGET = 50
HISTORICAL_PER_SEC_BUDGET = 5


def mask_secret(value: str, prefix_len: int = 4, suffix_len: int = 4) -> str:
    s = (value or "").strip()
    if not s:
        return "--"
    if len(s) <= prefix_len + suffix_len:
        return "*" * len(s)
    return f"{s[:prefix_len]}****{s[-suffix_len:]}"


def scale_money(raw_val: Any, money_digits: int = 2) -> float:
    try:
        val = float(raw_val or 0.0)
        digits = max(0, int(money_digits if money_digits is not None else 2))
        return round(val / (10 ** digits), 2)
    except (TypeError, ValueError):
        return 0.0


def decode_price(raw_int: Any, digits: int = 5) -> float:
    try:
        val = float(raw_int or 0.0) / PRICE_SCALE
        return round(val, max(0, min(8, int(digits))))
    except (TypeError, ValueError):
        return 0.0


def encode_relative_distance(price_dist: float) -> int:
    try:
        val = abs(float(price_dist or 0.0))
        if val <= 0.0:
            return 0
        return max(1, int(round(val * PRICE_SCALE)))
    except (TypeError, ValueError):
        return 0


def lots_to_protocol_volume(lots: float, symbol_meta: dict[str, Any] | None = None) -> int:
    meta = symbol_meta or {}
    lot_size_cents = int(meta.get("lotSize") or DEFAULT_LOT_SIZE_CENTS)
    if lot_size_cents <= 0:
        lot_size_cents = DEFAULT_LOT_SIZE_CENTS
    raw = int(round(max(0.0001, float(lots)) * lot_size_cents))
    min_vol = int(meta.get("minVolume") or 0)
    max_vol = int(meta.get("maxVolume") or 0)
    step_vol = int(meta.get("stepVolume") or 0)
    if step_vol > 0:
        raw = max(step_vol, int(round(raw / step_vol)) * step_vol)
    if min_vol > 0:
        raw = max(min_vol, raw)
    if max_vol > 0:
        raw = min(max_vol, raw)
    return max(1, raw)


def protocol_volume_to_lots(protocol_vol: Any, symbol_meta: dict[str, Any] | None = None) -> float:
    meta = symbol_meta or {}
    lot_size_cents = int(meta.get("lotSize") or DEFAULT_LOT_SIZE_CENTS)
    if lot_size_cents <= 0:
        lot_size_cents = DEFAULT_LOT_SIZE_CENTS
    try:
        return round(float(protocol_vol or 0) / float(lot_size_cents), 4)
    except (TypeError, ValueError):
        return 0.0


def build_oauth_authorize_url(
    client_id: str,
    redirect_uri: str,
    scope: str = "trading",
    product: str = "web",
) -> str:
    params = urllib.parse.urlencode(
        {
            "client_id": client_id.strip(),
            "redirect_uri": redirect_uri.strip(),
            "scope": scope.strip() or "trading",
            "product": product.strip() or "web",
        }
    )
    return f"{CTRADER_OAUTH_AUTH_URL}?{params}"


def _http_get_json(
    url: str,
    http_transport: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if http_transport is not None:
        return http_transport(url)
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "Prado-Ubuntu-HFT/2.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"cTrader OAuth HTTP {exc.code}: {body[:240]}")


def exchange_oauth_code(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    http_transport: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code.strip(),
            "redirect_uri": redirect_uri.strip(),
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
        }
    )
    data = _http_get_json(f"{CTRADER_OAUTH_TOKEN_URL}?{params}", http_transport=http_transport)
    if data.get("errorCode") or data.get("error"):
        raise CTraderAuthError(
            "TOKEN_INVALID",
            f"Erro OAuth cTrader: {data.get('description') or data.get('error_description') or data.get('errorCode') or data.get('error')}",
        )
    if not data.get("accessToken") and not data.get("access_token"):
        raise CTraderAuthError("TOKEN_INVALID", f"Resposta OAuth cTrader sem accessToken: {data}")
    return {
        "access_token": str(data.get("accessToken") or data.get("access_token") or ""),
        "refresh_token": str(data.get("refreshToken") or data.get("refresh_token") or ""),
        "expires_in": int(data.get("expiresIn") or data.get("expires_in") or 2592000),
        "token_type": str(data.get("tokenType") or data.get("token_type") or "bearer"),
    }


def refresh_oauth_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    http_transport: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token.strip(),
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
        }
    )
    data = _http_get_json(f"{CTRADER_OAUTH_TOKEN_URL}?{params}", http_transport=http_transport)
    if data.get("errorCode") or data.get("error"):
        raise CTraderAuthError(
            "TOKEN_EXPIRED",
            f"Falha ao renovar token cTrader: {data.get('description') or data.get('errorCode') or data.get('error')}",
        )
    return {
        "access_token": str(data.get("accessToken") or data.get("access_token") or ""),
        "refresh_token": str(data.get("refreshToken") or data.get("refresh_token") or refresh_token),
        "expires_in": int(data.get("expiresIn") or data.get("expires_in") or 2592000),
    }


def classify_payload_group(payload_type: int) -> str:
    if payload_type == PT_HEARTBEAT_EVENT:
        return "heartbeat"
    if payload_type in HISTORICAL_PAYLOAD_TYPES:
        return "historical"
    return "realtime"


class CTraderAuthError(RuntimeError):
    """Structured authentication error carrying a canonical auth_state."""

    def __init__(self, auth_state: str, message: str) -> None:
        super().__init__(message)
        self.auth_state = auth_state


class CTraderRateLimitError(RuntimeError):
    """Raised when local or remote cTrader RateLimit blocks a request."""


class CTraderRateLimiter:
    """Thread-safe 1-second sliding-window rate limiter (50 req/s realtime, 5 req/s historical)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._windows: dict[str, deque[float]] = {
            "realtime": deque(),
            "historical": deque(),
        }
        self._blocked_until: dict[str, float] = {}
        self._global_blocked_until: float = 0.0
        self._consecutive_blocks: dict[str, int] = {}
        self._last_error: str = ""

    def _prune(self, dq: deque[float], now: float) -> None:
        cutoff = now - 1.0
        while dq and dq[0] < cutoff:
            dq.popleft()

    def acquire(self, group: str, now: float | None = None) -> None:
        if group == "heartbeat":
            return
        grp = "historical" if group == "historical" else "realtime"
        t = time.time() if now is None else now
        with self._lock:
            until = max(self._global_blocked_until, self._blocked_until.get(grp, 0.0))
            if t < until:
                wait = round(until - t, 2)
                raise CTraderRateLimitError(
                    f"RateLimit cTrader ativo ({grp}, cooldown {wait}s): {self._last_error or 'aguardando janela'}"
                )
            dq = self._windows.setdefault(grp, deque())
            self._prune(dq, t)
            limit = HISTORICAL_PER_SEC_BUDGET if grp == "historical" else REALTIME_PER_SEC_BUDGET
            if len(dq) >= limit:
                self._blocked_until[grp] = t + 0.5
                msg = f"Orçamento cTrader '{grp}' atingido ({len(dq)}/{limit} req/s)"
                self._last_error = msg
                raise CTraderRateLimitError(msg)
            dq.append(t)

    def record_remote_rate_limit(
        self,
        message: str = "",
        retry_after: float | None = None,
        group: str = "realtime",
        now: float | None = None,
    ) -> float:
        t = time.time() if now is None else now
        grp = "historical" if group == "historical" else "realtime"
        with self._lock:
            streak = self._consecutive_blocks.get(grp, 0) + 1
            self._consecutive_blocks[grp] = streak
            if retry_after and retry_after > 0:
                delay = min(60.0, float(retry_after))
            else:
                delay = min(30.0, 1.5 * (2 ** min(streak - 1, 4))) + random.uniform(0.05, 0.35)
            self._blocked_until[grp] = max(self._blocked_until.get(grp, 0.0), t + delay)
            self._last_error = message or "cTrader Open API RateLimit"
            return delay

    def record_success(self, group: str = "realtime") -> None:
        grp = "historical" if group == "historical" else "realtime"
        with self._lock:
            self._consecutive_blocks.pop(grp, None)
            if not self._consecutive_blocks:
                self._last_error = ""

    def status(self, now: float | None = None) -> dict[str, Any]:
        t = time.time() if now is None else now
        with self._lock:
            self._prune(self._windows["realtime"], t)
            self._prune(self._windows["historical"], t)
            rt_rem = max(0.0, self._blocked_until.get("realtime", 0.0) - t)
            hist_rem = max(0.0, self._blocked_until.get("historical", 0.0) - t)
            glob_rem = max(0.0, self._global_blocked_until - t)
            max_rem = max(glob_rem, rt_rem, hist_rem)
            return {
                "state": "BLOCKED" if max(glob_rem, rt_rem) > 0.0 else "NORMAL",
                "cooldown_seconds": round(max_rem, 2),
                "ws_per_sec": len(self._windows["realtime"]),
                "historical_per_sec": len(self._windows["historical"]),
                "last_error": self._last_error,
            }


def _normalize_trade_side(raw_side: Any) -> str:
    if raw_side in (TRADE_SIDE_BUY, "BUY", "1", 1):
        return "BUY"
    if raw_side in (TRADE_SIDE_SELL, "SELL", "2", 2):
        return "SELL"
    s = str(raw_side or "").upper()
    return "SELL" if "SELL" in s else "BUY"


def _normalize_position_status(raw_status: Any) -> int:
    if isinstance(raw_status, int):
        return raw_status
    s = str(raw_status or "").upper()
    if "CLOSED" in s or s == "2":
        return POSITION_STATUS_CLOSED
    return POSITION_STATUS_OPEN


def _normalize_execution_type(raw_exec: Any) -> int:
    if isinstance(raw_exec, int):
        return raw_exec
    s = str(raw_exec or "").upper()
    if "FILLED" in s:
        return EXECUTION_ORDER_FILLED
    if "PARTIAL" in s:
        return EXECUTION_ORDER_PARTIAL_FILL
    if "REJECTED" in s:
        return EXECUTION_ORDER_REJECTED
    if "ACCEPTED" in s:
        return EXECUTION_ORDER_ACCEPTED
    return 0


class CTraderClient:
    """Thread-safe cTrader Open API JSON WebSocket client (port 5036)."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: str,
        refresh_token: str = "",
        account_id: str | int = "",
        is_live: bool = False,
        preferred_account_type: str = "DEMO",
        rpc_transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        http_transport: Callable[[str], dict[str, Any]] | None = None,
        rate_limiter: CTraderRateLimiter | None = None,
    ) -> None:
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self.access_token = (access_token or "").strip()
        self.refresh_token = (refresh_token or "").strip()
        self._selected_account_id = str(account_id).strip() if account_id not in (None, "") else ""
        self.is_live = bool(is_live)
        self.preferred_account_type = (preferred_account_type or "DEMO").upper()
        self._rpc_transport = rpc_transport
        self._http_transport = http_transport
        self.rate_limiter = rate_limiter or CTraderRateLimiter()

        self._lock = threading.RLock()
        self._send_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending_rpcs: dict[str, dict[str, Any]] = {}
        self._stream_lock = threading.RLock()

        self._symbols_by_name: dict[str, dict[str, Any]] = {}
        self._symbols_by_id: dict[int, dict[str, Any]] = {}
        self._symbol_details_cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._symbol_details_ttl: float = 300.0
        self._assets_by_id: dict[int, dict[str, Any]] = {}
        self._subscribed_symbol_ids: set[int] = set()
        self._live_ticks: dict[str, deque[TickRecord]] = {}
        self._last_spot_prices: dict[int, tuple[float, float]] = {}
        self._stream_positions: dict[str, dict[str, Any]] = {}
        self._recently_closed_deals: deque[dict[str, Any]] = deque(maxlen=200)
        self._stream_balance: tuple[float, float] | None = None
        self._authorized_info: dict[str, Any] = {}
        self._money_digits: int = 2

        self._reader_active: bool = False
        self._reader_dead: bool = False
        self._reader_stop = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._ws: Any = None
        self._ws_url_active: str = ""
        self._app_authed: bool = False
        self._account_authed: bool = False
        self._req_seq: int = 0
        self._last_activity_at: float = 0.0

        self.connection_state: str = "DISCONNECTED"
        self.auth_state: str = "UNAUTHENTICATED"
        self.last_error: str = ""
        self.last_order_lifecycle: dict[str, Any] = {}

    @property
    def ws_url(self) -> str:
        if self._ws_url_active:
            return self._ws_url_active
        return CTRADER_LIVE_WS_URL if self.is_live else CTRADER_DEMO_WS_URL

    def _next_msg_id(self) -> str:
        self._req_seq += 1
        return f"prado_{self._req_seq}"

    def _open_ws_url(self, url: str) -> Any:
        try:
            import websocket  # type: ignore

            return websocket.create_connection(
                url,
                header=["User-Agent: Prado-Ubuntu-HFT/2.0"],
                timeout=10,
            )
        except ModuleNotFoundError:
            from websockets.sync.client import connect as ws_sync_connect  # type: ignore

            cm = ws_sync_connect(
                url,
                additional_headers={"User-Agent": "Prado-Ubuntu-HFT/2.0"},
                open_timeout=10,
                close_timeout=5,
            )
            conn = cm.__enter__()

            class _WebsocketsSyncAdapter:
                def __init__(self, inner: Any, ctx: Any) -> None:
                    self._inner = inner
                    self._ctx = ctx
                    self.connected = True
                    self._timeout = 10.0

                def settimeout(self, timeout: float) -> None:
                    self._timeout = max(0.1, float(timeout))

                def send(self, data: str) -> None:
                    self._inner.send(data)

                def recv(self) -> str:
                    res = self._inner.recv(timeout=self._timeout)
                    return res.decode("utf-8") if isinstance(res, bytes) else str(res)

                def close(self) -> None:
                    self.connected = False
                    try:
                        self._ctx.__exit__(None, None, None)
                    except Exception:
                        try:
                            self._inner.close()
                        except Exception:
                            pass

            return _WebsocketsSyncAdapter(conn, cm)

    def _symbol_name_for_id(self, symbol_id: int) -> str:
        info = self._symbols_by_id.get(int(symbol_id))
        if info:
            return str(info.get("name") or f"SYM_{symbol_id}")
        return f"SYM_{symbol_id}"

    def _symbol_digits_for_id(self, symbol_id: int) -> int:
        det = self._symbol_details_cache.get(int(symbol_id))
        if det:
            return int(det[1].get("digits", 5))
        return 5

    def _format_position(
        self,
        pos: dict[str, Any],
        pnl_entry: dict[str, Any] | None = None,
        pnl_digits: int | None = None,
    ) -> dict[str, Any]:
        pid = str(pos.get("positionId") or "")
        td = pos.get("tradeData") or {}
        sym_id = int(td.get("symbolId") or 0)
        sym_name = self._symbol_name_for_id(sym_id)
        side = _normalize_trade_side(td.get("tradeSide"))
        det_entry = self._symbol_details_cache.get(sym_id)
        sym_meta = det_entry[1] if det_entry else None
        lots = protocol_volume_to_lots(td.get("volume", 0), sym_meta)
        price_open = float(pos.get("price") or 0.0)
        spot_pair = self._last_spot_prices.get(sym_id)
        if spot_pair:
            curr_price = spot_pair[0] if side == "BUY" else spot_pair[1]
        else:
            curr_price = price_open

        profit = 0.0
        if pnl_entry is not None:
            md = pnl_digits if pnl_digits is not None else int(pos.get("moneyDigits") or self._money_digits)
            raw_pnl = pnl_entry.get("netUnrealizedPnL", pnl_entry.get("grossUnrealizedPnL", 0))
            profit = scale_money(raw_pnl, md)
        elif pos.get("_cached_profit") is not None:
            profit = float(pos["_cached_profit"])

        label = str(td.get("label") or "")
        comment = str(td.get("comment") or label or "cTrader")
        return {
            "ticket": pid,
            "symbol": sym_name,
            "symbol_id": sym_id,
            "type": side,
            "side": side,
            "volume": lots,
            "volume_raw": int(td.get("volume") or 0),
            "price_open": round(price_open, 6),
            "price_current": round(curr_price, 6),
            "sl": round(float(pos.get("stopLoss") or 0.0), 6),
            "tp": round(float(pos.get("takeProfit") or 0.0), 6),
            "profit": round(profit, 2),
            "bot_name": label or comment,
            "comment": comment,
        }

    def _ingest_async_event(self, msg: dict[str, Any]) -> None:
        pt = int(msg.get("payloadType") or 0)
        payload = msg.get("payload") or {}
        if not isinstance(payload, dict):
            return
        self._last_activity_at = time.time()

        if pt == PT_SPOT_EVENT:
            sym_id = int(payload.get("symbolId") or 0)
            if sym_id <= 0:
                return
            digits = self._symbol_digits_for_id(sym_id)
            prev = self._last_spot_prices.get(sym_id, (0.0, 0.0))
            bid = decode_price(payload["bid"], digits) if payload.get("bid") is not None else prev[0]
            ask = decode_price(payload["ask"], digits) if payload.get("ask") is not None else prev[1]
            if bid <= 0.0 and ask > 0.0:
                bid = ask
            if ask <= 0.0 and bid > 0.0:
                ask = bid
            if bid <= 0.0 and ask <= 0.0:
                return
            mid = round(0.5 * (bid + ask), max(2, digits))
            prev_mid = 0.5 * (prev[0] + prev[1]) if prev[0] > 0 and prev[1] > 0 else mid
            flag = TICK_FLAG_BUY if mid >= prev_mid else TICK_FLAG_SELL
            ts_ms = int(payload.get("timestamp") or int(time.time() * 1000))
            sym_name = self._symbol_name_for_id(sym_id)
            tick = TickRecord(
                time_msc=ts_ms,
                bid=bid,
                ask=ask,
                last=mid,
                volume_real=0.0,
                tick_volume=1.0,
                flags=flag,
            )
            with self._stream_lock:
                self._last_spot_prices[sym_id] = (bid, ask)
                dq = self._live_ticks.setdefault(sym_name, deque(maxlen=600))
                dq.append(tick)
            return

        if pt == PT_EXECUTION_EVENT:
            pos = payload.get("position")
            deal = payload.get("deal")
            if isinstance(pos, dict):
                pid = str(pos.get("positionId") or "")
                status = _normalize_position_status(pos.get("positionStatus"))
                if pid:
                    with self._stream_lock:
                        if status == POSITION_STATUS_CLOSED:
                            self._stream_positions.pop(pid, None)
                        else:
                            self._stream_positions[pid] = pos
            if isinstance(deal, dict) and isinstance(deal.get("closePositionDetail"), dict):
                detail = deal["closePositionDetail"]
                md = int(detail.get("moneyDigits") or deal.get("moneyDigits") or self._money_digits)
                gross = scale_money(detail.get("grossProfit", 0), md)
                swap = scale_money(detail.get("swap", 0), md)
                comm = scale_money(detail.get("commission", 0), md)
                pnl = round(gross + swap + comm, 2)
                bal_after = detail.get("balance")
                sym_id = int(deal.get("symbolId") or 0)
                sym_meta = (self._symbol_details_cache.get(sym_id) or (0.0, {}))[1]
                closed_item = {
                    "ticket": str(deal.get("positionId") or deal.get("dealId") or ""),
                    "symbol": self._symbol_name_for_id(sym_id),
                    "side": _normalize_trade_side(deal.get("tradeSide")),
                    "volume": protocol_volume_to_lots(detail.get("closedVolume") or deal.get("filledVolume") or deal.get("volume"), sym_meta),
                    "price_open": float(detail.get("entryPrice") or 0.0),
                    "price_close": float(deal.get("executionPrice") or 0.0),
                    "profit": pnl,
                    "reason": "CTRADER_EXECUTION_CLOSE",
                    "bot_name": str(deal.get("label") or deal.get("comment") or "cTrader"),
                    "comment": str(deal.get("comment") or deal.get("label") or "cTrader"),
                }
                with self._stream_lock:
                    self._recently_closed_deals.append(closed_item)
                    if bal_after is not None:
                        bal_val = scale_money(bal_after, md)
                        self._authorized_info["balance"] = bal_val
                        self._stream_balance = (time.time(), bal_val)
            return

        if pt == PT_TRADER_UPDATE_EVENT:
            trader = payload.get("trader")
            if isinstance(trader, dict) and "balance" in trader:
                md = int(trader.get("moneyDigits") or self._money_digits)
                bal_val = scale_money(trader["balance"], md)
                with self._stream_lock:
                    self._money_digits = md
                    self._authorized_info["balance"] = bal_val
                    self._stream_balance = (time.time(), bal_val)
            return

        if pt == PT_ACCOUNTS_TOKEN_INVALIDATED_EVENT:
            self.auth_state = "TOKEN_EXPIRED"
            self.last_error = "Token cTrader invalidado pelo servidor."
            return

        if pt == PT_CLIENT_DISCONNECT_EVENT:
            self.connection_state = "DISCONNECTED"
            self.last_error = str(payload.get("reason") or "Conexão encerrada pelo servidor cTrader.")

    def _start_ws_reader(self, ws: Any) -> None:
        self._stop_ws_reader()
        if hasattr(ws, "settimeout"):
            try:
                ws.settimeout(1.0)
            except Exception:
                pass
        stop_event = threading.Event()
        self._reader_stop = stop_event
        self._reader_dead = False
        self._reader_active = True

        def _loop() -> None:
            try:
                while not stop_event.is_set() and getattr(ws, "connected", True):
                    try:
                        raw = ws.recv()
                    except TimeoutError:
                        continue
                    except Exception as exc:
                        if "timeout" in type(exc).__name__.lower():
                            continue
                        if not stop_event.is_set():
                            self.connection_state = "DISCONNECTED"
                            with self._pending_lock:
                                for entry in self._pending_rpcs.values():
                                    entry["error"] = exc
                                    entry["event"].set()
                        break

                    if not raw:
                        continue
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    if not isinstance(msg, dict):
                        continue

                    self._ingest_async_event(msg)
                    cid = msg.get("clientMsgId")
                    matched = False
                    if cid is not None:
                        with self._pending_lock:
                            entry = self._pending_rpcs.get(str(cid))
                            if entry is not None:
                                entry["response"] = msg
                                entry["event"].set()
                                matched = True
                    if not matched and int(msg.get("payloadType") or 0) in (PT_OA_ERROR_RES, PT_ERROR_RES):
                        err_payload = msg.get("payload") or {}
                        code = str(err_payload.get("errorCode", "ERR"))
                        desc = str(err_payload.get("description", code))
                        if "RATE" in code or "FREQUENCY" in code or "BLOCKED_PAYLOAD_TYPE" in code:
                            retry_after = float(err_payload.get("retryAfter") or 0.0)
                            self.rate_limiter.record_remote_rate_limit(desc, retry_after=retry_after)
                        elif "TOKEN" in code or "AUTH" in code:
                            self.auth_state = "TOKEN_EXPIRED" if "EXPIRE" in code else "TOKEN_INVALID"
            finally:
                if not stop_event.is_set():
                    self._reader_dead = True
                    self._reader_active = False

        t = threading.Thread(target=_loop, daemon=True)
        self._reader_thread = t
        t.start()

    def _stop_ws_reader(self) -> None:
        self._reader_stop.set()
        self._reader_active = False
        self._reader_dead = False
        with self._pending_lock:
            for entry in self._pending_rpcs.values():
                if entry.get("response") is None and entry.get("error") is None:
                    entry["error"] = ConnectionError("Conexão WebSocket cTrader fechada.")
                    entry["event"].set()
        t = self._reader_thread
        self._reader_thread = None
        if t is not None and t.is_alive() and threading.current_thread() is not t:
            t.join(timeout=0.5)

    def _send_via_reader(self, ws: Any, envelope: dict[str, Any], timeout: float = 12.0) -> dict[str, Any]:
        cid = str(envelope["clientMsgId"])
        ev = threading.Event()
        entry: dict[str, Any] = {"event": ev, "response": None, "error": None}
        with self._pending_lock:
            self._pending_rpcs[cid] = entry
        try:
            with self._send_lock:
                ws.send(json.dumps(envelope))
            if not ev.wait(timeout=timeout):
                raise TimeoutError("Tempo limite aguardando resposta WebSocket cTrader.")
            if entry["error"] is not None:
                raise entry["error"]
            resp = entry["response"]
            if not isinstance(resp, dict):
                raise RuntimeError("Resposta WebSocket cTrader inválida.")
            return resp
        finally:
            with self._pending_lock:
                self._pending_rpcs.pop(cid, None)

    def _handle_error_payload(self, err: dict[str, Any], group: str = "realtime") -> None:
        code = str(err.get("errorCode") or "ERR").upper()
        desc = str(err.get("description") or code)
        if "BLOCKED_PAYLOAD_TYPE" in code or "FREQUENCY" in code or "RATE" in code or "TOO_MANY" in code:
            retry_after = float(err.get("retryAfter") or 0.0)
            self.rate_limiter.record_remote_rate_limit(desc, retry_after=retry_after, group=group)
            raise CTraderRateLimitError(f"cTrader Open API ({code}): {desc}")
        if "CH_CLIENT_AUTH_FAILURE" in code or "INVALID_CLIENT" in code or "APPLICATION" in code:
            self.auth_state = "APP_CREDENTIALS_INVALID"
            raise CTraderAuthError("APP_CREDENTIALS_INVALID", f"cTrader App Auth ({code}): {desc}")
        if "TOKEN_EXPIRED" in code or "EXPIRED" in code:
            self.auth_state = "TOKEN_EXPIRED"
            raise CTraderAuthError("TOKEN_EXPIRED", f"cTrader Token Expirado ({code}): {desc}")
        if "OA_AUTH" in code or "INVALID_TOKEN" in code or "ACCESS_DENIED" in code or "TOKEN" in code:
            self.auth_state = "TOKEN_INVALID"
            raise CTraderAuthError("TOKEN_INVALID", f"cTrader Auth ({code}): {desc}")
        if "PERMISSION" in code or "SCOPE" in code:
            self.auth_state = "INSUFFICIENT_SCOPE"
            raise CTraderAuthError("INSUFFICIENT_SCOPE", f"cTrader Escopo ({code}): {desc}")
        raise RuntimeError(f"cTrader Open API ({code}): {desc}")

    def _open_connection(self) -> Any:
        self.connection_state = "CONNECTING"
        target_url = CTRADER_LIVE_WS_URL if self.is_live else CTRADER_DEMO_WS_URL
        try:
            ws = self._open_ws_url(target_url)
        except Exception as exc:
            self.connection_state = "ERROR"
            raise RuntimeError(f"Falha ao conectar na cTrader Open API ({target_url}): {exc}")

        self._ws_url_active = target_url
        self.connection_state = "CONNECTED"
        self._start_ws_reader(ws)
        try:
            app_env = {
                "clientMsgId": self._next_msg_id(),
                "payloadType": PT_APPLICATION_AUTH_REQ,
                "payload": {"clientId": self.client_id, "clientSecret": self.client_secret},
            }
            resp = self._send_via_reader(ws, app_env, timeout=10.0)
            pt = int(resp.get("payloadType") or 0)
            if pt in (PT_OA_ERROR_RES, PT_ERROR_RES):
                self._handle_error_payload(resp.get("payload") or {}, group="realtime")
            self._app_authed = True
            self._last_activity_at = time.time()
            return ws
        except Exception:
            self._stop_ws_reader()
            try:
                ws.close()
            except Exception:
                pass
            raise

    def _send_rpc(self, payload_type: int, payload: dict[str, Any], max_attempts: int = 2) -> dict[str, Any]:
        group = classify_payload_group(payload_type)
        self.rate_limiter.acquire(group)
        envelope = {
            "clientMsgId": self._next_msg_id(),
            "payloadType": int(payload_type),
            "payload": dict(payload),
        }

        if self._rpc_transport is not None:
            resp = self._rpc_transport(envelope)
            pt = int(resp.get("payloadType") or 0)
            if pt in (PT_OA_ERROR_RES, PT_ERROR_RES, PT_ORDER_ERROR_EVENT):
                self._handle_error_payload(resp.get("payload") or {}, group=group)
            self.rate_limiter.record_success(group)
            return resp

        last_exc: Exception | None = None
        resp: dict[str, Any] | None = None
        for attempt in range(max(1, int(max_attempts))):
            with self._lock:
                try:
                    if self._ws is None or self._reader_dead or not getattr(self._ws, "connected", False):
                        if self._ws is not None:
                            self.close()
                        self._ws = self._open_connection()
                    ws = self._ws
                    use_reader = self._reader_active
                except (CTraderAuthError, CTraderRateLimitError):
                    raise
                except Exception as exc:
                    last_exc = exc
                    self.close()
                    if attempt + 1 >= max_attempts:
                        raise RuntimeError(f"Conexão WebSocket cTrader interrompida: {exc}")
                    continue

            try:
                if use_reader:
                    resp = self._send_via_reader(ws, envelope)
                else:
                    with self._lock:
                        ws.send(json.dumps(envelope))
                        expected_cid = envelope["clientMsgId"]
                        resp = None
                        for _ in range(5):
                            raw = ws.recv()
                            cand = json.loads(raw)
                            if (
                                not isinstance(cand, dict)
                                or cand.get("clientMsgId") is None
                                or cand.get("clientMsgId") == expected_cid
                            ):
                                resp = cand
                                break
                        if resp is None:
                            raise RuntimeError("Resposta cTrader dessincronizada.")
                last_exc = None
                break
            except (CTraderAuthError, CTraderRateLimitError):
                raise
            except Exception as exc:
                last_exc = exc
                self.close()
                if attempt + 1 >= max_attempts:
                    raise RuntimeError(f"Conexão WebSocket cTrader interrompida: {exc}")

        if last_exc is not None or resp is None:
            raise RuntimeError(f"Conexão WebSocket cTrader interrompida: {last_exc}")

        pt = int(resp.get("payloadType") or 0)
        if pt in (PT_OA_ERROR_RES, PT_ERROR_RES, PT_ORDER_ERROR_EVENT):
            self._handle_error_payload(resp.get("payload") or {}, group=group)
        self.rate_limiter.record_success(group)
        return resp

    def ping(self) -> bool:
        try:
            if self._rpc_transport is not None:
                self._rpc_transport({"clientMsgId": self._next_msg_id(), "payloadType": PT_HEARTBEAT_EVENT, "payload": {}})
                return True
            with self._lock:
                if self._ws is None or self._reader_dead or not getattr(self._ws, "connected", False):
                    return False
                with self._send_lock:
                    self._ws.send(json.dumps({"payloadType": PT_HEARTBEAT_EVENT, "payload": {}}))
            return True
        except Exception:
            self.close()
            return False

    def close(self) -> None:
        with self._lock:
            self._stop_ws_reader()
            if self._ws is not None:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None
            with self._stream_lock:
                self._subscribed_symbol_ids.clear()
                self._stream_positions.clear()
            self._app_authed = False
            self._account_authed = False
            self._ws_url_active = ""
            self.connection_state = "DISCONNECTED"

    def reconnect(self) -> bool:
        if self._rpc_transport is not None:
            return True
        try:
            self.close()
            self.authorize()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self.connection_state = "ERROR"
            return False

    def _pick_account(self, accounts: list[dict[str, Any]]) -> dict[str, Any]:
        if not accounts:
            raise CTraderAuthError("ACCOUNT_NOT_FOUND", "Nenhuma conta cTrader encontrada para este Access Token.")
        want_demo = self.preferred_account_type != "REAL"
        if self._selected_account_id:
            for acc in accounts:
                if str(acc.get("account_id")) == self._selected_account_id or str(acc.get("ctid_account_id")) == self._selected_account_id:
                    return acc
        for acc in accounts:
            atype = str(acc.get("account_type", "")).upper()
            if want_demo and atype == "DEMO":
                return acc
            if not want_demo and atype == "REAL":
                return acc
        if want_demo:
            raise CTraderAuthError(
                "NO_DEMO_ACCOUNT",
                "Nenhuma conta DEMO cTrader encontrada para este token; fallback para conta REAL bloqueado por segurança.",
            )
        return accounts[0]

    def list_accounts(self) -> list[dict[str, Any]]:
        if not self.client_id or not self.client_secret:
            raise CTraderAuthError("APP_CREDENTIALS_INVALID", "Informe Client ID e Client Secret da cTrader.")
        if not self.access_token:
            raise CTraderAuthError("TOKEN_INVALID", "Access Token cTrader não configurado.")
        if self._rpc_transport is None and not self._app_authed:
            with self._lock:
                if self._ws is None or self._reader_dead or not getattr(self._ws, "connected", False):
                    self._ws = self._open_connection()
        resp = self._send_rpc(PT_GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ, {"accessToken": self.access_token})
        payload = resp.get("payload") or {}
        scope = str(payload.get("permissionScope") or "")
        if scope and "VIEW" in scope.upper() and "TRADE" not in scope.upper():
            # View-only still lists accounts, note scope on warn if needed
            pass
        raw_accounts = payload.get("ctidTraderAccount") or []
        out: list[dict[str, Any]] = []
        for raw in raw_accounts:
            ctid = str(raw.get("ctidTraderAccountId") or "").strip()
            if not ctid:
                continue
            is_live = bool(raw.get("isLive", False))
            trader_login = str(raw.get("traderLogin") or ctid)
            broker = str(raw.get("brokerTitleShort") or "cTrader")
            out.append(
                {
                    "account_id": f"ct_{ctid}",
                    "ctid_account_id": ctid,
                    "trader_login": trader_login,
                    "account_type": "REAL" if is_live else "DEMO",
                    "is_live": is_live,
                    "broker_name": broker,
                    "label": f"{broker} {'Real' if is_live else 'Demo'} ({trader_login})",
                }
            )
        return out

    def refresh_access_token(self) -> dict[str, Any]:
        if not self.refresh_token:
            raise CTraderAuthError("TOKEN_EXPIRED", "Refresh Token cTrader não disponível; refaça a autorização OAuth.")
        if self.client_id and self.client_secret:
            refreshed = refresh_oauth_token(
                self.client_id,
                self.client_secret,
                self.refresh_token,
                http_transport=self._http_transport,
            )
            self.access_token = refreshed["access_token"]
            self.refresh_token = refreshed["refresh_token"]
            return refreshed
        resp = self._send_rpc(PT_REFRESH_TOKEN_REQ, {"refreshToken": self.refresh_token})
        p = resp.get("payload") or {}
        self.access_token = str(p.get("accessToken") or self.access_token)
        self.refresh_token = str(p.get("refreshToken") or self.refresh_token)
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_in": int(p.get("expiresIn") or 2592000),
        }

    def authorize(self) -> dict[str, Any]:
        if not self.client_id or not self.client_secret:
            self.auth_state = "APP_CREDENTIALS_INVALID"
            self.connection_state = "ERROR"
            raise CTraderAuthError(
                "APP_CREDENTIALS_INVALID",
                "Configure seu Client ID e Client Secret obtidos em https://openapi.ctrader.com/apps.",
            )
        if not self.access_token:
            self.auth_state = "TOKEN_INVALID"
            self.connection_state = "ERROR"
            raise CTraderAuthError(
                "TOKEN_INVALID",
                "Access Token cTrader ausente. Clique em 'Autorizar com cTrader (OAuth)' ou cole seu token.",
            )

        accounts = self.list_accounts()
        picked = self._pick_account(accounts)
        ctid_int = int(picked["ctid_account_id"])
        target_live = bool(picked.get("is_live", False))
        self._selected_account_id = str(ctid_int)

        if target_live != self.is_live:
            self.is_live = target_live
            if self._rpc_transport is None:
                self.close()

        # App auth happens inside _open_connection(); now authorize account
        self._send_rpc(
            PT_ACCOUNT_AUTH_REQ,
            {"ctidTraderAccountId": ctid_int, "accessToken": self.access_token},
        )
        self._account_authed = True
        self.auth_state = "AUTHENTICATED"
        self.connection_state = "CONNECTED"

        # Fetch account balance, leverage and deposit currency
        trader_resp = self._send_rpc(PT_TRADER_REQ, {"ctidTraderAccountId": ctid_int})
        trader = (trader_resp.get("payload") or {}).get("trader") or {}
        md = int(trader.get("moneyDigits") if trader.get("moneyDigits") is not None else 2)
        self._money_digits = md
        balance = scale_money(trader.get("balance", 0), md)
        dep_asset_id = int(trader.get("depositAssetId") or 0)
        currency = "USD"
        try:
            assets_resp = self._send_rpc(PT_ASSET_LIST_REQ, {"ctidTraderAccountId": ctid_int})
            for asset in (assets_resp.get("payload") or {}).get("asset") or []:
                aid = int(asset.get("assetId") or 0)
                if aid > 0:
                    self._assets_by_id[aid] = asset
                if aid == dep_asset_id:
                    currency = str(asset.get("name") or asset.get("displayName") or "USD")
        except Exception:
            pass

        leverage_cents = int(trader.get("leverageInCents") or 10000)
        leverage = max(1, leverage_cents // 100)
        broker_name = str(trader.get("brokerName") or picked.get("broker_name") or "cTrader")
        login_str = str(trader.get("traderLogin") or picked.get("trader_login") or ctid_int)

        auth_info = {
            "loginid": login_str,
            "ctid_account_id": str(ctid_int),
            "currency": currency,
            "balance": balance,
            "is_virtual": 0 if target_live else 1,
            "is_live": target_live,
            "leverage": leverage,
            "broker_name": broker_name,
            "is_limited_risk": bool(trader.get("isLimitedRisk", False)),
            "fullname": f"{broker_name} ({'REAL' if target_live else 'DEMO'} • 1:{leverage})",
        }
        self._authorized_info = auth_info
        self._stream_balance = (time.time(), balance)
        return auth_info

    def _require_ctid(self) -> int:
        if not self._selected_account_id:
            self.authorize()
        return int(self._selected_account_id)

    def get_balance(self) -> float | None:
        if self._reader_active and self._stream_balance is not None and (time.time() - self._stream_balance[0]) < 30.0:
            return self._stream_balance[1]
        ctid = self._require_ctid()
        resp = self._send_rpc(PT_TRADER_REQ, {"ctidTraderAccountId": ctid})
        trader = (resp.get("payload") or {}).get("trader") or {}
        if "balance" in trader:
            md = int(trader.get("moneyDigits") if trader.get("moneyDigits") is not None else self._money_digits)
            self._money_digits = md
            bal = scale_money(trader["balance"], md)
            self._authorized_info["balance"] = bal
            self._stream_balance = (time.time(), bal)
            return bal
        return None

    def get_active_symbols(self) -> list[dict[str, Any]]:
        ctid = self._require_ctid()
        resp = self._send_rpc(PT_SYMBOLS_LIST_REQ, {"ctidTraderAccountId": ctid, "includeArchivedSymbols": False})
        raw_syms = (resp.get("payload") or {}).get("symbol") or []
        out: list[dict[str, Any]] = []
        for s in raw_syms:
            sid = int(s.get("symbolId") or 0)
            sname = str(s.get("symbolName") or "").strip()
            if sid <= 0 or not sname:
                continue
            if s.get("enabled") is False:
                continue
            item = {
                "name": sname,
                "symbol_id": sid,
                "description": str(s.get("description") or sname),
                "category": "cTrader",
                "visible": True,
            }
            self._symbols_by_name[sname] = item
            self._symbols_by_id[sid] = item
            out.append(item)
        return out

    def _resolve_symbol_id(self, symbol: str) -> int:
        sym = symbol.strip()
        info = self._symbols_by_name.get(sym)
        if info:
            return int(info["symbol_id"])
        self.get_active_symbols()
        info = self._symbols_by_name.get(sym)
        if not info:
            # Case-insensitive fallback match (e.g., EURUSD vs EUR/USD)
            clean_target = sym.replace("/", "").upper()
            for k, v in self._symbols_by_name.items():
                if k.replace("/", "").upper() == clean_target:
                    return int(v["symbol_id"])
            raise RuntimeError(f"Símbolo '{symbol}' não encontrado na conta cTrader ativa.")
        return int(info["symbol_id"])

    def get_symbol_details(self, symbol: str, use_cache: bool = True) -> dict[str, Any]:
        sid = self._resolve_symbol_id(symbol)
        now = time.time()
        if use_cache:
            cached = self._symbol_details_cache.get(sid)
            if cached and (now - cached[0]) < self._symbol_details_ttl:
                return dict(cached[1])
        ctid = self._require_ctid()
        resp = self._send_rpc(PT_SYMBOL_BY_ID_REQ, {"ctidTraderAccountId": ctid, "symbolId": [sid]})
        syms = (resp.get("payload") or {}).get("symbol") or []
        meta = dict(syms[0]) if syms else {"symbolId": sid, "digits": 5, "pipPosition": 4, "lotSize": DEFAULT_LOT_SIZE_CENTS}
        self._symbol_details_cache[sid] = (now, meta)
        return dict(meta)

    def subscribe_spots(self, symbol_names: list[str]) -> None:
        if not symbol_names:
            return
        ctid = self._require_ctid()
        to_sub: list[int] = []
        for s in symbol_names:
            try:
                sid = self._resolve_symbol_id(s)
                if sid not in self._subscribed_symbol_ids:
                    to_sub.append(sid)
            except Exception:
                continue
        if not to_sub:
            return
        self._send_rpc(
            PT_SUBSCRIBE_SPOTS_REQ,
            {"ctidTraderAccountId": ctid, "symbolId": to_sub, "subscribeToSpotTimestamp": True},
        )
        with self._stream_lock:
            self._subscribed_symbol_ids.update(to_sub)

    def get_live_ticks(self, symbol: str) -> list[TickRecord]:
        with self._stream_lock:
            dq = self._live_ticks.get(symbol)
            return list(dq) if dq else []

    def get_ticks_history(
        self,
        symbol: str,
        count: int = 200,
        granularity: int = 0,
        end: int | None = None,
    ) -> list[TickRecord]:
        ctid = self._require_ctid()
        sid = self._resolve_symbol_id(symbol)
        meta = self.get_symbol_details(symbol)
        digits = int(meta.get("digits", 5))
        to_ms = int(end if end is not None else time.time() * 1000)
        gran = int(granularity or 0)

        if gran > 0:
            period = TRENDBAR_PERIOD_BY_GRANULARITY.get(gran, 1)
            from_ms = max(0, to_ms - (max(1, int(count)) + 5) * gran * 1000)
            resp = self._send_rpc(
                PT_GET_TRENDBARS_REQ,
                {
                    "ctidTraderAccountId": ctid,
                    "symbolId": sid,
                    "period": period,
                    "fromTimestamp": from_ms,
                    "toTimestamp": to_ms,
                    "count": min(5000, max(1, int(count))),
                },
            )
            bars = (resp.get("payload") or {}).get("trendbar") or []
            records: list[TickRecord] = []
            for b in bars:
                low_raw = int(b.get("low") or 0)
                close_raw = low_raw + int(b.get("deltaClose") or 0)
                close_p = decode_price(close_raw, digits)
                t_ms = int(b.get("utcTimestampInMinutes") or 0) * 60_000
                vol = float(b.get("volume") or 1.0)
                records.append(
                    TickRecord(
                        time_msc=t_ms,
                        bid=close_p,
                        ask=close_p,
                        last=close_p,
                        volume_real=vol,
                        tick_volume=vol,
                        flags=0,
                    )
                )
            records.sort(key=lambda r: r.time_msc)
            return records

        # Tick-by-tick mode: prefer live stream when already populated, otherwise fetch historical ticks
        live = self.get_live_ticks(symbol)
        if len(live) >= min(40, count):
            return live[-count:]

        # Subscribe spots for future live ticks and fetch historical window
        try:
            self.subscribe_spots([symbol])
        except Exception:
            pass

        from_ms = max(0, to_ms - 3600 * 1000)
        resp = self._send_rpc(
            PT_GET_TICKDATA_REQ,
            {
                "ctidTraderAccountId": ctid,
                "symbolId": sid,
                "type": QUOTE_TYPE_BID,
                "fromTimestamp": from_ms,
                "toTimestamp": to_ms,
            },
        )
        raw_ticks = (resp.get("payload") or {}).get("tickData") or []
        if not raw_ticks:
            return live

        decoded: list[TickRecord] = []
        acc_ts = 0
        acc_px = 0
        for idx, item in enumerate(raw_ticks):
            if idx == 0:
                acc_ts = int(item.get("timestamp") or 0)
                acc_px = int(item.get("tick") or 0)
            else:
                acc_ts += int(item.get("timestamp") or 0)
                acc_px += int(item.get("tick") or 0)
            price = decode_price(acc_px, digits)
            decoded.append(
                TickRecord(
                    time_msc=acc_ts,
                    bid=price,
                    ask=price,
                    last=price,
                    volume_real=0.0,
                    tick_volume=1.0,
                    flags=0,
                )
            )
        # Response is newest-first -> reverse to chronological (oldest-first)
        decoded.reverse()
        if decoded:
            with self._stream_lock:
                dq = self._live_ticks.setdefault(symbol, deque(maxlen=600))
                if not dq:
                    for tk in decoded[-300:]:
                        dq.append(tk)
        return decoded[-count:]

    def place_market_order(
        self,
        symbol: str,
        is_buy: bool,
        lots: float,
        sl_points: float = 0.0,
        tp_points: float = 0.0,
        label: str = "PradoHFT",
        comment: str = "",
    ) -> tuple[bool, str]:
        ctid = self._require_ctid()
        sid = self._resolve_symbol_id(symbol)
        meta = self.get_symbol_details(symbol)
        protocol_vol = lots_to_protocol_volume(lots, meta)
        actual_lots = protocol_volume_to_lots(protocol_vol, meta)
        side_enum = TRADE_SIDE_BUY if is_buy else TRADE_SIDE_SELL
        side_str = "BUY" if is_buy else "SELL"

        req_payload: dict[str, Any] = {
            "ctidTraderAccountId": ctid,
            "symbolId": sid,
            "orderType": ORDER_TYPE_MARKET,
            "tradeSide": side_enum,
            "volume": protocol_vol,
            "label": (label or "PradoHFT")[:100],
            "comment": (comment or label or "PradoHFT")[:512],
            "clientOrderId": self._next_msg_id()[:50],
        }
        rel_sl = encode_relative_distance(sl_points)
        rel_tp = encode_relative_distance(tp_points)
        if rel_sl > 0:
            req_payload["relativeStopLoss"] = rel_sl
        if rel_tp > 0:
            req_payload["relativeTakeProfit"] = rel_tp
        if self._authorized_info.get("is_limited_risk"):
            req_payload["guaranteedStopLoss"] = True

        self.last_order_lifecycle = {
            "stage": "ORDER_REQUESTED",
            "symbol": symbol,
            "side": side_str,
            "lots": actual_lots,
            "volume_raw": protocol_vol,
            "timestamp": time.time(),
        }

        try:
            # Never auto-retry NEW_ORDER_REQ on timeout/disconnect without reconciling first
            resp = self._send_rpc(PT_NEW_ORDER_REQ, req_payload, max_attempts=1)
        except CTraderRateLimitError as exc:
            self.last_order_lifecycle["stage"] = "RATE_LIMITED"
            return False, f"[cTrader] RateLimit ativo: {exc}"
        except TimeoutError as exc:
            self.last_order_lifecycle["stage"] = "RECONCILIATION_REQUIRED"
            return False, f"[cTrader] Ordem em {symbol} requer reconciliação (sem reenvio automático): {exc}"
        except Exception as exc:
            self.last_order_lifecycle["stage"] = "ORDER_ERROR"
            return False, f"[cTrader] Ordem recusada em {symbol}: {exc}"

        p = resp.get("payload") or {}
        exec_type = _normalize_execution_type(p.get("executionType"))
        if exec_type == EXECUTION_ORDER_REJECTED:
            err_code = str(p.get("errorCode") or "ORDER_REJECTED")
            self.last_order_lifecycle["stage"] = "ORDER_REJECTED"
            return False, f"[cTrader] Ordem rejeitada em {symbol}: {err_code}"

        pos = p.get("position") or {}
        order = p.get("order") or {}
        pos_id = pos.get("positionId") or order.get("positionId") or ""
        order_id = order.get("orderId") or ""
        if pos_id:
            self.last_order_lifecycle["stage"] = "POSITION_OPEN"
            self.last_order_lifecycle["position_id"] = str(pos_id)
            self.last_order_lifecycle["order_id"] = str(order_id)
            if isinstance(pos, dict) and pos.get("positionId"):
                with self._stream_lock:
                    self._stream_positions[str(pos_id)] = pos
            return True, f"[cTrader] {side_str} {actual_lots} lote(s) aberto em {symbol} | Posição #{pos_id}"

        self.last_order_lifecycle["stage"] = "ORDER_ACCEPTED"
        self.last_order_lifecycle["order_id"] = str(order_id)
        return True, f"[cTrader] Ordem {side_str} {actual_lots} lote(s) aceita em {symbol} | Ordem #{order_id}"

    def pop_closed_deals(self) -> list[dict[str, Any]]:
        with self._stream_lock:
            items = list(self._recently_closed_deals)
            self._recently_closed_deals.clear()
            return items

    def get_open_positions(self) -> list[dict[str, Any]]:
        ctid = self._require_ctid()
        try:
            rec_resp = self._send_rpc(PT_RECONCILE_REQ, {"ctidTraderAccountId": ctid})
        except CTraderRateLimitError:
            with self._stream_lock:
                return [self._format_position(p) for p in self._stream_positions.values()]

        raw_positions = (rec_resp.get("payload") or {}).get("position") or []
        open_raw = [
            p for p in raw_positions
            if _normalize_position_status(p.get("positionStatus")) != POSITION_STATUS_CLOSED
        ]
        if not open_raw:
            with self._stream_lock:
                self._stream_positions.clear()
            return []

        pnl_by_pid: dict[str, dict[str, Any]] = {}
        pnl_digits: int | None = None
        try:
            pnl_resp = self._send_rpc(PT_GET_POSITION_UNREALIZED_PNL_REQ, {"ctidTraderAccountId": ctid})
            pnl_payload = pnl_resp.get("payload") or {}
            pnl_digits = int(pnl_payload.get("moneyDigits") if pnl_payload.get("moneyDigits") is not None else self._money_digits)
            for item in pnl_payload.get("positionUnrealizedPnL") or []:
                pnl_by_pid[str(item.get("positionId") or "")] = item
        except Exception:
            pass

        out: list[dict[str, Any]] = []
        new_stream_map: dict[str, dict[str, Any]] = {}
        for pos in open_raw:
            pid = str(pos.get("positionId") or "")
            formatted = self._format_position(pos, pnl_entry=pnl_by_pid.get(pid), pnl_digits=pnl_digits)
            pos_copy = dict(pos)
            pos_copy["_cached_profit"] = formatted["profit"]
            if pid:
                new_stream_map[pid] = pos_copy
            out.append(formatted)

        with self._stream_lock:
            self._stream_positions = new_stream_map
        return out

    def close_position(self, position_id: str | int, volume_raw: int | None = None) -> tuple[bool, str]:
        try:
            pid_int = int(position_id)
        except (TypeError, ValueError):
            return False, f"[cTrader] ID de posição inválido: {position_id}"

        ctid = self._require_ctid()
        vol = int(volume_raw or 0)
        if vol <= 0:
            with self._stream_lock:
                cached_pos = self._stream_positions.get(str(pid_int))
                if cached_pos:
                    vol = int((cached_pos.get("tradeData") or {}).get("volume") or 0)
        if vol <= 0:
            open_pos = self.get_open_positions()
            matched = next((p for p in open_pos if str(p.get("ticket")) == str(pid_int)), None)
            if matched:
                vol = int(matched.get("volume_raw") or 0)
            else:
                return True, f"[cTrader] Posição #{pid_int} já estava encerrada na corretora."
        if vol <= 0:
            return False, f"[cTrader] Volume da posição #{pid_int} não encontrado para encerramento."

        try:
            self._send_rpc(
                PT_CLOSE_POSITION_REQ,
                {"ctidTraderAccountId": ctid, "positionId": pid_int, "volume": vol},
            )
        except CTraderRateLimitError as exc:
            return False, f"[cTrader] RateLimit ativo ao encerrar #{pid_int}: {exc}"
        except Exception as exc:
            err_low = str(exc).lower()
            if "not_found" in err_low or "already" in err_low or "closed" in err_low or "position_not_found" in err_low:
                with self._stream_lock:
                    self._stream_positions.pop(str(pid_int), None)
                return True, f"[cTrader] Posição #{pid_int} já estava encerrada na corretora."
            return False, f"[cTrader] Erro ao encerrar posição #{pid_int}: {exc}"

        with self._stream_lock:
            self._stream_positions.pop(str(pid_int), None)
        return True, f"[cTrader] Posição #{pid_int} encerrada com sucesso."
