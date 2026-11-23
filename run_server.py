#!/usr/bin/env python3
"""Entrypoint for Prado Institutional HFT Web Dashboard & cTrader Quant Engine (Ubuntu & Windows)."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from prado_linux.web_app import run_http_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Prado Institutional HFT — Ubuntu Web Server & cTrader Quant Brain")
    parser.add_argument("--host", default="0.0.0.0", help="IP de bind do servidor web (padrao: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Porta HTTP do painel web (padrao: 8080)")
    parser.add_argument(
        "--config",
        default=str(ROOT_DIR / "data" / "prado_server_config.json"),
        help="Caminho do arquivo JSON de configuracao",
    )
    args = parser.parse_args()
    run_http_server(config_path=Path(args.config), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
