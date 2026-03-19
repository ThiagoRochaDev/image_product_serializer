"""
Infrastructure: GeminiClient
Integração com a API Google Gemini para decomposição semântica de produtos.
Implementa IGeminiClient (porta definida na camada de aplicação).
"""
from __future__ import annotations

import json
import re
import time

import google.generativeai as genai

from application.use_cases.generate_structured_use_case import IGeminiClient
from infrastructure.config import settings

# Prompt do sistema enviado ao Gemini para extrair atributos visuais
_SYSTEM_PROMPT = """You are a visual attributes extractor for e-commerce product photography.
Given a product name, description, and category, extract the visual attributes needed to generate 
a professional product photo for Amazon Brazil.

Return ONLY valid JSON with these exact fields:
{
  "objeto": "main object type (e.g., smartphone, t-shirt, pan)",
  "cor_principal": "primary color in English",
  "material": "main material (e.g., glass and aluminum, cotton, stainless steel)",
  "formato": "shape/form descriptor (e.g., rectangular slab, slim fit, round bottom)",
  "detalhes_visuais": "key visual details separated by commas",
  "categoria_visual": "visual category (electronics, clothing, kitchenware)"
}

Do NOT include markdown or code fences. Return only the JSON object."""


class GeminiClient(IGeminiClient):
    """
    Implementação concreta do cliente Gemini.
    Usa o modelo configurado em settings.GEMINI_MODEL com resposta forçada em JSON.
    """

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
    ) -> dict:
        """
        Chama o Gemini e retorna o dicionário de atributos visuais.
        Inclui retry automático para erros de rede ou respostas malformadas.
        """
        user_message = (
            f"Product name: {product_name}\n"
            f"Description: {description or 'N/A'}\n"
            f"Category: {category}"
        )

        last_error: Exception | None = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                response = self._model.generate_content(user_message)
                raw_text = response.text.strip()
                return self._parse_json(raw_text)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self._MAX_RETRIES:
                    time.sleep(self._RETRY_DELAY_S * attempt)

        raise RuntimeError(
            f"Gemini falhou após {self._MAX_RETRIES} tentativas: {last_error}"
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Tenta extrair JSON válido de uma string, removendo marcadores de bloco de código."""
        # Remove markdown code fences se presentes
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemini retornou JSON inválido: {exc}\nRaw: {raw[:200]}") from exc
