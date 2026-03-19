"""
Value Object: Prompt
Representa um prompt imutável para o modelo de geração de imagens.
"""
from __future__ import annotations

from dataclasses import dataclass
from domain.entities.image_result import Scenario


@dataclass(frozen=True)
class Prompt:
    """
    Value Object imutável. Dois prompts com o mesmo texto e cenário são idênticos.
    """
    text: str
    scenario: Scenario

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("Prompt text cannot be empty.")

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def __str__(self) -> str:
        return self.text
