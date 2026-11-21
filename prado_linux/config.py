"""Configuration persistence for Prado Institutional HFT Ubuntu Server (Accounts, Categories & Multi-Bot Fleet)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import secrets
from typing import Any

from prado_linux.auth import hash_password

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "B3 Futuros (Mini Índice & Dólar)": ["WIN$N", "WDO$N", "IND$N", "DOL$N"],
    "B3 Ações Blue Chips": ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "B3SA3", "WEGE3"],
    "Criptomoedas 24/7": ["BTCUSD#", "ETHUSD#", "SOLUSD#", "DOGEUSD#", "Crypto_10#"],
    "Índices Globais & Wall Street": ["US100Cash#", "US500Cash#", "US30Cash#", "GER40Cash#", "HK50Cash#"],
    "Forex & Commodities": ["EURUSD", "GBPUSD", "USDJPY", "GOLD#", "SILVER#", "WTI#"],
}


@dataclass
class PradoServerConfig:
    # Web Login Auth
    admin_username: str = "admin"
    admin_password_hash: str = ""
    secret_key: str = ""
    web_port: int = 8080

    # Primary MetaTrader 5 Credentials & Connection Mode
    mt5_connection_mode: str = "AUTO_MT5_WINE"
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_terminal_path: str = ""
    rpyc_host: str = "127.0.0.1"
    rpyc_port: int = 18812
    metaapi_token: str = ""
    metaapi_account_id: str = ""

    # Multiple Saved MT5 Accounts
    accounts: list[dict[str, Any]] = field(default_factory=list)

    # Symbol Selection Mode ("PRINCIPAIS" vs "TODOS") and Custom Broker Categories
    symbol_selection_mode: str = "PRINCIPAIS"
    custom_categories: dict[str, list[str]] = field(default_factory=lambda: dict(DEFAULT_CATEGORIES))

    # Active Running / Configured Robot Fleet
    bots: list[dict[str, Any]] = field(default_factory=list)

    # Operational Rules from Wall Street Institutional Broker Transcript ("Fio")
    auto_trading_enabled: bool = True
    operation_mode: str = "BOTH"
    active_symbols: list[str] = field(
        default_factory=lambda: ["WIN$N", "WDO$N", "BTCUSD#", "US100Cash#", "EURUSD"]
    )
    correlated_basket: list[str] = field(
        default_factory=lambda: ["PETR4", "VALE3", "Crypto_10#"]
    )

    # VWAP & Order Flow Aggression Calibration
    window_ticks: int = 120
    zscore_threshold: float = 1.8
    imbalance_threshold: float = 0.35
    revert_sigma: float = 2.0
    correlation_block_threshold: float = 0.40
    poll_interval_sec: float = 0.5

    # Risk Guard & Execution ("HFT sempre dorme zerado")
    default_lot_size: float = 1.0
    sl_sigma_mult: float = 1.0
    tp_sigma_mult: float = 1.8
    breakeven_trigger_sigma: float = 0.7
    trailing_step_sigma: float = 0.4
    max_daily_loss_money: float = 500.0
    daily_target_money: float = 1000.0
    trading_start_time: str = "09:05"
    trading_end_time: str = "17:20"
    eod_flatten_time: str = "17:35"
    enforce_eod_flatten: bool = True
    magic_number: int = 20261121


def load_config(config_path: Path) -> PradoServerConfig:
    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        cfg = PradoServerConfig(**{k: v for k, v in raw.items() if k in PradoServerConfig.__dataclass_fields__})
    else:
        cfg = PradoServerConfig()

    changed = False
    if not cfg.admin_password_hash:
        cfg.admin_password_hash = hash_password("prado2026")
        changed = True
    if not cfg.secret_key:
        cfg.secret_key = secrets.token_hex(32)
        changed = True
    if not cfg.custom_categories:
        cfg.custom_categories = dict(DEFAULT_CATEGORIES)
        changed = True

    if changed or not config_path.exists():
        save_config(cfg, config_path)
    return cfg


def save_config(cfg: PradoServerConfig, config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
