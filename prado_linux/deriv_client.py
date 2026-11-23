"""Deriv API Client (Modern REST + OTP WebSocket + Public WS + RateLimit Manager).

Follows docs/vendor/deriv-api/llms.txt:
- Public market data: wss://api.derivws.com/trading/v1/options/ws/public (no OTP, no auth)
- Authenticated trading: REST GET /trading/v1/options/accounts + POST .../otp -> data.url
- PAT auth sends Authorization: Bearer <token> + Deriv-App-ID: <app_id>
- Legacy fallback only for classic non-pat_ tokens when explicitly configured.
"""
from __future__ import annotations

from collections import deque
import json
import random
import re
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.request

from prado_linux.flow_math import TickRecord

REST_BASE_URL = "https://api.derivws.com"
PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"
LEGACY_WS_ENDPOINTS = (
    "wss://red.derivws.com/websockets/v3",
    "wss://green.derivws.com/websockets/v3",
    "wss://blue.derivws.com/websockets/v3",
    "wss://ws.derivws.com/websockets/v3",
)

# Official WebSocket budgets from docs/vendor/deriv-api/llms/api-overview.md
WS_BUDGETS: dict[str, tuple[int, int]] = {
    "trade": (360, 14400),      # proposal, proposal_open_contract, buy, sell
    "account": (100, 2000),     # balance, statement
    "portfolio": (30, 1500),    # portfolio, profit_table
    "other": (220, 14400),      # ticks_history, active_symbols, etc.
}
REST_USER_PER_MIN = 80


def mask_secret(value: str, prefix_len: int = 4, suffix_len: int = 4) -> str:
    s = (value or "").strip()
    if not s:
        return "--"
    if len(s) <= prefix_len + suffix_len:
        return "*" * len(s)
    return f"{s[:prefix_len]}****{s[-suffix_len:]}"


def classify_ws_budget_group(payload: dict[str, Any]) -> str:
    if any(k in payload for k in ("proposal", "proposal_open_contract", "buy", "sell")):
        return "trade"
    if any(k in payload for k in ("balance", "statement")):
        return "account"
    if any(k in payload for k in ("portfolio", "profit_table")):
        return "portfolio"
    if "ping" in payload:
        return "ping"
    return "other"


def extract_ws_endpoint(payload: dict[str, Any]) -> str:
    for key in (
        "proposal_open_contract",
        "proposal",
        "buy",
        "sell",
        "portfolio",
        "profit_table",
        "balance",
        "statement",
        "ticks_history",
        "ticks",
        "contracts_for",
        "active_symbols",
        "authorize",
        "ping",
    ):
        if key in payload:
            return key
    return "other"


class DerivAuthError(RuntimeError):
    """Structured authentication error carrying a canonical auth_state."""

    def __init__(self, auth_state: str, message: str) -> None:
        super().__init__(message)
        self.auth_state = auth_state


class DerivRateLimitError(RuntimeError):
    """Raised when local or remote RateLimit blocks a request."""


class DerivRateLimiter:
    """Centralized thread-safe sliding-window rate limiter with scoped backoff + jitter."""

    _ISOLATED_ENDPOINTS = frozenset({"proposal_open_contract", "ticks_history"})

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ws_windows: dict[str, deque[float]] = {k: deque() for k in WS_BUDGETS}
        self._ws_blocked_until: dict[str, float] = {}
        self._ws_last_error: dict[str, str] = {}
        self._ws_endpoint_blocked_until: dict[str, float] = {}
        self._endpoint_last_error: dict[str, str] = {}
        self._rest_window: deque[float] = deque()
        self._rest_blocked_until: float = 0.0
        self._rest_last_error: str = ""
        self._blocked_until: float = 0.0
        self._consecutive_429: int = 0
        self._consecutive_429_by_key: dict[str, int] = {}
        self._last_error: str = ""

    def _prune(self, dq: deque[float], now: float, horizon: float = 3600.0) -> None:
        cutoff = now - horizon
        while dq and dq[0] < cutoff:
            dq.popleft()

    def is_endpoint_blocked(self, endpoint: str, now: float | None = None) -> float:
        if not endpoint:
            return 0.0
        t = time.time() if now is None else now
        with self._lock:
            until = max(self._blocked_until, self._ws_endpoint_blocked_until.get(endpoint, 0.0))
            return round(max(0.0, until - t), 2)

    def acquire_ws(self, group: str, now: float | None = None, endpoint: str = "") -> None:
        if group == "ping":
            return
        t = time.time() if now is None else now
        with self._lock:
            ep_until = self._ws_endpoint_blocked_until.get(endpoint, 0.0) if endpoint else 0.0
            grp_until = self._ws_blocked_until.get(group, 0.0)
            max_until = max(self._blocked_until, grp_until, ep_until)
            if t < max_until:
                wait = round(max_until - t, 2)
                if ep_until >= grp_until and ep_until >= self._blocked_until and endpoint:
                    reason = self._endpoint_last_error.get(endpoint) or self._last_error or "aguardando janela"
                elif grp_until >= self._blocked_until:
                    reason = self._ws_last_error.get(group) or self._last_error or "aguardando janela"
                else:
                    reason = self._last_error or "aguardando janela"
                raise DerivRateLimitError(f"RateLimit ativo (cooldown {wait}s): {reason}")
            dq = self._ws_windows.setdefault(group, deque())
            self._prune(dq, t, 3600.0)
            per_min, per_hour = WS_BUDGETS.get(group, WS_BUDGETS["other"])
            recent_min = sum(1 for ts in dq if ts >= t - 60.0)
            if recent_min >= per_min or len(dq) >= per_hour:
                self._ws_blocked_until[group] = t + 2.0
                msg = f"Orçamento local WS '{group}' atingido ({recent_min}/{per_min} min)"
                self._ws_last_error[group] = msg
                self._last_error = msg
                raise DerivRateLimitError(msg)
            dq.append(t)

    def acquire_rest(self, now: float | None = None) -> None:
        t = time.time() if now is None else now
        with self._lock:
            rest_blocked = max(self._blocked_until, self._rest_blocked_until)
            if t < rest_blocked:
                wait = round(rest_blocked - t, 2)
                reason = self._rest_last_error if self._rest_blocked_until >= self._blocked_until else self._last_error
                raise DerivRateLimitError(
                    f"RateLimit REST ativo (cooldown {wait}s): {reason or 'aguardando janela'}"
                )
            self._prune(self._rest_window, t, 60.0)
            if len(self._rest_window) >= REST_USER_PER_MIN:
                self._rest_blocked_until = t + 2.0
                msg = f"Orçamento REST atingido ({len(self._rest_window)}/{REST_USER_PER_MIN} min)"
                self._rest_last_error = msg
                self._last_error = msg
                raise DerivRateLimitError(msg)
            self._rest_window.append(t)

    def record_remote_rate_limit(
        self,
        message: str = "",
        now: float | None = None,
        scope: str = "global",
        group: str | None = None,
        endpoint: str | None = None,
    ) -> float:
        t = time.time() if now is None else now
        msg = message or "Deriv API RateLimit"
        with self._lock:
            if scope == "rest":
                key = "rest"
                streak = self._consecutive_429_by_key.get(key, 0) + 1
                self._consecutive_429_by_key[key] = streak
                delay = min(30.0, 2.0 ** min(streak, 4)) + random.uniform(0.1, 1.0)
                self._rest_blocked_until = max(self._rest_blocked_until, t + delay)
                self._rest_last_error = msg
                return delay

            if scope == "ws":
                if endpoint and endpoint in self._ISOLATED_ENDPOINTS:
                    key = f"ep:{endpoint}"
                    streak = self._consecutive_429_by_key.get(key, 0) + 1
                    self._consecutive_429_by_key[key] = streak
                    delay = min(30.0, 2.0 ** min(streak, 4)) + random.uniform(0.1, 1.0)
                    self._ws_endpoint_blocked_until[endpoint] = max(
                        self._ws_endpoint_blocked_until.get(endpoint, 0.0), t + delay
                    )
                    self._endpoint_last_error[endpoint] = msg
                    return delay
                if group:
                    key = f"grp:{group}"
                    streak = self._consecutive_429_by_key.get(key, 0) + 1
                    self._consecutive_429_by_key[key] = streak
                    delay = min(30.0, 2.0 ** min(streak, 4)) + random.uniform(0.1, 1.0)
                    self._ws_blocked_until[group] = max(self._ws_blocked_until.get(group, 0.0), t + delay)
                    self._ws_last_error[group] = msg
                    return delay

            self._consecutive_429 += 1
            base = min(60.0, 2.0 ** min(self._consecutive_429, 5))
            delay = base + random.uniform(0.1, 1.0)
            self._blocked_until = max(self._blocked_until, t + delay)
            self._last_error = msg
            return delay

    def record_success(
        self,
        scope: str = "global",
        group: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        with self._lock:
            if scope == "rest":
                self._consecutive_429_by_key.pop("rest", None)
                return
            if scope == "ws":
                if endpoint:
                    self._consecutive_429_by_key.pop(f"ep:{endpoint}", None)
                if group:
                    self._consecutive_429_by_key.pop(f"grp:{group}", None)
                return
            if self._consecutive_429 > 0:
                self._consecutive_429 = 0

    def status(self, now: float | None = None) -> dict[str, Any]:
        t = time.time() if now is None else now
        with self._lock:
            counts_min: dict[str, int] = {}
            for grp, dq in self._ws_windows.items():
                self._prune(dq, t, 3600.0)
                counts_min[grp] = sum(1 for ts in dq if ts >= t - 60.0)
            self._prune(self._rest_window, t, 60.0)
            global_rem = max(0.0, self._blocked_until - t)
            rest_rem = max(0.0, self._rest_blocked_until - t)
            group_cooldowns = {
                grp: round(until - t, 2)
                for grp, until in self._ws_blocked_until.items()
                if until > t
            }
            endpoint_cooldowns = {
                ep: round(until - t, 2)
                for ep, until in self._ws_endpoint_blocked_until.items()
                if until > t
            }
            trade_rem = group_cooldowns.get("trade", 0.0)
            blocked = global_rem > 0.0 or trade_rem > 0.0
            last_err = self._last_error
            if not last_err and endpoint_cooldowns:
                first_ep = next(iter(endpoint_cooldowns))
                last_err = self._endpoint_last_error.get(first_ep, "")
            elif not last_err and group_cooldowns:
                first_grp = next(iter(group_cooldowns))
                last_err = self._ws_last_error.get(first_grp, "")
            return {
                "state": "BLOCKED" if blocked else "NORMAL",
                "cooldown_seconds": round(max(global_rem, trade_rem), 2),
                "rest_cooldown_seconds": round(rest_rem, 2),
                "group_cooldowns": group_cooldowns,
                "endpoint_cooldowns": endpoint_cooldowns,
                "ws_per_min": counts_min,
                "rest_per_min": len(self._rest_window),
                "last_error": last_err,
            }


class DerivClient:
    """Thread-safe Deriv API client supporting Modern REST+OTP WS, Public WS, and Legacy fallback."""

    DERIV_ENDPOINTS = LEGACY_WS_ENDPOINTS

    def __init__(
        self,
        token: str,
        app_id: str = "1089",
        rpc_transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        rest_transport: Callable[[str, str, dict[str, str]], dict[str, Any]] | None = None,
        rate_limiter: DerivRateLimiter | None = None,
        preferred_account_type: str = "DEMO",
    ) -> None:
        self.token = token.strip()
        self.app_id = (app_id or "1089").strip()
        self.preferred_account_type = (preferred_account_type or "DEMO").upper()
        self._rpc_transport = rpc_transport
        self._rest_transport = rest_transport
        self.rate_limiter = rate_limiter or DerivRateLimiter()
        self._lock = threading.RLock()
        self._send_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending_rpcs: dict[int, dict[str, Any]] = {}
        self._stream_lock = threading.RLock()
        self._stream_contracts: dict[str, dict[str, Any]] = {}
        self._poc_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._poc_cache_ttl: float = 10.0
        self._contracts_for_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._contracts_for_cache_ttl: float = 180.0
        self._subscribed_cids: set[str] = set()
        self._poc_stream_subscribed: bool = False
        self._balance_stream_subscribed: bool = False
        self._stream_balance: tuple[float, float] | None = None
        self._recently_closed_contracts: deque[dict[str, Any]] = deque(maxlen=200)
        self._reader_active: bool = False
        self._reader_dead: bool = False
        self._reader_stop = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._ws: Any = None
        self._ws_url_active: str = ""
        self._authorized_info: dict[str, Any] = {}
        self._selected_account_id: str = ""
        self._otp_expires_at: float = 0.0
        self._req_seq: int = 0
        self.connection_state: str = "DISCONNECTED"
        self.auth_state: str = "UNAUTHENTICATED"
        self.last_error: str = ""
        self.last_order_lifecycle: dict[str, Any] = {}

    @property
    def is_pat_token(self) -> bool:
        return self.token.startswith("pat_")

    @property
    def is_public_client(self) -> bool:
        return not self.token

    @property
    def ws_url(self) -> str:
        if self.is_public_client:
            return PUBLIC_WS_URL
        if self._ws_url_active:
            return self._ws_url_active
        return f"{self.DERIV_ENDPOINTS[0]}?app_id={self.app_id}"

    def _next_req_id(self) -> int:
        self._req_seq += 1
        return self._req_seq

    def _rest_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "Prado-Ubuntu-HFT/2.0",
        }
        # Deriv-App-ID is required for PAT auth, not required for OAuth 2.0
        if self.is_pat_token and self.app_id:
            headers["Deriv-App-ID"] = self.app_id
        return headers

    def _rest_call(self, method: str, path: str) -> dict[str, Any]:
        self.rate_limiter.acquire_rest()
        url = f"{REST_BASE_URL}{path}"
        headers = self._rest_headers()

        if self._rest_transport is not None:
            resp = self._rest_transport(method, url, headers)
            self.rate_limiter.record_success(scope="rest")
            return resp

        req = urllib.request.Request(
            url,
            data=b"{}" if method.upper() == "POST" else None,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                raw = r.read().decode("utf-8")
                self.rate_limiter.record_success(scope="rest")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 429:
                self.rate_limiter.record_remote_rate_limit(f"HTTP 429: {body[:120]}", scope="rest")
                raise DerivRateLimitError(f"Deriv REST RateLimit (429): {body[:200]}")
            if exc.code == 401:
                lower_body = body.lower()
                if "expir" in lower_body:
                    self.auth_state = "TOKEN_EXPIRED"
                    raise DerivAuthError("TOKEN_EXPIRED", f"Deriv REST 401 (token expirado): {body[:200]}")
                if "Deriv-App-ID" in body or "app" in lower_body:
                    self.auth_state = "APP_ID_MISMATCH"
                    raise DerivAuthError("APP_ID_MISMATCH", f"Deriv REST 401 (App ID): {body[:200]}")
                self.auth_state = "TOKEN_INVALID"
                raise DerivAuthError("TOKEN_INVALID", f"Deriv REST 401: {body[:200]}")
            if exc.code == 403:
                self.auth_state = "INSUFFICIENT_SCOPE"
                raise DerivAuthError("INSUFFICIENT_SCOPE", f"Deriv REST 403 (escopo insuficiente): {body[:200]}")
            raise RuntimeError(f"Deriv REST ({exc.code}): {body[:240]}")

    def _open_ws_url(self, url: str) -> Any:
        try:
            import websocket  # type: ignore

            return websocket.create_connection(
                url,
                origin="https://app.deriv.com",
                header=["User-Agent: Mozilla/5.0"],
                timeout=10,
            )
        except ModuleNotFoundError:
            from websockets.sync.client import connect as ws_sync_connect  # type: ignore

            cm = ws_sync_connect(
                url,
                origin="https://app.deriv.com",
                additional_headers={"User-Agent": "Mozilla/5.0"},
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

    def _is_contract_closed(self, poc: dict[str, Any]) -> bool:
        return (
            poc.get("is_sold") in (1, True)
            or poc.get("is_expired") in (1, True)
            or str(poc.get("status", "")).lower() in ("sold", "won", "lost", "cancelled")
        )

    def _format_contract_position(self, poc: dict[str, Any], fallback: dict[str, Any] | None = None) -> dict[str, Any]:
        fb = fallback or {}
        cid = str(poc.get("contract_id") or fb.get("contract_id") or "")
        ctype = str(poc.get("contract_type") or fb.get("contract_type") or "MULTUP").upper()
        is_buy = "UP" in ctype or "CALL" in ctype
        lim = poc.get("limit_order") or {}
        sl_amt = float((lim.get("stop_loss") or {}).get("order_amount", 0.0) or 0.0)
        tp_amt = float((lim.get("take_profit") or {}).get("order_amount", 0.0) or 0.0)
        return {
            "ticket": cid,
            "symbol": str(poc.get("underlying_symbol") or poc.get("underlying") or fb.get("underlying_symbol") or fb.get("symbol") or ""),
            "type": "BUY" if is_buy else "SELL",
            "side": "BUY" if is_buy else "SELL",
            "volume": float(poc.get("buy_price", fb.get("buy_price", 0.0)) or 0.0),
            "price_open": round(float(poc.get("entry_spot", 0.0) or 0.0), 6),
            "price_current": round(float(poc.get("current_spot", 0.0) or 0.0), 6),
            "sl": sl_amt,
            "tp": tp_amt,
            "profit": round(float(poc.get("profit", 0.0) or 0.0), 2),
            "comment": f"Deriv_{ctype}",
        }

    def _ingest_stream_message(self, msg: dict[str, Any]) -> None:
        poc = msg.get("proposal_open_contract")
        if isinstance(poc, dict):
            cid = str(poc.get("contract_id") or "")
            if cid:
                now = time.time()
                with self._stream_lock:
                    self._poc_cache[cid] = (now, poc)
                    if self._is_contract_closed(poc):
                        self._stream_contracts.pop(cid, None)
                        self._subscribed_cids.discard(cid)
                        self._recently_closed_contracts.append(poc)
                    else:
                        self._stream_contracts[cid] = poc
        bal = msg.get("balance")
        if isinstance(bal, dict) and "balance" in bal:
            try:
                bal_val = float(bal["balance"])
                with self._stream_lock:
                    self._authorized_info["balance"] = bal_val
                    self._stream_balance = (time.time(), bal_val)
            except (TypeError, ValueError):
                pass

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
                        err_name = type(exc).__name__.lower()
                        if "timeout" in err_name:
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

                    self._ingest_stream_message(msg)
                    rid = msg.get("req_id")
                    matched_waiter = False
                    if rid is not None:
                        with self._pending_lock:
                            entry = self._pending_rpcs.get(rid)
                            if entry is not None:
                                entry["response"] = msg
                                entry["event"].set()
                                matched_waiter = True
                    if not matched_waiter and msg.get("error"):
                        err = msg["error"]
                        code = str(err.get("code", "ERR"))
                        err_msg = str(err.get("message", err))
                        ep = str(msg.get("msg_type") or "")
                        if code in ("RateLimit", "TooManyRequests"):
                            grp = classify_ws_budget_group({ep: 1}) if ep else "other"
                            self.rate_limiter.record_remote_rate_limit(err_msg, scope="ws", group=grp, endpoint=ep)
                        elif code in ("InvalidToken", "AuthorizationRequired"):
                            self.auth_state = "TOKEN_EXPIRED" if "expir" in err_msg.lower() else "TOKEN_INVALID"
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
        self._poc_stream_subscribed = False
        self._balance_stream_subscribed = False
        with self._pending_lock:
            for entry in self._pending_rpcs.values():
                if entry.get("response") is None and entry.get("error") is None:
                    entry["error"] = ConnectionError("Conexão WebSocket fechada.")
                    entry["event"].set()
        t = self._reader_thread
        self._reader_thread = None
        if t is not None and t.is_alive() and threading.current_thread() is not t:
            t.join(timeout=0.5)

    def _send_via_reader(self, ws: Any, req_payload: dict[str, Any], timeout: float = 12.0) -> dict[str, Any]:
        rid = int(req_payload["req_id"])
        ev = threading.Event()
        entry: dict[str, Any] = {"event": ev, "response": None, "error": None}
        with self._pending_lock:
            self._pending_rpcs[rid] = entry
        try:
            with self._send_lock:
                ws.send(json.dumps(req_payload))
            if not ev.wait(timeout=timeout):
                raise TimeoutError("Tempo limite aguardando resposta WebSocket Deriv.")
            if entry["error"] is not None:
                raise entry["error"]
            resp = entry["response"]
            if not isinstance(resp, dict):
                raise RuntimeError("Resposta WebSocket inválida.")
            return resp
        finally:
            with self._pending_lock:
                self._pending_rpcs.pop(rid, None)

    def _start_live_streams(self, ws: Any) -> None:
        if self.is_public_client or not self._reader_active:
            return
        if not self._poc_stream_subscribed:
            try:
                poc_req = {"proposal_open_contract": 1, "subscribe": 1, "req_id": self._next_req_id()}
                self.rate_limiter.acquire_ws("trade", endpoint="proposal_open_contract")
                resp = self._send_via_reader(ws, poc_req, timeout=6.0)
                if not resp.get("error"):
                    self._poc_stream_subscribed = True
                elif resp.get("error", {}).get("code") in ("RateLimit", "TooManyRequests"):
                    self.rate_limiter.record_remote_rate_limit(
                        str(resp["error"].get("message", "")),
                        scope="ws",
                        group="trade",
                        endpoint="proposal_open_contract",
                    )
            except Exception:
                pass
        if not self._balance_stream_subscribed:
            try:
                bal_req = {"balance": 1, "subscribe": 1, "req_id": self._next_req_id()}
                self.rate_limiter.acquire_ws("account", endpoint="balance")
                resp = self._send_via_reader(ws, bal_req, timeout=6.0)
                if not resp.get("error"):
                    self._balance_stream_subscribed = True
            except Exception:
                pass

    def has_live_contract_stream(self) -> bool:
        return bool(self._reader_active and not self._reader_dead and self._poc_stream_subscribed)

    def get_stream_contract(self, contract_id: str | int) -> dict[str, Any] | None:
        cid = str(contract_id)
        with self._stream_lock:
            poc = self._stream_contracts.get(cid)
            if poc is not None:
                return self._format_contract_position(poc)
            cached = self._poc_cache.get(cid)
            if cached is not None and self._is_contract_closed(cached[1]):
                return {"_closed": True}
        return None

    def pop_closed_contracts(self) -> list[dict[str, Any]]:
        with self._stream_lock:
            items = list(self._recently_closed_contracts)
            self._recently_closed_contracts.clear()
            return items

    def _open_connection(self) -> Any:
        self.connection_state = "CONNECTING"
        if self.is_public_client:
            try:
                ws = self._open_ws_url(PUBLIC_WS_URL)
                self._ws_url_active = PUBLIC_WS_URL
                self.connection_state = "CONNECTED"
                self._start_ws_reader(ws)
                return ws
            except Exception as exc:
                self.connection_state = "ERROR"
                raise RuntimeError(f"Falha ao conectar no WebSocket público Deriv: {exc}")

        # Modern OTP-URL flow for PAT or OAuth tokens
        if self.is_pat_token or len(self.token) > 40:
            if self.is_pat_token and self.app_id == "1089":
                self.auth_state = "APP_ID_MISMATCH"
                self.connection_state = "ERROR"
                raise DerivAuthError(
                    "APP_ID_MISMATCH",
                    "Token 'pat_...' não é aceito com App ID legado 1089. "
                    "Configure um App ID registrado em developers.deriv.com.",
                )
            if not self._selected_account_id:
                self.authorize()
            otp_resp = self._rest_call("POST", f"/trading/v1/options/accounts/{self._selected_account_id}/otp")
            otp_url = (otp_resp.get("data") or {}).get("url", "")
            if not otp_url:
                self.connection_state = "ERROR"
                raise DerivAuthError("TOKEN_INVALID", f"Resposta OTP inválida da Deriv: {otp_resp}")
            try:
                ws = self._open_ws_url(otp_url)
            except Exception as exc:
                self.connection_state = "ERROR"
                raise RuntimeError(f"Falha ao conectar no WebSocket OTP Deriv: {exc}")
            self._ws_url_active = otp_url.split("?")[0]
            self._otp_expires_at = time.time() + 240.0
            self.connection_state = "CONNECTED"
            self._start_ws_reader(ws)
            self._start_live_streams(ws)
            return ws

        # Legacy classic token flow (only when non-PAT token is used)
        last_exc: Exception | None = None
        for base in self.DERIV_ENDPOINTS:
            url = f"{base}?app_id={self.app_id}"
            try:
                ws = self._open_ws_url(url)
                self._ws_url_active = url
                self.connection_state = "CONNECTED"
                self._start_ws_reader(ws)
                auth_resp = self._send_via_reader(
                    ws, {"authorize": self.token, "req_id": self._next_req_id()}, timeout=10.0
                )
                if auth_resp.get("error"):
                    self._stop_ws_reader()
                    try:
                        ws.close()
                    except Exception:
                        pass
                    self._handle_rpc_error(auth_resp["error"], group="other", endpoint="authorize")
                self._authorized_info = auth_resp.get("authorize", {})
                self.auth_state = "AUTHENTICATED"
                self._start_live_streams(ws)
                return ws
            except (DerivAuthError, DerivRateLimitError):
                raise
            except Exception as exc:
                self._stop_ws_reader()
                last_exc = exc
        self.connection_state = "ERROR"
        raise RuntimeError(f"Falha ao conectar nos servidores WebSocket Deriv: {last_exc}")

    def _handle_rpc_error(self, err: dict[str, Any], group: str = "other", endpoint: str = "") -> None:
        code = str(err.get("code", "ERR"))
        msg = str(err.get("message", err))
        if code in ("RateLimit", "TooManyRequests"):
            self.rate_limiter.record_remote_rate_limit(msg, scope="ws", group=group, endpoint=endpoint)
            raise DerivRateLimitError(f"Deriv API ({code}): {msg}")
        if code in ("InvalidToken", "AuthorizationRequired"):
            if "expir" in msg.lower():
                self.auth_state = "TOKEN_EXPIRED"
                raise DerivAuthError("TOKEN_EXPIRED", f"Deriv Auth ({code}): {msg}")
            self.auth_state = "TOKEN_INVALID"
            raise DerivAuthError("TOKEN_INVALID", f"Deriv Auth ({code}): {msg}")
        if code in ("InvalidAppID",):
            self.auth_state = "APP_ID_MISMATCH"
            raise DerivAuthError("APP_ID_MISMATCH", f"Deriv Auth ({code}): {msg}")
        raise RuntimeError(f"Deriv API ({code}): {msg}")

    def _send_rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        group = classify_ws_budget_group(payload)
        endpoint = extract_ws_endpoint(payload)
        self.rate_limiter.acquire_ws(group, endpoint=endpoint)

        req_payload = dict(payload)
        if "req_id" not in req_payload:
            req_payload["req_id"] = self._next_req_id()

        if self._rpc_transport is not None:
            resp = self._rpc_transport(req_payload)
            if isinstance(resp, dict) and resp.get("error"):
                err_ep = str(resp.get("msg_type") or endpoint)
                self._handle_rpc_error(resp["error"], group=group, endpoint=err_ep)
            self.rate_limiter.record_success(scope="ws", group=group, endpoint=endpoint)
            return resp

        is_buy_call = "buy" in req_payload
        max_attempts = 1 if is_buy_call else 2
        last_transport_exc: Exception | None = None
        resp: dict[str, Any] | None = None

        for attempt in range(max_attempts):
            with self._lock:
                if (
                    self._ws is not None
                    and (self.is_pat_token or len(self.token) > 40)
                    and self._otp_expires_at > 0
                    and time.time() >= self._otp_expires_at
                ):
                    self.close()
                try:
                    if self._ws is None or self._reader_dead or not getattr(self._ws, "connected", False):
                        if self._ws is not None:
                            self.close()
                        self._ws = self._open_connection()
                        # Legacy classic mock-socket handshake only; real reader connections authenticate inside _open_connection
                        if (
                            not self._reader_active
                            and self.token
                            and not self.is_pat_token
                            and len(self.token) <= 40
                            and "authorize" not in req_payload
                        ):
                            self._ws.send(json.dumps({"authorize": self.token, "req_id": self._next_req_id()}))
                            auth_raw = self._ws.recv()
                            auth_resp = json.loads(auth_raw)
                            if auth_resp.get("error"):
                                self.close()
                                self._handle_rpc_error(auth_resp["error"], group="other", endpoint="authorize")
                            self._authorized_info = auth_resp.get("authorize", {})
                            self.auth_state = "AUTHENTICATED"
                    ws = self._ws
                    use_reader = self._reader_active
                except (DerivAuthError, DerivRateLimitError):
                    raise
                except Exception as exc:
                    last_transport_exc = exc
                    self.close()
                    self.connection_state = "DISCONNECTED"
                    if attempt + 1 >= max_attempts:
                        raise RuntimeError(f"Conexão WebSocket interrompida: {exc}")
                    continue

            try:
                if use_reader:
                    resp = self._send_via_reader(ws, req_payload)
                else:
                    with self._lock:
                        ws.send(json.dumps(req_payload))
                        expected_req_id = req_payload.get("req_id")
                        resp = None
                        for _ in range(5):
                            raw = ws.recv()
                            candidate = json.loads(raw)
                            if (
                                expected_req_id is None
                                or not isinstance(candidate, dict)
                                or candidate.get("req_id") is None
                                or candidate.get("req_id") == expected_req_id
                            ):
                                resp = candidate
                                break
                        if resp is None:
                            raise RuntimeError("Resposta WebSocket dessincronizada (req_id divergente).")
                last_transport_exc = None
                break
            except (DerivAuthError, DerivRateLimitError):
                raise
            except Exception as exc:
                last_transport_exc = exc
                self.close()
                self.connection_state = "DISCONNECTED"
                if attempt + 1 >= max_attempts:
                    raise RuntimeError(f"Conexão WebSocket interrompida: {exc}")

        if last_transport_exc is not None or resp is None:
            raise RuntimeError(f"Conexão WebSocket interrompida: {last_transport_exc}")

        if resp.get("error"):
            err_ep = str(resp.get("msg_type") or endpoint)
            self._handle_rpc_error(resp["error"], group=group, endpoint=err_ep)
        self.rate_limiter.record_success(scope="ws", group=group, endpoint=endpoint)
        return resp

    def ping(self) -> bool:
        try:
            resp = self._send_rpc({"ping": 1})
            ok = resp.get("ping") == "pong" or resp.get("msg_type") == "ping"
            if not ok:
                self.close()
            return ok
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
                self._subscribed_cids.clear()
                self._stream_contracts.clear()
            self.connection_state = "DISCONNECTED"

    def reconnect(self) -> bool:
        """Controlled reconnection: closes stale WS and requests fresh OTP if needed."""
        if self._rpc_transport is not None:
            return True
        with self._lock:
            self.connection_state = "RECONNECTING"
            self._stop_ws_reader()
            if self._ws is not None:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None
            with self._stream_lock:
                self._subscribed_cids.clear()
                self._stream_contracts.clear()
            try:
                self._ws = self._open_connection()
                return True
            except Exception as exc:
                self.last_error = str(exc)
                self.connection_state = "ERROR"
                return False

    def _pick_account(self, accounts: list[dict[str, Any]]) -> dict[str, Any]:
        want_demo = self.preferred_account_type != "REAL"
        for acc in accounts:
            atype = str(acc.get("account_type", "")).lower()
            if want_demo and atype == "demo":
                return acc
            if not want_demo and atype == "real":
                return acc
        if want_demo:
            raise DerivAuthError(
                "NO_DEMO_ACCOUNT",
                "Nenhuma conta DEMO encontrada para este token; fallback para conta REAL bloqueado por segurança.",
            )
        return accounts[0]

    def list_accounts(self) -> list[dict[str, Any]]:
        """List all accounts (Demo & Real) belonging to the configured token + App ID."""
        if self._rpc_transport is None and (self.is_pat_token or len(self.token) > 40):
            if self.app_id == "1089":
                raise DerivAuthError(
                    "APP_ID_MISMATCH",
                    "Token 'pat_...' não é aceito com App ID 1089.",
                )
            data = self._rest_call("GET", "/trading/v1/options/accounts")
            accounts = data.get("data", []) if isinstance(data, dict) else []
            return list(accounts)
        auth = self.authorize()
        return [
            {
                "account_id": auth.get("loginid", "---"),
                "account_type": "demo" if auth.get("is_virtual", 1) else "real",
                "balance": float(auth.get("balance", 0.0)),
                "currency": str(auth.get("currency", "USD")),
            }
        ]

    def authorize(self) -> dict[str, Any]:
        if self._rpc_transport is None and self.is_pat_token and self.app_id == "1089":
            self.auth_state = "APP_ID_MISMATCH"
            self.connection_state = "ERROR"
            raise DerivAuthError(
                "APP_ID_MISMATCH",
                "Token 'pat_...' não é aceito com App ID 1089. "
                "Gere um App ID em developers.deriv.com ou utilize um token clássico.",
            )

        if self._rpc_transport is None and (self.is_pat_token or len(self.token) > 40):
            data = self._rest_call("GET", "/trading/v1/options/accounts")
            accounts = data.get("data", []) if isinstance(data, dict) else []
            if not accounts:
                self.auth_state = "TOKEN_INVALID"
                raise DerivAuthError("TOKEN_INVALID", "Nenhuma conta retornada pela API Deriv REST v1.")
            acc = self._pick_account(accounts)
            acc_id = str(acc.get("account_id", acc.get("loginid", "")))
            self._selected_account_id = acc_id
            auth = {
                "loginid": acc_id or "---",
                "currency": str(acc.get("currency", "USD")),
                "balance": float(acc.get("balance", 0.0)),
                "is_virtual": 1 if str(acc.get("account_type", "")).lower() == "demo" else 0,
                "fullname": f"Conta Deriv ({str(acc.get('account_type', 'demo')).upper()})",
            }
            self._authorized_info = auth
            self.auth_state = "AUTHENTICATED"
            return auth

        resp = self._send_rpc({"authorize": self.token})
        auth = resp.get("authorize", {})
        self._authorized_info = auth
        self.auth_state = "AUTHENTICATED"
        self.connection_state = "CONNECTED"
        return auth

    def get_balance(self) -> float | None:
        """Lightweight balance check without re-running authorize()."""
        if self._reader_active and self._stream_balance is not None and (time.time() - self._stream_balance[0]) < 60.0:
            return self._stream_balance[1]
        if self.is_pat_token or (len(self.token) > 40 and self._rpc_transport is None):
            data = self._rest_call("GET", "/trading/v1/options/accounts")
            accounts = data.get("data", []) if isinstance(data, dict) else []
            if accounts:
                acc = self._pick_account(accounts)
                bal = float(acc.get("balance", 0.0))
                self._authorized_info["balance"] = bal
                return bal
            return None
        resp = self._send_rpc({"balance": 1})
        bal_obj = resp.get("balance", {})
        if isinstance(bal_obj, dict) and "balance" in bal_obj:
            bal = float(bal_obj["balance"])
            self._authorized_info["balance"] = bal
            return bal
        return None

    def get_active_symbols(self) -> list[dict[str, Any]]:
        resp = self._send_rpc({"active_symbols": "brief"})
        raw_syms = resp.get("active_symbols", [])
        out: list[dict[str, Any]] = []
        for s in raw_syms:
            sym_code = str(s.get("underlying_symbol") or s.get("symbol") or "")
            if not sym_code:
                continue
            out.append(
                {
                    "name": sym_code,
                    "description": str(s.get("underlying_symbol_name") or s.get("display_name") or sym_code),
                    "category": str(s.get("market") or s.get("market_display_name") or "Deriv"),
                    "visible": True,
                }
            )
        return out

    def get_ticks_history(
        self,
        symbol: str,
        count: int = 200,
        granularity: int = 0,
        end: int | str = "latest",
        start: int | None = None,
    ) -> list[TickRecord]:
        gran = int(granularity or 0)
        req: dict[str, Any] = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": min(5000, max(1, int(count))),
            "end": str(end),
            "style": "candles" if gran > 0 else "ticks",
        }
        if start is not None:
            req["start"] = int(start)
        if gran > 0:
            req["granularity"] = gran
        resp = self._send_rpc(req)
        records: list[TickRecord] = []
        if gran > 0:
            candles = resp.get("candles", [])
            for c in candles:
                p = float(c.get("close", 0.0))
                t_msc = int(c.get("epoch", 0)) * 1000
                records.append(
                    TickRecord(
                        time_msc=t_msc,
                        bid=p,
                        ask=p,
                        last=p,
                        volume_real=0.0,
                        tick_volume=1.0,
                        flags=0,
                    )
                )
            return records
        hist = resp.get("history", {})
        prices = hist.get("prices", [])
        times = hist.get("times", [])
        for p_raw, t_raw in zip(prices, times):
            p = float(p_raw)
            t_msc = int(t_raw) * 1000
            records.append(
                TickRecord(
                    time_msc=t_msc,
                    bid=p,
                    ask=p,
                    last=p,
                    volume_real=0.0,
                    tick_volume=1.0,
                    flags=0,
                )
            )
        return records

    _NON_FATAL_CONTRACT_ERRORS = (
        "TradingDurationNotAllowed",
        "Trading is not offered for this duration",
        "MarketIsClosed",
        "ContractCreationSuspended",
        "InvalidSymbol",
    )

    @classmethod
    def _is_contract_unavailable_error(cls, err_txt: str) -> bool:
        low = err_txt.lower()
        return any(marker.lower() in low for marker in cls._NON_FATAL_CONTRACT_ERRORS)

    def get_contracts_for(self, symbol: str, use_cache: bool = True) -> list[dict[str, Any]] | None:
        """Fetch currently available contracts for `underlying_symbol` via `contracts_for`."""
        now = time.time()
        if use_cache:
            with self._lock:
                cached = self._contracts_for_cache.get(symbol)
                if cached and (now - cached[0]) < self._contracts_for_cache_ttl:
                    return list(cached[1])
        resp = self._send_rpc({"contracts_for": symbol})
        if not isinstance(resp, dict) or "contracts_for" not in resp:
            return None
        cf = resp.get("contracts_for")
        if not isinstance(cf, dict):
            return None
        available = cf.get("available")
        if not isinstance(available, list):
            return None
        items = [dict(item) for item in available if isinstance(item, dict)]
        with self._lock:
            self._contracts_for_cache[symbol] = (now, items)
        return list(items)

    def supports_multiplier_contract(self, symbol: str, contract_type: str) -> tuple[bool, str]:
        """Verify via `contracts_for` whether `contract_type` is currently offered for `symbol`."""
        try:
            available = self.get_contracts_for(symbol)
        except DerivRateLimitError:
            return True, ""
        except RuntimeError as exc:
            err_txt = str(exc)
            if self._is_contract_unavailable_error(err_txt):
                return False, f"[Deriv] Contrato/duração indisponível para {symbol}: {err_txt}"
            return True, ""

        if available is None:
            return True, ""
        if not available:
            return False, f"[Deriv] Nenhum contrato disponível para {symbol} no momento (mercado fechado ou restrito)."

        target = contract_type.upper()
        if any(str(item.get("contract_type", "")).upper() == target for item in available):
            return True, ""
        return False, f"[Deriv] Contrato {target} indisponível para {symbol} no momento (contracts_for)."

    def place_multiplier_order(
        self,
        symbol: str,
        is_buy: bool,
        stake: float,
        multiplier: int = 100,
        sl_amount: float | None = None,
        tp_amount: float | None = None,
    ) -> tuple[bool, str]:
        contract_type = "MULTUP" if is_buy else "MULTDOWN"
        currency = str(self._authorized_info.get("currency", "USD"))
        proposal_req: dict[str, Any] = {
            "proposal": 1,
            "amount": round(max(1.0, float(stake)), 2),
            "basis": "stake",
            "contract_type": contract_type,
            "currency": currency,
            "multiplier": int(multiplier),
            "underlying_symbol": symbol,
        }
        limit_order: dict[str, Any] = {}
        if sl_amount and sl_amount > 0:
            limit_order["stop_loss"] = round(min(float(stake) * 0.95, float(sl_amount)), 2)
        if tp_amount and tp_amount > 0:
            limit_order["take_profit"] = round(float(tp_amount), 2)
        if limit_order:
            proposal_req["limit_order"] = limit_order

        self.last_order_lifecycle = {
            "stage": "ORDER_REQUESTED",
            "symbol": symbol,
            "contract_type": contract_type,
            "stake": round(max(1.0, float(stake)), 2),
            "multiplier": int(multiplier),
            "timestamp": time.time(),
        }
        supported, unavailable_reason = self.supports_multiplier_contract(symbol, contract_type)
        if not supported:
            self.last_order_lifecycle["stage"] = "CONTRACT_UNAVAILABLE"
            return False, unavailable_reason
        try:
            prop_resp = self._send_rpc(proposal_req)
        except DerivRateLimitError as exc:
            self.last_order_lifecycle["stage"] = "RATE_LIMITED"
            return False, f"[Deriv] RateLimit ativo: {exc}"
        except RuntimeError as exc:
            err_txt = str(exc)
            if self._is_contract_unavailable_error(err_txt):
                self.last_order_lifecycle["stage"] = "CONTRACT_UNAVAILABLE"
                return False, f"[Deriv] Contrato/duração indisponível para {symbol}: {err_txt}"
            if "Multiplier is not in acceptable range" in err_txt and "Accepts" in err_txt:
                tail = err_txt.split("Accepts", 1)[1]
                accepted = [int(m) for m in re.findall(r"\d+", tail)]
                if accepted:
                    chosen = min(accepted, key=lambda x: abs(x - int(multiplier)))
                    multiplier = chosen
                    proposal_req["multiplier"] = chosen
                    self.last_order_lifecycle["multiplier"] = chosen
                    try:
                        prop_resp = self._send_rpc(proposal_req)
                    except DerivRateLimitError as rl_exc:
                        self.last_order_lifecycle["stage"] = "RATE_LIMITED"
                        return False, f"[Deriv] RateLimit ativo: {rl_exc}"
                    except RuntimeError as retry_exc:
                        retry_txt = str(retry_exc)
                        if self._is_contract_unavailable_error(retry_txt):
                            self.last_order_lifecycle["stage"] = "CONTRACT_UNAVAILABLE"
                            return False, f"[Deriv] Contrato/duração indisponível para {symbol}: {retry_txt}"
                        raise
                else:
                    raise
            else:
                raise
        prop = prop_resp.get("proposal", {})
        prop_id = prop.get("id")
        if not prop_id:
            self.last_order_lifecycle["stage"] = "ORDER_ERROR"
            return False, f"[Deriv] Proposta recusada para {symbol}: {prop_resp}"

        self.last_order_lifecycle["stage"] = "PROPOSAL_VALIDATED"
        self.last_order_lifecycle["proposal_id"] = prop_id
        ask_price = float(prop.get("ask_price", stake))
        buy_req: dict[str, Any] = {"buy": prop_id, "price": round(ask_price * 1.05, 2)}
        if self._reader_active:
            buy_req["subscribe"] = 1
        try:
            buy_resp = self._send_rpc(buy_req)
        except Exception as exc:
            # Never auto-retry buy on timeout/disconnect without reconciling portfolio first
            self.last_order_lifecycle["stage"] = "RECONCILIATION_REQUIRED"
            return False, f"[Deriv] Compra em {symbol} requer reconciliação (sem reenvio automático): {exc}"

        buy_data = buy_resp.get("buy", {})
        cid = buy_data.get("contract_id")
        if cid:
            self.last_order_lifecycle["stage"] = "CONTRACT_OPEN"
            self.last_order_lifecycle["contract_id"] = cid
            if self._reader_active:
                spot = float(prop.get("spot", 0.0) or 0.0)
                init_poc = {
                    "contract_id": cid,
                    "underlying_symbol": symbol,
                    "contract_type": contract_type,
                    "buy_price": float(buy_data.get("buy_price", stake) or stake),
                    "entry_spot": spot,
                    "current_spot": spot,
                    "profit": 0.0,
                    "limit_order": {
                        "stop_loss": {"order_amount": limit_order.get("stop_loss", 0.0)},
                        "take_profit": {"order_amount": limit_order.get("take_profit", 0.0)},
                    },
                }
                with self._stream_lock:
                    self._stream_contracts[str(cid)] = init_poc
                    self._subscribed_cids.add(str(cid))
            return True, f"[Deriv] Multiplier {contract_type} ({multiplier}x) aberto em {symbol} | Contrato #{cid}"
        self.last_order_lifecycle["stage"] = "ORDER_ERROR"
        return False, f"[Deriv] Falha na compra em {symbol}: {buy_resp}"

    def get_open_contracts(self) -> list[dict[str, Any]]:
        try:
            port_resp = self._send_rpc({"portfolio": 1})
            contracts = port_resp.get("portfolio", {}).get("contracts", [])
        except DerivRateLimitError:
            with self._stream_lock:
                if self._stream_contracts:
                    return [self._format_contract_position(poc) for poc in self._stream_contracts.values()]
                return [
                    self._format_contract_position(poc)
                    for _, poc in self._poc_cache.values()
                    if not self._is_contract_closed(poc)
                ]

        now = time.time()
        active_cids: set[str] = set()
        positions: list[dict[str, Any]] = []
        rate_limited = self.rate_limiter.is_endpoint_blocked("proposal_open_contract", now=now) > 0.0
        uncached_fetches = 0
        max_uncached_per_call = 5

        for c in contracts:
            cid = str(c.get("contract_id", ""))
            if not cid:
                continue
            active_cids.add(cid)

            poc: dict[str, Any] | None = None
            with self._stream_lock:
                stream_poc = self._stream_contracts.get(cid)
                cached_entry = self._poc_cache.get(cid)
                already_sub = cid in self._subscribed_cids

            if stream_poc is not None:
                poc = stream_poc
            elif cached_entry is not None and (now - cached_entry[0]) < self._poc_cache_ttl:
                poc = cached_entry[1]
            elif not rate_limited and uncached_fetches < max_uncached_per_call:
                uncached_fetches += 1
                req: dict[str, Any] = {"proposal_open_contract": 1, "contract_id": int(cid)}
                if self._reader_active and not already_sub:
                    req["subscribe"] = 1
                try:
                    poc_resp = self._send_rpc(req)
                    poc = poc_resp.get("proposal_open_contract", {}) or c
                    with self._stream_lock:
                        self._poc_cache[cid] = (time.time(), poc)
                        if self._reader_active and req.get("subscribe") == 1 and not self._is_contract_closed(poc):
                            self._stream_contracts[cid] = poc
                            self._subscribed_cids.add(cid)
                except DerivAuthError:
                    raise
                except DerivRateLimitError:
                    # Stop hammering proposal_open_contract for remaining contracts immediately
                    rate_limited = True
                    poc = cached_entry[1] if cached_entry is not None else c
                except Exception:
                    poc = cached_entry[1] if cached_entry is not None else c
            else:
                poc = cached_entry[1] if cached_entry is not None else c

            if self._is_contract_closed(poc):
                continue
            positions.append(self._format_contract_position(poc, fallback=c))

        with self._stream_lock:
            for stale_cid in [k for k in self._stream_contracts if k not in active_cids]:
                self._stream_contracts.pop(stale_cid, None)
                self._subscribed_cids.discard(stale_cid)

        return positions

    def close_contract(self, contract_id: str | int) -> tuple[bool, str]:
        try:
            cid_int = int(contract_id)
        except (TypeError, ValueError):
            return False, f"[Deriv] ID de contrato inválido: {contract_id}"
        try:
            resp = self._send_rpc({"sell": cid_int, "price": 0})
        except DerivRateLimitError as exc:
            return False, f"[Deriv] RateLimit ativo ao encerrar #{contract_id}: {exc}"
        except Exception as exc:
            err_lower = str(exc).lower()
            if "betexpired" in err_lower or "has expired" in err_lower or "already been sold" in err_lower or "already sold" in err_lower:
                with self._stream_lock:
                    self._stream_contracts.pop(str(contract_id), None)
                    self._poc_cache.pop(str(contract_id), None)
                    self._subscribed_cids.discard(str(contract_id))
                return True, f"[Deriv] Contrato #{contract_id} já estava encerrado/expirado na corretora."
            return False, f"[Deriv] Erro ao encerrar #{contract_id}: {exc}"
        sold = resp.get("sell", {})
        if sold:
            with self._stream_lock:
                self._stream_contracts.pop(str(contract_id), None)
                self._poc_cache.pop(str(contract_id), None)
                self._subscribed_cids.discard(str(contract_id))
            return True, f"[Deriv] Contrato #{contract_id} encerrado (Valor: {sold.get('sold_for', 0)})."
        return False, f"[Deriv] Falha ao encerrar #{contract_id}: {resp}"
