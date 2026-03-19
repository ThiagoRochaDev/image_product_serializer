"""
Infrastructure: StableDiffusionClient
Implementa IImageGenerator com três backends intercambiáveis via Strategy Pattern:
  - MockBackend    → geração instantânea sem API (para testes)
  - StabilityAPIBackend → Stability AI REST API (~R$0.10/img)
  - LocalSDXLBackend   → GPU local via HuggingFace Diffusers
"""
from __future__ import annotations

import io
import os
import time
from abc import ABC, abstractmethod

from application.use_cases.generate_baseline_use_case import IImageGenerator
from infrastructure.config import settings


# ─────────────────────────────────────────────────────────────
# Strategy Interface
# ─────────────────────────────────────────────────────────────
class ISDXLBackend(ABC):
    @abstractmethod
    def generate(self, prompt: str, filename: str) -> bytes:
        """Retorna bytes PNG da imagem gerada."""
        ...


# ─────────────────────────────────────────────────────────────
# Backend 1: Mock — Pillow, sem custo, para testar o pipeline
# ─────────────────────────────────────────────────────────────
class MockBackend(ISDXLBackend):
    """
    Gera uma imagem placeholder 1024×1024 com o nome do produto no centro.
    Usada para validar o fluxo completo sem consumir APIs.
    Propositalmente faz imagens com variação para simular resultados reais.
    """

    # Paleta de cores para diferenciar visualmente baseline vs. estruturado
    _COLORS = {
        "baseline": (180, 200, 220),
        "estruturado": (200, 220, 180),
    }

    def generate(self, prompt: str, filename: str) -> bytes:
        from PIL import Image, ImageDraw, ImageFont
        import random

        # Determina cenário pelo nome do arquivo
        scenario_color = (
            self._COLORS["estruturado"]
            if "estruturado" in filename
            else self._COLORS["baseline"]
        )

        # Cria imagem base 1024×1024 com fundo branco (simulando produto real)
        img = Image.new("RGB", (1024, 1024), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Produto simulado: retângulo colorido centralizado
        margin = random.randint(100, 200)
        draw.rectangle(
            [margin, margin, 1024 - margin, 1024 - margin],
            fill=scenario_color,
            outline=(80, 80, 80),
            width=3,
        )

        # Texto do prompt truncado
        label = prompt[:80] + "..." if len(prompt) > 80 else prompt
        draw.text((50, 1024 - 80), f"[MOCK] {label}", fill=(40, 40, 40))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# Backend 2: Stability AI REST API
# ─────────────────────────────────────────────────────────────
class StabilityAPIBackend(ISDXLBackend):
    """
    Gera imagens via Stability AI API REST v1.
    Custo: ~US$0.02/imagem (≈R$0.10).
    """

    def __init__(self, api_key: str | None = None) -> None:
        import requests as _req
        self._requests = _req
        self._api_key = api_key or settings.STABILITY_API_KEY
        if not self._api_key:
            raise EnvironmentError(
                "STABILITY_API_KEY não encontrada. Adicione ao arquivo .env."
            )

    def generate(self, prompt: str, filename: str) -> bytes:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "text_prompts": [{"text": prompt, "weight": 1.0}],
            "cfg_scale": settings.GUIDANCE_SCALE,
            "height": settings.IMAGE_HEIGHT,
            "width": settings.IMAGE_WIDTH,
            "samples": 1,
            "steps": settings.INFERENCE_STEPS,
        }

        for attempt in range(1, 4):
            resp = self._requests.post(
                settings.STABILITY_API_URL, headers=headers, json=payload, timeout=120
            )
            if resp.status_code == 200:
                import base64
                data = resp.json()
                image_b64 = data["artifacts"][0]["base64"]
                return base64.b64decode(image_b64)
            elif resp.status_code == 429:
                time.sleep(10 * attempt)  # rate limit — espera exponencial
            else:
                raise RuntimeError(
                    f"Stability API erro {resp.status_code}: {resp.text[:200]}"
                )

        raise RuntimeError("Stability API falhou após 3 tentativas (rate limit).")


# ─────────────────────────────────────────────────────────────
# Backend 3: Local SDXL via HuggingFace Diffusers
# ─────────────────────────────────────────────────────────────
class LocalSDXLBackend(ISDXLBackend):
    """
    Geração local com SDXL via HuggingFace Diffusers.
    Requer NVIDIA GPU com >= 8GB VRAM e torch + diffusers instalados.
    """

    def __init__(self) -> None:
        try:
            import torch
            from diffusers import StableDiffusionXLPipeline
        except ImportError as exc:
            raise ImportError(
                "Instale: pip install diffusers transformers accelerate torch"
            ) from exc

        self._pipe = StableDiffusionXLPipeline.from_pretrained(
            settings.SDXL_MODEL_ID,
            torch_dtype=torch.float16,
            use_safetensors=True,
            variant="fp16",
        )
        self._pipe.to("cuda")

    def generate(self, prompt: str, filename: str) -> bytes:
        image = self._pipe(
            prompt=prompt,
            num_inference_steps=settings.INFERENCE_STEPS,
            guidance_scale=settings.GUIDANCE_SCALE,
            width=settings.IMAGE_WIDTH,
            height=settings.IMAGE_HEIGHT,
        ).images[0]

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# Context — escolhe o backend pelo settings
# ─────────────────────────────────────────────────────────────
class StableDiffusionClient(IImageGenerator):
    """
    Contexto do Strategy Pattern.
    Delega para o backend correto de acordo com SD_BACKEND do settings.
    """

    _BACKEND_MAP: dict[str, type[ISDXLBackend]] = {
        "mock": MockBackend,
        "api": StabilityAPIBackend,
        "local": LocalSDXLBackend,
    }

    def __init__(self, backend: str | None = None) -> None:
        mode = backend or settings.SD_BACKEND
        if mode not in self._BACKEND_MAP:
            raise ValueError(f"Backend inválido '{mode}'. Válidos: {list(self._BACKEND_MAP)}")
        self._backend: ISDXLBackend = self._BACKEND_MAP[mode]()
        self._mode = mode

    @property
    def mode(self) -> str:
        return self._mode

    def generate(self, prompt: str, filename: str) -> bytes:
        return self._backend.generate(prompt, filename)
