"""Configuration persistence for Prado Institutional HFT Ubuntu Server (Demo/Real Accounts, Math Bots & Backtester)."""
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

KNOWN_BROKER_SERVERS: list[str] = [
    "XMGlobal-MT5 10",
    "XMGlobal-MT5 13",
    "XMGlobal-MT5",
    "XMGlobal-MT5 2",
    "XMGlobal-MT5 4",
    "XMGlobal-MT5 5",
    "XMGlobal-MT5 6",
    "XMGlobal-MT5 7",
    "XMGlobal-MT5 8",
    "XMGlobal-MT5 9",
    "XMGlobal-MT5 11",
    "XMGlobal-MT5 12",
    "XMGlobal-MT5 14",
    "XMGlobal-MT5 15",
    "XPInvestimentos-PRD",
    "XPInvestimentos-DEMO",
    "ClearInvestimentos-PRD",
    "ClearInvestimentos-DEMO",
    "RicoInvestimentos-PRD",
    "RicoInvestimentos-DEMO",
    "BTGPactual-PRD",
    "BTGPactual-DEMO",
    "GenialInvestimentos-PRD",
    "GenialInvestimentos-DEMO",
    "ModalMais-PRD",
    "ModalMais-DEMO",
    "ToroInvestimentos-PRD",
    "ToroInvestimentos-DEMO",
    "CMCapital-PRD",
    "CMCapital-DEMO",
    "TerraInvestimentos-PRD",
    "GuideInvestimentos-PRD",
    "Orama-PRD",
    "ICMarketsSC-Demo",
    "ICMarketsSC-MT5",
    "ICMarketsSC-MT5-2",
    "ICMarketsSC-MT5-4",
    "Exness-MT5Trial",
    "Exness-MT5Real",
    "Pepperstone-Demo",
    "Pepperstone-MT5-Live01",
    "FBS-Demo",
    "FBS-Real",
    "Tickmill-Demo",
    "Tickmill-Live",
    "FP-Markets-MT5-Demo",
    "FP-Markets-MT5-Live",
    "AdmiralMarkets-Demo",
    "AdmiralMarkets-Live",
    "VantageInternational-Demo",
    "VantageInternational-Live",
    "HFM-Demo",
    "HFM-LiveServer",
    "OctaFX-Demo",
    "OctaFX-Real",
    "RoboForex-ECN",
    "RoboForex-Pro",
    "FTMO-Demo",
    "FTMO-Server",
    "The5ers-Demo",
    "The5ers-Live",
    "MetaQuotes-Demo",
]

DEFAULT_PRESEEDED_ACCOUNTS: list[dict[str, Any]] = [
    {
        "account_id": "acc_xm_demo_346595704",
        "account_type": "DEMO",
        "label": "Jose XM Global Demo (346595704)",
        "mt5_login": "346595704",
        "mt5_password": "Soares@16510303",
        "mt5_server": "XMGlobal-MT5 10",
        "created_at": "2026-11-21 16:30:00",
    },
    {
        "account_id": "acc_xm_real_382177116",
        "account_type": "REAL",
        "label": "Jose do Prado Pinheiro - XM Global Real (382177116)",
        "mt5_login": "382177116",
        "mt5_password": "Soares@16510303",
        "mt5_server": "XMGlobal-MT5 13",
        "created_at": "2026-11-21 16:30:00",
    },
]

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
        "name": "2. Fala 1 — Trem Institucional FIX VWAP (Seguidor Puro de Fluxo de Agressão)",
        "operation_mode": "TREND_ONLY",
        "formula": "Sinal = sign(ΔVol) quando |Z_agressão| ≥ 1.8 ∧ |Imbalance| ≥ 0.35 ∧ sign(P - VWAP) == sign(Z)",
        "description": "Detecta quando algoritmos institucionais (protocolo FIX) calibram agressividade máxima na pedra a favor da VWAP.",
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
        "description": "Matemática pura dos HFTs não-direcionais: fornece liquidez nos extremos de desvio padrão quando o fluxo agressor perde força.",
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
        "description": "Focado em explosões súbitas de agressão no Times & Trades com realização rápida em poucos segundos.",
        "window_ticks": 50,
        "zscore_threshold": 2.2,
        "imbalance_threshold": 0.45,
        "revert_sigma": 2.0,
        "sl_sigma_mult": 0.8,
        "tp_sigma_mult": 1.2,
    },
    {
        "template_id": "STAT_ARB_CORRELATION_BASKET",
        "name": "5. Arbitragem Estatística & Correlação de Cesta (B3 WIN/PETR4/VALE3 & Cripto)",
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
]


def deduplicate_accounts(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure no duplicate accounts with same (mt5_login, mt5_server) or account_id."""
    by_key: dict[str, dict[str, Any]] = {}
    for acc in accounts:
        login = str(acc.get("mt5_login", "")).strip()
        srv = str(acc.get("mt5_server", "")).strip()
        key = f"{login}@{srv}" if login else str(acc.get("account_id", ""))
        if not key:
            continue
        # Correct known XM Global 346595704 demo type if mistakenly saved as REAL
        if login == "346595704" and srv == "XMGlobal-MT5 10":
            acc["account_type"] = "DEMO"
            if acc.get("label", "").strip().lower() == "jose":
                acc["label"] = "Jose XM Global Demo (346595704)"
        by_key[key] = acc
    return list(by_key.values())


@dataclass
class PradoServerConfig:
    # Web Login Auth
    admin_username: str = "admin"
    admin_password_hash: str = ""
    secret_key: str = ""
    web_port: int = 8080

    # Primary MetaTrader 5 Credentials & Active Account Selection (DEMO vs REAL)
    mt5_connection_mode: str = "AUTO_MT5_WINE"
    active_account_id: str = "acc_xm_demo_346595704"
    active_account_type: str = "DEMO"
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_terminal_path: str = ""
    rpyc_host: str = "127.0.0.1"
    rpyc_port: int = 18812
    metaapi_token: str = ""
    metaapi_account_id: str = ""
    metaapi_region: str = "london"

    # Saved MT5 Accounts (Both DEMO and REAL)
    accounts: list[dict[str, Any]] = field(default_factory=lambda: [dict(a) for a in DEFAULT_PRESEEDED_ACCOUNTS])

    # Symbol Selection Mode ("PRINCIPAIS" vs "TODOS") and Custom Broker Categories
    symbol_selection_mode: str = "PRINCIPAIS"
    custom_categories: dict[str, list[str]] = field(default_factory=lambda: dict(DEFAULT_CATEGORIES))

    # Active Running / Configured Robot Fleet
    bots: list[dict[str, Any]] = field(default_factory=list)

    # Last Backtest Results History
    backtest_history: list[dict[str, Any]] = field(default_factory=list)

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
    default_lot_size: float = 0.10
    sl_sigma_mult: float = 1.0
    tp_sigma_mult: float = 1.8
    breakeven_trigger_sigma: float = 0.7
    trailing_step_sigma: float = 0.4
    max_daily_loss_money: float = 5000.0
    daily_target_money: float = 10000.0
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

    # Ensure pre-seeded XM Global accounts exist and deduplicate any existing accounts
    existing_logins = {str(a.get("mt5_login", "")) for a in cfg.accounts}
    for pre in DEFAULT_PRESEEDED_ACCOUNTS:
        if pre["mt5_login"] not in existing_logins:
            cfg.accounts.append(dict(pre))
            changed = True

    deduped = deduplicate_accounts(cfg.accounts)
    if len(deduped) != len(cfg.accounts):
        cfg.accounts = deduped
        changed = True
    else:
        cfg.accounts = deduped

    if changed or not config_path.exists():
        save_config(cfg, config_path)
    return cfg


def save_config(cfg: PradoServerConfig, config_path: Path) -> None:
    cfg.accounts = deduplicate_accounts(cfg.accounts)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
