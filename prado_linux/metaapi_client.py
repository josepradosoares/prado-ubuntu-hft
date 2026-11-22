"""Zero-dependency pure-Python MetaApi Cloud REST Client.
Allows the Ubuntu VPS to trade MetaTrader 5 accounts 100% via Python HTTPS
without running any MetaTrader 5 terminal anywhere (neither on PC nor on VPS).
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROVISIONING_BASE = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai"


def default_http_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(raw)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            body = json.loads(raw) if raw else {"message": str(exc)}
        except Exception:
            body = {"message": raw or str(exc)}
        return exc.code, body
    except URLError as exc:
        return 503, {"message": f"Erro de rede MetaApi: {exc.reason}"}


class MetaApiClient:
    """Pure Python REST client for MetaApi Cloud Trading & Market Data APIs."""

    def __init__(
        self,
        token: str,
        account_id: str = "",
        region: str = "london",
        transport: Callable[[str, str, dict[str, str], dict[str, Any] | None], tuple[int, Any]] | None = None,
    ) -> None:
        self.token = token.strip()
        self.account_id = account_id.strip()
        self.region = (region or "london").strip()
        self._transport = transport or default_http_transport

    @property
    def client_base(self) -> str:
        return f"https://mt-client-api-v1.{self.region}.agiliumtrade.ai"

    def _headers(self) -> dict[str, str]:
        return {
            "auth-token": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
        return self._transport(method, url, self._headers(), payload)

    def provision_mt5_account(
        self,
        login: str,
        password: str,
        server: str,
        name: str,
        magic: int = 20261121,
    ) -> tuple[bool, dict[str, Any]]:
        """Register & deploy an MT5 account on MetaApi Cloud so no MT5 terminal is needed locally."""
        url = f"{PROVISIONING_BASE}/users/current/accounts"
        payload = {
            "name": name or f"Prado_{login}",
            "type": "cloud",
            "login": str(login),
            "password": password,
            "server": server,
            "platform": "mt5",
            "magic": int(magic),
            "application": "MetaApi",
            "reliability": "regular",
        }
        headers = self._headers()
        headers["transaction-id"] = f"prado_{int(time.time() * 1000)}"
        code, body = self._transport("POST", url, headers, payload)
        if code in (200, 201, 202) and isinstance(body, dict) and body.get("id"):
            self.account_id = str(body["id"])
            return True, body
        return False, body if isinstance(body, dict) else {"message": str(body)}

    def get_account_information(self) -> dict[str, Any]:
        url = f"{self.client_base}/users/current/accounts/{self.account_id}/account-information"
        code, body = self._request("GET", url)
        if code == 200 and isinstance(body, dict):
            return body
        raise RuntimeError(f"MetaApi account-information ({code}): {body}")

    def get_positions(self) -> list[dict[str, Any]]:
        url = f"{self.client_base}/users/current/accounts/{self.account_id}/positions"
        code, body = self._request("GET", url)
        if code == 200 and isinstance(body, list):
            return body
        return []

    def get_symbols(self) -> list[str]:
        url = f"{self.client_base}/users/current/accounts/{self.account_id}/symbols"
        code, body = self._request("GET", url)
        if code == 200 and isinstance(body, list):
            return [str(s) for s in body]
        return []

    def get_current_tick(self, symbol: str) -> dict[str, Any] | None:
        from urllib.parse import quote

        sym_enc = quote(symbol, safe="")
        url = f"{self.client_base}/users/current/accounts/{self.account_id}/symbols/{sym_enc}/current-tick"
        code, body = self._request("GET", url)
        if code == 200 and isinstance(body, dict):
            return body
        return None

    def place_order(
        self,
        symbol: str,
        is_buy: bool,
        volume: float,
        sl: float | None = None,
        tp: float | None = None,
        comment: str = "PradoHFT",
    ) -> tuple[bool, str]:
        url = f"{self.client_base}/users/current/accounts/{self.account_id}/trade"
        payload: dict[str, Any] = {
            "actionType": "ORDER_TYPE_BUY" if is_buy else "ORDER_TYPE_SELL",
            "symbol": symbol,
            "volume": float(volume),
            "comment": comment[:28],
        }
        if sl and sl > 0:
            payload["stopLoss"] = round(float(sl), 5)
        if tp and tp > 0:
            payload["takeProfit"] = round(float(tp), 5)

        code, body = self._request("POST", url, payload)
        if code in (200, 201) and isinstance(body, dict):
            ret = body.get("numericCode")
            if ret in (None, 10008, 10009):
                ord_id = body.get("orderId") or body.get("positionId") or "OK"
                return True, f"[MetaApi] Ordem executada em {symbol} (ID: {ord_id})"
            return False, f"[MetaApi] Rejeitada ({ret}): {body.get('message', body)}"
        return False, f"[MetaApi] Erro HTTP {code}: {body}"

    def close_position(self, position_id: str) -> tuple[bool, str]:
        url = f"{self.client_base}/users/current/accounts/{self.account_id}/trade"
        payload = {
            "actionType": "POSITION_CLOSE_ID",
            "positionId": str(position_id),
        }
        code, body = self._request("POST", url, payload)
        if code in (200, 201):
            return True, f"[MetaApi] Posição #{position_id} encerrada."
        return False, f"[MetaApi] Erro ao fechar #{position_id}: {body}"
