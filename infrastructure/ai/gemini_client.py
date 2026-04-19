"""
Infrastructure: GeminiClient
Integração com a API Google Gemini para decomposição semântica de produtos.
Usa visão multimodal quando imgUrl está disponível — o modelo vê a foto real
do produto antes de extrair os atributos visuais.
"""
from __future__ import annotations

import io
import json
import re
import time

import google.generativeai as genai

from application.use_cases.generate_structured_use_case import IGeminiClient
from infrastructure.config import settings

_SYSTEM_PROMPT = """You are a visual attributes extractor for e-commerce product photography.
Given a product name, description, category, and optionally a product image, extract the visual
attributes needed to generate a professional product photo for Amazon Brazil.

Return ONLY valid JSON with these exact fields:
{
  "english_name": "short English product name (3-6 words, brand + type + key spec)",
  "objeto": "main object type in English (e.g., smartphone, t-shirt, frying pan)",
  "cor_principal": "primary color in English",
  "material": "main material (e.g., glass and aluminum, cotton, stainless steel)",
  "formato": "shape/form descriptor (e.g., rectangular slab, slim fit, round bottom)",
  "detalhes_visuais": "key visual details separated by commas, max 8 items",
  "categoria_visual": "visual category (electronics, clothing, kitchenware)"
}

Rules:
- ALL values must be in English
- english_name: brand name + product type + most distinctive feature (e.g., "Samsung 50 inch 4K TV")
- If an image is provided, prioritize what you SEE over what the text says
- detalhes_visuais: describe visible physical features (shape, buttons, ports, texture, logo)
- Do NOT include markdown or code fences. Return only the JSON object."""


class GeminiClient(IGeminiClient):
    _MAX_RETRIES = 3
    _RETRY_DELAY_S = 2.0

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.GEMINI_API_KEY
        if not key:
            raise EnvironmentError(
                "GEMINI_API_KEY não encontrada. "
                "Adicione ao arquivo .env ou passe como argumento."
            )
        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=_SYSTEM_PROMPT,
        )

    def extract_visual_attributes(
        self,
        product_name: str,
        description: str,
        category: str,
        image_url: str = "",
    ) -> dict:
        user_message = (
            f"Product name: {product_name}\n"
            f"Description: {description or 'N/A'}\n"
            f"Category: {category}"
        )

        content_parts: list = [user_message]

        if image_url:
            image_bytes = self._fetch_image(image_url)
            if image_bytes:
                import PIL.Image
                img = PIL.Image.open(io.BytesIO(image_bytes))
                content_parts = [img, user_message]

        last_error: Exception | None = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                response = self._model.generate_content(content_parts)
                raw_text = response.text.strip()
                return self._parse_json(raw_text)
            except Exception as exc:
                last_error = exc
                if attempt < self._MAX_RETRIES:
                    time.sleep(self._RETRY_DELAY_S * attempt)

        raise RuntimeError(
            f"Gemini falhou após {self._MAX_RETRIES} tentativas: {last_error}"
        )

    @staticmethod
    def _fetch_image(url: str) -> bytes | None:
        try:
            import requests
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None

    @staticmethod
    def _parse_json(raw: str) -> dict:
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemini retornou JSON inválido: {exc}\nRaw: {raw[:200]}") from exc