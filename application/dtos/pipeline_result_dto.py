"""
DTOs da camada de Aplicação — Data Transfer Objects
Isolam as entidades de domínio das fronteiras externas (CLI, relatório).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProductDTO:
    """DTO de entrada para os casos de uso de geração."""
    id: str
    name: str
    description: str
    category: str
    index: int = 0          # posição na lista de 15 produtos (para nomes de arquivo)
    total: int = 15         # total do experimento


@dataclass
class ValidationDTO:
    resolution_ok: bool
    sharpness_score: float
    iou_score: float
    is_compliant: bool
    width: int
    height: int


@dataclass
class ImageResultDTO:
    product_id: str
    product_name: str
    scenario: str           # "baseline" | "structured"
    image_path: Optional[str]
    prompt_used: Optional[str]
    gemini_attributes: Optional[dict]
    validation: Optional[ValidationDTO]
    error: Optional[str]

    @property
    def is_compliant(self) -> bool:
        if self.validation is None:
            return False
        return self.validation.is_compliant


@dataclass
class PipelineResultDTO:
    """DTO de saída agregado com todos os resultados do experimento."""
    products_total: int
    images_total: int
    categories: list[str]
    baseline_results: list[ImageResultDTO] = field(default_factory=list)
    structured_results: list[ImageResultDTO] = field(default_factory=list)
    hypothesis_threshold: float = 0.50
    hypothesis_min_delta: float = 0.00

    # ---- métricas calculadas após a execução ----
    @property
    def baseline_compliant_count(self) -> int:
        return sum(1 for r in self.baseline_results if r.is_compliant)

    @property
    def structured_compliant_count(self) -> int:
        return sum(1 for r in self.structured_results if r.is_compliant)

    @property
    def baseline_compliance_rate(self) -> float:
        if not self.baseline_results:
            return 0.0
        return self.baseline_compliant_count / len(self.baseline_results)

    @property
    def structured_compliance_rate(self) -> float:
        if not self.structured_results:
            return 0.0
        return self.structured_compliant_count / len(self.structured_results)

    @property
    def hypothesis_validated(self) -> bool:
        """
        H₁ validada se:
        1) taxa_estruturado >= limiar
        2) taxa_estruturado > taxa_baseline
        3) delta >= margem mínima (em taxa absoluta)
        """
        delta = self.structured_compliance_rate - self.baseline_compliance_rate
        return (
            self.structured_compliance_rate >= self.hypothesis_threshold
            and self.structured_compliance_rate > self.baseline_compliance_rate
            and delta >= self.hypothesis_min_delta
        )

    def avg_metric(self, results: list[ImageResultDTO], metric: str) -> float:
        valid = [r for r in results if r.validation is not None]
        if not valid:
            return 0.0
        return sum(getattr(r.validation, metric) for r in valid) / len(valid)
