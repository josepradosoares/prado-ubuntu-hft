"""Configuration persistence for Prado Institutional HFT Ubuntu Server."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import secrets

from prado_linux.auth import hash_password


@dataclass
class PradoServerConfig:
    # Web Login Auth
    admin_username: str = "admin"
    admin_password_hash: str = ""
    secret_key: str = ""
    web_port: int = 8080

    # MetaTrader 5 Credentials & Connection Mode
    # Modes: "AUTO_MT5_WINE" (MT5 local/Wine/rpyc), "METAAPI_CLOUD" (Cloud bridge), "SIMULATION" (Test/Replay)
    mt5_connection_mode: str = "AUTO_MT5_WINE"
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_terminal_path: str = ""
    rpyc_host: str = "127.0.0.1"
    rpyc_port: int = 18812
    metaapi_token: str = ""
    metaapi_account_id: str = ""

    # Operational Rules from Wall Street Institutional Broker Transcript ("Fio")
    auto_trading_enabled: bool = True
    operation_mode: str = "BOTH"  # "BOTH", "TREND_ONLY" (Fala 1 - Trem Institucional), "REVERT_ONLY" (Fala 2 - Giro HFT)
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

    if changed or not config_path.exists():
        save_config(cfg, config_path)
    return cfg


def save_config(cfg: PradoServerConfig, config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
