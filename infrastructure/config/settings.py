"""
Infrastructure: Settings
Configurações centrais do pipeline carregadas via python-dotenv.
Este é o único arquivo que precisa ser editado para mudar o comportamento do sistema.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# Carrega variáveis do arquivo .env na raiz do projeto
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = OUTPUT_DIR / "imagens"
REPORTS_DIR = OUTPUT_DIR / "relatorios"

# Cria os diretórios de saída se não existirem
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Chaves de API
# ─────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
STABILITY_API_KEY: str = os.getenv("STABILITY_API_KEY", "")

# ─────────────────────────────────────────────────────────────
# Modelos de IA
# ─────────────────────────────────────────────────────────────
# Modelo Gemini usado para extração de atributos visuais (TCC)
GEMINI_MODEL: str = "gemini-2.5-flash-lite"
SDXL_MODEL_ID: str = "stabilityai/stable-diffusion-xl-base-1.0"
STABILITY_API_URL: str = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

# ─────────────────────────────────────────────────────────────
# Modo do backend de geração de imagens
# ─────────────────────────────────────────────────────────────
# "local"  → GPU local via HuggingFace Diffusers (requer NVIDIA >= 8GB VRAM)
# "api"    → Stability AI REST API (~R$0.10/imagem)
# "mock"   → Imagem placeholder gerada por Pillow (sem custo, para testes)
SD_BACKEND: Literal["local", "api", "mock"] = os.getenv("SD_BACKEND", "mock")

# Parâmetros de geração
IMAGE_WIDTH: int = 1024
IMAGE_HEIGHT: int = 1024
INFERENCE_STEPS: int = 30
GUIDANCE_SCALE: float = 7.5

# ─────────────────────────────────────────────────────────────
# Métricas de conformidade (Seção 06 do guia metodológico)
# ─────────────────────────────────────────────────────────────
MIN_RESOLUTION_PX: int = 1000
MIN_SHARPNESS_VARIANCE: float = 100.0
MIN_IOU: float = 0.50
CENTRAL_ZONE_RATIO: float = 0.70

# ─────────────────────────────────────────────────────────────
# Experimento
# ─────────────────────────────────────────────────────────────
EXPERIMENT_CATEGORIES: list[str] = ["eletronicos", "vestuario", "utensilios"]
SAMPLES_PER_CATEGORY: int = 5
MAX_RETRIES: int = 1          # tentativas para imagens com IoU < 0.20
RETRY_IOU_THRESHOLD: float = 0.20  # retry apenas para falha severa de centralização
HYPOTHESIS_THRESHOLD: float = 0.50  # limiar mínimo de conformidade para H₁
# Margem mínima (taxa absoluta) para considerar o estruturado superior ao baseline.
# Ex.: 0.05 = +5.0 pontos percentuais.
HYPOTHESIS_MIN_DELTA: float = 0.00
