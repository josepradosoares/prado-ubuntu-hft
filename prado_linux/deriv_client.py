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


class DerivAuthError(RuntimeError):
    """Structured authentication error carrying a canonical auth_state."""

    def __init__(self, auth_state: str, message: str) -> None:
        super().__init__(message)
        self.auth_state = auth_state


class DerivRateLimitError(RuntimeError):
    """Raised when local or remote RateLimit blocks a request."""


class DerivRateLimiter:
    """Centralized thread-safe sliding-window rate limiter with exponential backoff + jitter."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ws_windows: dict[str, deque[float]] = {k: deque() for k in WS_BUDGETS}
        self._ws_blocked_until: dict[str, float] = {}
        self._rest_window: deque[float] = deque()
        self._rest_blocked_until: float = 0.0
        self._blocked_until: float = 0.0
        self._consecutive_429: int = 0
        self._last_error: str = ""

    def _prune(self, dq: deque[float], now: float, horizon: float = 3600.0) -> None:
        cutoff = now - horizon
        while dq and dq[0] < cutoff:
            dq.popleft()

    def acquire_ws(self, group: str, now: float | None = None) -> None:
        if group == "ping":
            return
        t = time.time() if now is None else now
        with self._lock:
            grp_blocked = max(self._blocked_until, self._ws_blocked_until.get(group, 0.0))
            if t < grp_blocked:
                wait = round(grp_blocked - t, 2)
                raise DerivRateLimitError(
                    f"RateLimit ativo (cooldown {wait}s): {self._last_error or 'aguardando janela'}"
                )
            dq = self._ws_windows.setdefault(group, deque())
            self._prune(dq, t, 3600.0)
            per_min, per_hour = WS_BUDGETS.get(group, WS_BUDGETS["other"])
            recent_min = sum(1 for ts in dq if ts >= t - 60.0)
            if recent_min >= per_min or len(dq) >= per_hour:
                self._ws_blocked_until[group] = t + 2.0
                self._last_error = f"Orçamento local WS '{group}' atingido ({recent_min}/{per_min} min)"
                raise DerivRateLimitError(self._last_error)
            dq.append(t)

    def acquire_rest(self, now: float | None = None) -> None:
        t = time.time() if now is None else now
        with self._lock:
            rest_blocked = max(self._blocked_until, self._rest_blocked_until)
            if t < rest_blocked:
                wait = round(rest_blocked - t, 2)
                raise DerivRateLimitError(
                    f"RateLimit REST ativo (cooldown {wait}s): {self._last_error or 'aguardando janela'}"
                )
            self._prune(self._rest_window, t, 60.0)
            if len(self._rest_window) >= REST_USER_PER_MIN:
                self._rest_blocked_until = t + 2.0
                self._last_error = f"Orçamento REST atingido ({len(self._rest_window)}/{REST_USER_PER_MIN} min)"
                raise DerivRateLimitError(self._last_error)
            self._rest_window.append(t)

    def record_remote_rate_limit(self, message: str = "", now: float | None = None) -> float:
        t = time.time() if now is None else now
        with self._lock:
            self._consecutive_429 += 1
            base = min(60.0, 2.0 ** min(self._consecutive_429, 5))
            jitter = random.uniform(0.1, 1.0)
            delay = base + jitter
            self._blocked_until = max(self._blocked_until, t + delay)
            self._last_error = message or "Deriv API RateLimit"
            return delay

    def record_success(self) -> None:
        with self._lock:
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
            blocked = t < self._blocked_until
            return {
                "state": "BLOCKED" if blocked else "NORMAL",
                "cooldown_seconds": round(max(0.0, self._blocked_until - t), 2),
                "ws_per_min": counts_min,
                "rest_per_min": len(self._rest_window),
                "last_error": self._last_error,
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
            self.rate_limiter.record_success()
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
                self.rate_limiter.record_success()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 429:
                self.rate_limiter.record_remote_rate_limit(f"HTTP 429: {body[:120]}")
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

                def send(self, data: str) -> None:
                    self._inner.send(data)

                def recv(self) -> str:
                    res = self._inner.recv(timeout=10)
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

    def _open_connection(self) -> Any:
        self.connection_state = "CONNECTING"
        if self.is_public_client:
            try:
                ws = self._open_ws_url(PUBLIC_WS_URL)
                self._ws_url_active = PUBLIC_WS_URL
                self.connection_state = "CONNECTED"
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
            return ws

        # Legacy classic token flow (only when non-PAT token is used)
        last_exc: Exception | None = None
        for base in self.DERIV_ENDPOINTS:
            url = f"{base}?app_id={self.app_id}"
            try:
                ws = self._open_ws_url(url)
                self._ws_url_active = url
                self.connection_state = "CONNECTED"
                return ws
            except Exception as exc:
                last_exc = exc
        self.connection_state = "ERROR"
        raise RuntimeError(f"Falha ao conectar nos servidores WebSocket Deriv: {last_exc}")

    def _handle_rpc_error(self, err: dict[str, Any]) -> None:
        code = str(err.get("code", "ERR"))
        msg = str(err.get("message", err))
        if code in ("RateLimit", "TooManyRequests"):
            self.rate_limiter.record_remote_rate_limit(msg)
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
        self.rate_limiter.acquire_ws(group)

        req_payload = dict(payload)
        if "req_id" not in req_payload:
            req_payload["req_id"] = self._next_req_id()

        if self._rpc_transport is not None:
            resp = self._rpc_transport(req_payload)
            if isinstance(resp, dict) and resp.get("error"):
                self._handle_rpc_error(resp["error"])
            self.rate_limiter.record_success()
            return resp

        with self._lock:
            is_buy_call = "buy" in req_payload
            max_attempts = 1 if is_buy_call else 2
            last_transport_exc: Exception | None = None
            raw = ""
            for attempt in range(max_attempts):
                if (
                    self._ws is not None
                    and (self.is_pat_token or len(self.token) > 40)
                    and self._otp_expires_at > 0
                    and time.time() >= self._otp_expires_at
                ):
                    self.close()
                try:
                    if self._ws is None or not getattr(self._ws, "connected", False):
                        self._ws = self._open_connection()
                        # Legacy classic token handshake only; modern OTP connections NEVER send authorize
                        if self.token and not self.is_pat_token and len(self.token) <= 40 and "authorize" not in req_payload:
                            self._ws.send(json.dumps({"authorize": self.token, "req_id": self._next_req_id()}))
                            auth_raw = self._ws.recv()
                            auth_resp = json.loads(auth_raw)
                            if auth_resp.get("error"):
                                self.close()
                                self._handle_rpc_error(auth_resp["error"])
                            self._authorized_info = auth_resp.get("authorize", {})
                            self.auth_state = "AUTHENTICATED"

                    self._ws.send(json.dumps(req_payload))
                    expected_req_id = req_payload.get("req_id")
                    resp = None
                    for _ in range(5):
                        raw = self._ws.recv()
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

            if last_transport_exc is not None:
                raise RuntimeError(f"Conexão WebSocket interrompida: {last_transport_exc}")

            if resp.get("error"):
                self._handle_rpc_error(resp["error"])
            self.rate_limiter.record_success()
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
            if self._ws is not None:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None
            self.connection_state = "DISCONNECTED"

    def reconnect(self) -> bool:
        """Controlled reconnection: closes stale WS and requests fresh OTP if needed."""
        with self._lock:
            self.connection_state = "RECONNECTING"
            if self._ws is not None:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None
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

    def get_ticks_history(self, symbol: str, count: int = 200, granularity: int = 0) -> list[TickRecord]:
        gran = int(granularity or 0)
        req: dict[str, Any] = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": int(count),
            "end": "latest",
            "style": "candles" if gran > 0 else "ticks",
        }
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
        try:
            prop_resp = self._send_rpc(proposal_req)
        except RuntimeError as exc:
            err_txt = str(exc)
            if "Multiplier is not in acceptable range" in err_txt and "Accepts" in err_txt:
                tail = err_txt.split("Accepts", 1)[1]
                accepted = [int(m) for m in re.findall(r"\d+", tail)]
                if accepted:
                    chosen = min(accepted, key=lambda x: abs(x - int(multiplier)))
                    multiplier = chosen
                    proposal_req["multiplier"] = chosen
                    self.last_order_lifecycle["multiplier"] = chosen
                    prop_resp = self._send_rpc(proposal_req)
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
        try:
            buy_resp = self._send_rpc({"buy": prop_id, "price": round(ask_price * 1.05, 2)})
        except Exception as exc:
            # Never auto-retry buy on timeout/disconnect without reconciling portfolio first
            self.last_order_lifecycle["stage"] = "RECONCILIATION_REQUIRED"
            return False, f"[Deriv] Compra em {symbol} requer reconciliação (sem reenvio automático): {exc}"

        buy_data = buy_resp.get("buy", {})
        cid = buy_data.get("contract_id")
        if cid:
            self.last_order_lifecycle["stage"] = "CONTRACT_OPEN"
            self.last_order_lifecycle["contract_id"] = cid
            return True, f"[Deriv] Multiplier {contract_type} ({multiplier}x) aberto em {symbol} | Contrato #{cid}"
        self.last_order_lifecycle["stage"] = "ORDER_ERROR"
        return False, f"[Deriv] Falha na compra em {symbol}: {buy_resp}"

    def get_open_contracts(self) -> list[dict[str, Any]]:
        port_resp = self._send_rpc({"portfolio": 1})
        contracts = port_resp.get("portfolio", {}).get("contracts", [])
        positions: list[dict[str, Any]] = []
        for c in contracts:
            cid = str(c.get("contract_id", ""))
            if not cid:
                continue
            try:
                poc_resp = self._send_rpc({"proposal_open_contract": 1, "contract_id": int(cid)})
                poc = poc_resp.get("proposal_open_contract", {})
            except Exception:
                poc = c
            ctype = str(poc.get("contract_type", c.get("contract_type", "MULTUP"))).upper()
            is_buy = "UP" in ctype or "CALL" in ctype
            lim = poc.get("limit_order") or {}
            sl_amt = float((lim.get("stop_loss") or {}).get("order_amount", 0.0))
            tp_amt = float((lim.get("take_profit") or {}).get("order_amount", 0.0))
            positions.append(
                {
                    "ticket": cid,
                    "symbol": str(poc.get("underlying_symbol") or poc.get("underlying") or c.get("symbol") or ""),
                    "type": "BUY" if is_buy else "SELL",
                    "side": "BUY" if is_buy else "SELL",
                    "volume": float(poc.get("buy_price", c.get("buy_price", 0.0))),
                    "price_open": round(float(poc.get("entry_spot", 0.0)), 6),
                    "price_current": round(float(poc.get("current_spot", 0.0)), 6),
                    "sl": sl_amt,
                    "tp": tp_amt,
                    "profit": round(float(poc.get("profit", 0.0)), 2),
                    "comment": f"Deriv_{ctype}",
                }
            )
        return positions

    def close_contract(self, contract_id: str | int) -> tuple[bool, str]:
        try:
            cid_int = int(contract_id)
        except (TypeError, ValueError):
            return False, f"[Deriv] ID de contrato inválido: {contract_id}"
        try:
            resp = self._send_rpc({"sell": cid_int, "price": 0})
        except Exception as exc:
            return False, f"[Deriv] Erro ao encerrar #{contract_id}: {exc}"
        sold = resp.get("sell", {})
        if sold:
            return True, f"[Deriv] Contrato #{contract_id} encerrado (Valor: {sold.get('sold_for', 0)})."
        return False, f"[Deriv] Falha ao encerrar #{contract_id}: {resp}"
