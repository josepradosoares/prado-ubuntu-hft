"""Configuration persistence for Prado Institutional HFT Ubuntu Server (Deriv Multipliers & Token Vault)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import secrets
from typing import Any

from prado_linux.auth import hash_password

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Índices Sintéticos Volatility (24/7)": ["R_10", "R_25", "R_50", "R_75", "R_100", "1HZ10V", "1HZ50V", "1HZ100V"],
    "Forex Principais": ["frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD", "frxUSDCAD"],
    "Ouro & Commodities": ["frxXAUUSD", "frxXAGUSD"],
    "Criptomoedas (24/7)": ["cryBTCUSD", "cryETHUSD"],
    "Índices Crash & Boom": ["BOOM500", "BOOM1000", "CRASH500", "CRASH1000"],
}

MATH_BOT_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": "WALL_STREET_HYBRID_BOTH",
        "name": "1. Híbrido Institucional Completo (Fala 1: Trem VWAP + Fala 2: Giro HFT ±2σ)",
        "operation_mode": "BOTH",
        "formula": "VWAP = Σ(Pᵢ·Vᵢ)/ΣVᵢ | Z = (μ_w - μ)/(σ/√(w/4)) | Entrada Fluxo (|Z|≥Z_min) + Reversão (|P - VWAP|≥k·σ)",
        "description": "Combina as duas lógicas matemáticas da entrevista do Broker de Wall Street: segue o fluxo institucional a favor da VWAP e opera retorno à média nas bandas externas.",
        "window_ticks": 120,
        "zscore_threshold": 1.8,
        "imbalance_threshold": 0.35,
        "revert_sigma": 2.0,
        "sl_sigma_mult": 1.0,
        "tp_sigma_mult": 1.8,
    },
    {
        "template_id": "FIX_VWAP_TREND_TRAIN",
        "name": "2. Fala 1 — Trem Institucional VWAP (Seguidor Puro de Fluxo de Agressão)",
        "operation_mode": "TREND_ONLY",
        "formula": "Sinal = sign(ΔVol) quando |Z_agressão| ≥ 1.8 ∧ |Imbalance| ≥ 0.35 ∧ sign(P - VWAP) == sign(Z)",
        "description": "Detecta aceleração de fluxo direcional a favor da VWAP e abre Multiplier na direção da tendência.",
        "window_ticks": 100,
        "zscore_threshold": 1.8,
        "imbalance_threshold": 0.35,
        "revert_sigma": 2.5,
        "sl_sigma_mult": 1.0,
        "tp_sigma_mult": 2.2,
    },
    {
        "template_id": "HFT_MEAN_REVERSION_2SIGMA",
        "name": "3. Fala 2 — Giro HFT Provedor de Liquidez (Reversão Matemática à Média ±2σ)",
        "operation_mode": "REVERT_ONLY",
        "formula": "Venda se P ≥ VWAP + 2σ ∧ Imbalance ≤ 0 | Compra se P ≤ VWAP - 2σ ∧ Imbalance ≥ 0 (Alvo = VWAP)",
        "description": "Matemática pura de retorno à média nos extremos de desvio padrão quando o fluxo agressor perde força.",
        "window_ticks": 80,
        "zscore_threshold": 2.0,
        "imbalance_threshold": 0.25,
        "revert_sigma": 2.0,
        "sl_sigma_mult": 0.9,
        "tp_sigma_mult": 1.5,
    },
    {
        "template_id": "ULTRA_SCALPER_ZSCORE_BURST",
        "name": "4. HFT Explosão de Agressão (Scalper Estatístico de Curto Alcance)",
        "operation_mode": "TREND_ONLY",
        "formula": "Janela curta w=50 ticks | Disparo em micro-explosão Z ≥ 2.2 ∧ Imbalance ≥ 0.45 | Alvo rápido 1.2σ",
        "description": "Focado em explosões súbitas de micro-tendência em Índices Volatility 24/7 com realização rápida.",
        "window_ticks": 50,
        "zscore_threshold": 2.2,
        "imbalance_threshold": 0.45,
        "revert_sigma": 2.0,
        "sl_sigma_mult": 0.8,
        "tp_sigma_mult": 1.2,
    },
    {
        "template_id": "STAT_ARB_CORRELATION_BASKET",
        "name": "5. Arbitragem Estatística & Correlação de Cesta (Volatility / Forex / Cripto)",
        "operation_mode": "BOTH",
        "formula": "Bias_Cesta = (1/N)·Σ Imbalance(Ativo_k) | Opera somente alinhado ao vetor matemático da cesta",
        "description": "Cruza a matemática da cesta correlacionada com o desvio padrão da VWAP do ativo-alvo sem precisar abrir nenhum gráfico.",
        "window_ticks": 140,
        "zscore_threshold": 1.6,
        "imbalance_threshold": 0.30,
        "revert_sigma": 1.8,
        "sl_sigma_mult": 1.0,
        "tp_sigma_mult": 1.8,
    },
    {
        "template_id": "GRID_LINEAR_HFT",
        "name": "6. Gradiente Linear — Grid HFT (Escalonamento Só Compra / Só Venda / Ambos)",
        "operation_mode": "GRID_LINEAR",
        "formula": "Entrada a cada ±grid_step pts (até max_grid_levels) | Saída individual ao recuar grid_tp_points",
        "description": "Robô de alta frequência para mercados lateralizados: escolhe Só Compra, Só Venda ou Ambos, escalona ordens a cada passo e realiza lucro nível a nível.",
        "window_ticks": 60,
        "zscore_threshold": 0.0,
        "imbalance_threshold": 0.0,
        "revert_sigma": 1.0,
        "sl_sigma_mult": 1.5,
        "tp_sigma_mult": 1.0,
        "grid_direction": "BUY_ONLY",
        "grid_step_points": 1.5,
        "grid_tp_points": 1.5,
        "max_grid_levels": 5,
    },
]


def deduplicate_accounts(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure no duplicate accounts with same account_id or label+type."""
    by_key: dict[str, dict[str, Any]] = {}
    for acc in accounts:
        key = str(acc.get("account_id", "")).strip() or f"{acc.get('account_type', 'DEMO')}_{acc.get('label', '')}"
        if not key:
            continue
        by_key[key] = acc
    return list(by_key.values())


@dataclass
class PradoServerConfig:
    # Web Login Auth
    admin_username: str = "admin"
    admin_password_hash: str = ""
    secret_key: str = ""
    web_port: int = 8080

    # Deriv API Credentials & Active Account Selection (DEMO vs REAL)
    connection_mode: str = "DERIV_CLOUD"  # "DERIV_CLOUD" or "SIMULATION"
    active_account_id: str = ""
    active_account_type: str = "DEMO"
    deriv_token: str = ""
    deriv_app_id: str = "1089"
    default_stake_usd: float = 10.0
    default_multiplier: int = 100

    # Saved Deriv Token Accounts (Demo & Real Vault)
    accounts: list[dict[str, Any]] = field(default_factory=list)

    # Symbol Selection Mode ("PRINCIPAIS" vs "TODOS") and Custom Categories
    symbol_selection_mode: str = "PRINCIPAIS"
    custom_categories: dict[str, list[str]] = field(default_factory=lambda: dict(DEFAULT_CATEGORIES))

    # Active Running / Configured Robot Fleet
    bots: list[dict[str, Any]] = field(default_factory=list)

    # Backtest Results History
    backtest_history: list[dict[str, Any]] = field(default_factory=list)

    # Operational Rules from Wall Street Institutional Broker Transcript ("Fio")
    auto_trading_enabled: bool = True
    allow_real_trading: bool = False
    operation_mode: str = "BOTH"
    active_symbols: list[str] = field(
        default_factory=lambda: ["R_100", "R_75", "1HZ100V", "frxEURUSD", "cryBTCUSD"]
    )
    correlated_basket: list[str] = field(
        default_factory=lambda: ["R_50", "R_25"]
    )

    # VWAP & Order Flow Aggression Calibration
    window_ticks: int = 120
    zscore_threshold: float = 1.8
    imbalance_threshold: float = 0.35
    revert_sigma: float = 2.0
    correlation_block_threshold: float = 0.40
    poll_interval_sec: float = 1.0

    # Risk Guard
    sl_sigma_mult: float = 1.0
    tp_sigma_mult: float = 1.8
    max_daily_loss_money: float = 500.0
    daily_target_money: float = 1000.0
    max_stake_per_trade: float = 100.0
    max_concurrent_trades: int = 5
    max_total_exposure_usd: float = 500.0
    min_order_interval_sec: float = 3.0


def load_config(config_path: Path) -> PradoServerConfig:
    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        cfg = PradoServerConfig(**{k: v for k, v in raw.items() if k in PradoServerConfig.__dataclass_fields__})
    else:
        cfg = PradoServerConfig()

    env_token = os.environ.get("DERIV_TOKEN", "").strip()
    if env_token and not cfg.deriv_token:
        cfg.deriv_token = env_token
    env_app_id = os.environ.get("DERIV_APP_ID", "").strip()
    if env_app_id and cfg.deriv_app_id == "1089":
        cfg.deriv_app_id = env_app_id
    env_allow_real = os.environ.get("ALLOW_REAL_TRADING", "").strip().lower()
    if env_allow_real in ("1", "true", "yes"):
        cfg.allow_real_trading = True

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

    legacy_mt5 = {
        "WIN$N", "WDO$N", "IND$N", "DOL$N", "BTCUSD#", "US100Cash#", "EURUSD", "Crypto_10#",
        "VALE3", "PETR4", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "B3SA3", "MGLU3", "WEGE3",
    }

    def _is_legacy_mt5(sym: str) -> bool:
        return sym in legacy_mt5 or "#" in sym or "$" in sym

    if any(_is_legacy_mt5(sym) for sym in cfg.active_symbols):
        cfg.active_symbols = [s for s in cfg.active_symbols if not _is_legacy_mt5(s)] or [
            "R_100",
            "R_75",
            "1HZ100V",
            "frxEURUSD",
            "cryBTCUSD",
        ]
        changed = True
    if any(_is_legacy_mt5(sym) for sym in cfg.correlated_basket):
        cfg.correlated_basket = [s for s in cfg.correlated_basket if not _is_legacy_mt5(s)] or ["R_50", "R_25"]
        changed = True
    for bot in cfg.bots:
        if isinstance(bot, dict) and _is_legacy_mt5(str(bot.get("symbol", ""))):
            bot["symbol"] = "cryBTCUSD" if "Crypto" in str(bot.get("symbol", "")) or "BTC" in str(bot.get("symbol", "")) else "R_100"
            changed = True
    if any(
        "B3 Futuros" in cat_name or any(_is_legacy_mt5(s) for s in syms)
        for cat_name, syms in cfg.custom_categories.items()
    ):
        cfg.custom_categories = dict(DEFAULT_CATEGORIES)
        changed = True

    deduped = deduplicate_accounts(cfg.accounts)
    if len(deduped) != len(cfg.accounts):
        cfg.accounts = deduped
        changed = True

    if changed or not config_path.exists():
        save_config(cfg, config_path)
    return cfg


def save_config(cfg: PradoServerConfig, config_path: Path) -> None:
    cfg.accounts = deduplicate_accounts(cfg.accounts)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
