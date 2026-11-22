"""Pure-Python Deriv WebSocket API Client (wss://ws.derivws.com/websockets/v3).
Supports 100% free live/demo trading on Deriv Multipliers (MULTUP / MULTDOWN)
with zero MetaTrader terminal and zero paid third-party gateways.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

from prado_linux.flow_math import TickRecord


class DerivClient:
    """Thread-safe WebSocket RPC client for Deriv API."""

    def __init__(
        self,
        token: str,
        app_id: str = "1089",
        rpc_transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.token = token.strip()
        self.app_id = (app_id or "1089").strip()
        self._rpc_transport = rpc_transport
        self._lock = threading.Lock()
        self._ws: Any = None
        self._authorized_info: dict[str, Any] = {}

    DERIV_ENDPOINTS = (
        "wss://red.derivws.com/websockets/v3",
        "wss://green.derivws.com/websockets/v3",
        "wss://blue.derivws.com/websockets/v3",
        "wss://ws.derivws.com/websockets/v3",
    )

    @property
    def ws_url(self) -> str:
        return f"{self.DERIV_ENDPOINTS[0]}?app_id={self.app_id}"

    def _open_connection(self) -> Any:
        import websocket  # type: ignore

        last_exc: Exception | None = None
        for base in self.DERIV_ENDPOINTS:
            url = f"{base}?app_id={self.app_id}"
            try:
                return websocket.create_connection(
                    url,
                    origin="https://app.deriv.com",
                    header=["User-Agent: Mozilla/5.0"],
                    timeout=10,
                )
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"Falha ao conectar nos servidores WebSocket Deriv: {last_exc}")

    def _send_rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._rpc_transport is not None:
            resp = self._rpc_transport(payload)
            if isinstance(resp, dict) and resp.get("error"):
                err = resp["error"]
                raise RuntimeError(f"Deriv API ({err.get('code', 'ERR')}): {err.get('message', err)}")
            return resp

        with self._lock:
            if self._ws is None or not getattr(self._ws, "connected", False):
                self._ws = self._open_connection()
                if self.token and "authorize" not in payload:
                    self._ws.send(json.dumps({"authorize": self.token}))
                    auth_raw = self._ws.recv()
                    auth_resp = json.loads(auth_raw)
                    if auth_resp.get("error"):
                        self._ws.close()
                        self._ws = None
                        err = auth_resp["error"]
                        raise RuntimeError(f"Deriv Auth ({err.get('code', 'ERR')}): {err.get('message', err)}")
                    self._authorized_info = auth_resp.get("authorize", {})

            self._ws.send(json.dumps(payload))
            raw = self._ws.recv()
            resp = json.loads(raw)
            if resp.get("error"):
                err = resp["error"]
                raise RuntimeError(f"Deriv API ({err.get('code', 'ERR')}): {err.get('message', err)}")
            return resp

    def close(self) -> None:
        with self._lock:
            if self._ws is not None:
                try:
                    self._ws.close()
                except Exception:
                    pass
                self._ws = None

    def authorize(self) -> dict[str, Any]:
        resp = self._send_rpc({"authorize": self.token})
        auth = resp.get("authorize", {})
        self._authorized_info = auth
        return auth

    def get_active_symbols(self) -> list[dict[str, Any]]:
        resp = self._send_rpc({"active_symbols": "brief", "product_type": "basic"})
        raw_syms = resp.get("active_symbols", [])
        out: list[dict[str, Any]] = []
        for s in raw_syms:
            out.append(
                {
                    "name": str(s.get("symbol", "")),
                    "description": str(s.get("display_name", s.get("symbol", ""))),
                    "category": str(s.get("market_display_name", "Deriv")),
                    "visible": True,
                }
            )
        return out

    def get_ticks_history(self, symbol: str, count: int = 200) -> list[TickRecord]:
        resp = self._send_rpc(
            {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": int(count),
                "end": "latest",
                "style": "ticks",
            }
        )
        hist = resp.get("history", {})
        prices = hist.get("prices", [])
        times = hist.get("times", [])
        records: list[TickRecord] = []
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
            "symbol": symbol,
        }
        limit_order: dict[str, Any] = {}
        if sl_amount and sl_amount > 0:
            limit_order["stop_loss"] = round(min(float(stake) * 0.95, float(sl_amount)), 2)
        if tp_amount and tp_amount > 0:
            limit_order["take_profit"] = round(float(tp_amount), 2)
        if limit_order:
            proposal_req["limit_order"] = limit_order

        prop_resp = self._send_rpc(proposal_req)
        prop = prop_resp.get("proposal", {})
        prop_id = prop.get("id")
        if not prop_id:
            return False, f"[Deriv] Proposta recusada para {symbol}: {prop_resp}"

        ask_price = float(prop.get("ask_price", stake))
        buy_resp = self._send_rpc({"buy": prop_id, "price": round(ask_price * 1.05, 2)})
        buy_data = buy_resp.get("buy", {})
        cid = buy_data.get("contract_id")
        if cid:
            return True, f"[Deriv] Multiplier {contract_type} ({multiplier}x) aberto em {symbol} | Contrato #{cid}"
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
                    "symbol": str(poc.get("underlying", c.get("symbol", ""))),
                    "type": "BUY" if is_buy else "SELL",
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
        resp = self._send_rpc({"sell": int(contract_id), "price": 0})
        sold = resp.get("sell", {})
        if sold:
            return True, f"[Deriv] Contrato #{contract_id} encerrado (Valor: {sold.get('sold_for', 0)})."
        return False, f"[Deriv] Falha ao encerrar #{contract_id}: {resp}"
