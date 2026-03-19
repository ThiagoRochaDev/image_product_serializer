"""
Domain Entity: ValidationResult
Resultado da validação OpenCV de uma imagem gerada.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    """
    Entidade imutável que encapsula o resultado das 3 métricas de conformidade.

    Critérios de conformidade (AND lógico):
    - resolução ≥ 1000×1000 px
    - variância Laplaciana (nitidez) ≥ 100
    - IoU de centralização ≥ 0.50
    """
    resolution_ok: bool
    sharpness_score: float       # variância Laplaciana
    iou_score: float             # Intersection over Union com a zona central
    width: int
    height: int

    SHARPNESS_THRESHOLD: float = 100.0
    IOU_THRESHOLD: float = 0.50

    @property
    def sharpness_ok(self) -> bool:
        return self.sharpness_score >= self.SHARPNESS_THRESHOLD

    @property
    def iou_ok(self) -> bool:
        return self.iou_score >= self.IOU_THRESHOLD

    @property
    def is_compliant(self) -> bool:
        """Uma imagem é conforme apenas se TODAS as métricas passarem."""
        return self.resolution_ok and self.sharpness_ok and self.iou_ok

    @property
    def compliance_score(self) -> float:
        """Score parcial: número de métricas aprovadas / 3."""
        passed = sum([self.resolution_ok, self.sharpness_ok, self.iou_ok])
        return passed / 3.0

    def to_dict(self) -> dict:
        return {
            "resolucao_ok": self.resolution_ok,
            "resolucao_dimensoes": f"{self.width}x{self.height}",
            "nitidez_laplaciano": round(self.sharpness_score, 2),
            "nitidez_ok": self.sharpness_ok,
            "centralizacao_iou": round(self.iou_score, 4),
            "centralizacao_ok": self.iou_ok,
            "conforme": self.is_compliant,
            "score_conformidade": round(self.compliance_score, 4),
        }
