"""
Domain Entity: ImageResult
Representa uma imagem gerada para um produto em um dado cenário.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from domain.entities.validation_result import ValidationResult


class Scenario(str, Enum):
    BASELINE = "baseline"
    STRUCTURED = "structured"


@dataclass
class ImageResult:
    """
    Entidade que associa um produto a uma imagem gerada e ao seu resultado de validação.
    Mutável pois a validação é preenchida após a geração.
    """
    product_id: str
    product_name: str
    scenario: Scenario
    image_path: Optional[str] = None
    prompt_used: Optional[str] = None
    gemini_attributes: Optional[dict] = None
    validation: Optional[ValidationResult] = None
    error: Optional[str] = None

    @property
    def is_compliant(self) -> bool:
        if self.validation is None:
            return False
        return self.validation.is_compliant

    @property
    def generation_failed(self) -> bool:
        return self.error is not None

    def to_dict(self) -> dict:
        return {
            "produto_id": self.product_id,
            "produto_nome": self.product_name,
            "cenario": self.scenario.value,
            "caminho_imagem": self.image_path,
            "prompt_utilizado": self.prompt_used,
            "atributos_gemini": self.gemini_attributes,
            "validacao": self.validation.to_dict() if self.validation else None,
            "erro": self.error,
        }
