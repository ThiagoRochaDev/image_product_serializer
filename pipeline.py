"""
Entrypoint opcional para executar o pipeline via:
  python pipeline.py --mock

Mantém compatibilidade com o README (que também recomenda `python -m interface.cli.pipeline`).
"""
from __future__ import annotations

from interface.cli.pipeline import build_and_run, parse_args


if __name__ == "__main__":
    args = parse_args()
    build_and_run(args)

