"""
Value Object: QualityThresholds
Encapsula os limiares de conformidade definidos na metodologia do TCC.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityThresholds:
    """
    Conjunto imutável de limiares para as 3 métricas de conformidade.

    Valores padrão derivados da metodologia do TCC (Seção 06):
    - resolução mínima: padrão Amazon Brasil
    - nitidez: calibrado empiricamente para imagens comerciais
    - IoU: metade da área relevante centralizada
    """
    min_resolution_px: int = 1000        # largura e altura mínimas em pixels
    min_sharpness_variance: float = 100.0 # variância Laplaciana mínima
    min_iou: float = 0.50                 # IoU mínimo com a zona central 70%
    central_zone_ratio: float = 0.70      # fração da imagem considerada central

    def resolution_passes(self, width: int, height: int) -> bool:
        return width >= self.min_resolution_px and height >= self.min_resolution_px

    def sharpness_passes(self, variance: float) -> bool:
        return variance >= self.min_sharpness_variance

    def iou_passes(self, iou: float) -> bool:
        return iou >= self.min_iou

    @property
    def central_bounds_ratio(self) -> tuple[float, float]:
        """Retorna (start_ratio, end_ratio) para a zona central em cada eixo."""
        margin = (1.0 - self.central_zone_ratio) / 2.0
        return margin, 1.0 - margin


# Instância padrão usada em todo o pipeline — pode ser substituída via config
DEFAULT_THRESHOLDS = QualityThresholds()
