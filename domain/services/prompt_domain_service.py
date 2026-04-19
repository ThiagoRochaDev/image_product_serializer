"""
Domain Service: PromptDomainService
Responsável pela lógica de montagem de prompts — separando responsabilidade semântica
(Gemini) da responsabilidade técnica (guardrails).
"""
from __future__ import annotations

from domain.entities.image_result import Scenario
from domain.entities.product import Product
from domain.value_objects.prompt import Prompt

# ---------------------------------------------------------------------------
# Guardrails fixos — requisitos não-negociáveis de qualidade visual Amazon BR
# ---------------------------------------------------------------------------
_GUARDRAILS: list[str] = [
    "pure white background",
    "soft studio lighting, even illumination",
    "centered, front view, full product visible",
    "professional product photography, commercial grade",
    "high resolution, sharp focus, 8k",
]

# Campos esperados no JSON retornado pelo Gemini
_EXPECTED_FIELDS = ("objeto", "cor_principal", "material", "formato", "detalhes_visuais")


class PromptDomainService:
    """
    Serviço de domínio sem estado (stateless) que:
    1. Constrói o prompt BASELINE (mínimo, sem enriquecimento)
    2. Constrói o prompt ESTRUTURADO (atributos Gemini + guardrails)

    Esta separação garante que a regra de negócio dos guardrails viva no domínio,
    não na camada de infraestrutura ou de aplicação.
    """

    def build_baseline_prompt(
        self,
        product: Product,
        gemini_attributes: dict | None = None,
    ) -> Prompt:
        """
        Prompt mínimo — nome do produto em inglês + fundo branco.
        Representa o cenário controle (H₀).
        Usa english_name do Gemini para garantir compatibilidade com APIs inglês-only.
        """
        english_name = (gemini_attributes or {}).get("english_name", "").strip()
        name = english_name or product.name
        text = f"product photo of {name}, white background"
        return Prompt(text=text, scenario=Scenario.BASELINE)

    def build_structured_prompt(
        self,
        product: Product,
        gemini_attributes: dict,
    ) -> Prompt:
        """
        Prompt enriquecido — atributos Gemini + guardrails fixos.
        Representa o cenário de tratamento (H₁).

        Args:
            product: entidade produto (usada como fallback se atributos faltarem)
            gemini_attributes: dict retornado pelo GeminiClient com campos visuais

        Returns:
            Prompt estruturado e imutável
        """
        parts: list[str] = []

        # 1. Atributos semânticos extraídos pelo Gemini
        attr = gemini_attributes or {}
        english_name = attr.get("english_name", "").strip()
        cor = attr.get("cor_principal", "")
        material = attr.get("material", "")
        objeto = attr.get("objeto", product.name)
        formato = attr.get("formato", "")
        detalhes = attr.get("detalhes_visuais", "")

        # Âncora: nome em inglês garante que o SD gere o produto certo
        anchor = english_name or objeto
        visual_desc_parts = [p for p in [cor, material, anchor] if p]
        visual_desc = " ".join(visual_desc_parts)
        if formato:
            visual_desc += f", {formato}"
        if detalhes:
            visual_desc += f", {detalhes}"
        parts.append(visual_desc)

        # 2. Guardrails fixos (responsabilidade técnica, não semântica)
        parts.extend(_GUARDRAILS)

        text = ",\n".join(parts)
        return Prompt(text=text, scenario=Scenario.STRUCTURED)

    @staticmethod
    def get_guardrails() -> list[str]:
        """Expõe os guardrails para auditoria e documentação."""
        return list(_GUARDRAILS)
