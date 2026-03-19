"""
Infrastructure: OpenCVValidator
Implementa IImageValidator com as 3 métricas do TCC via OpenCV:
  1. Resolução  ≥ 1000×1000 px
  2. Nitidez     variância Laplaciana ≥ 100
  3. Centralização IoU ≥ 0.50 (objeto vs. zona central 70%)
"""
from __future__ import annotations

import cv2
import numpy as np

from application.use_cases.validate_image_use_case import IImageValidator
from domain.entities.validation_result import ValidationResult
from domain.value_objects.metrics import QualityThresholds, DEFAULT_THRESHOLDS


class OpenCVValidator(IImageValidator):
    """
    Validador determinístico usando OpenCV.
    Implementa os cálculos formais descritos na Seção 06 do guia metodológico.
    """

    def __init__(self, thresholds: QualityThresholds = DEFAULT_THRESHOLDS) -> None:
        self._thresholds = thresholds

    # ─────────────────────────────────────────────────────────
    # Interface pública
    # ─────────────────────────────────────────────────────────
    def validate(self, image_path: str) -> ValidationResult:
        """
        Executa as 3 métricas na imagem e retorna ValidationResult.
        Raises FileNotFoundError se a imagem não existir.
        """
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Imagem não encontrada: {image_path}")

        h, w = img.shape[:2]
        resolution_ok = self._thresholds.resolution_passes(w, h)
        sharpness_score = self._compute_sharpness(img)
        iou_score = self._compute_iou(img)

        return ValidationResult(
            resolution_ok=resolution_ok,
            sharpness_score=sharpness_score,
            iou_score=iou_score,
            width=w,
            height=h,
        )

    # ─────────────────────────────────────────────────────────
    # Métrica 1: Resolução
    # ─────────────────────────────────────────────────────────
    # Implementada diretamente no validate() via img.shape

    # ─────────────────────────────────────────────────────────
    # Métrica 2: Nitidez via Operador Laplaciano
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def _compute_sharpness(img: np.ndarray) -> float:
        """
        Variância do Laplaciano em escala de cinza.
        ∇²f = ∂²f/∂x² + ∂²f/∂y²
        Alta variância → bordas nítidas → imagem focada.
        Referência: Seção 6.2 do guia metodológico.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return float(laplacian.var())

    # ─────────────────────────────────────────────────────────
    # Métrica 3: Centralização via IoU
    # ─────────────────────────────────────────────────────────
    def _compute_iou(self, img: np.ndarray) -> float:
        """
        IoU entre o bounding box do produto e a zona central (70% × 70%).

        Algoritmo:
        1. Converte para HSV
        2. Cria máscara de fundo branco (remove fundo)
        3. Inverte a máscara para isolar o produto
        4. Encontra o maior contorno (produto)
        5. Calcula bounding box do produto
        6. Define área central (70% da imagem)
        7. Calcula IoU entre ambas

        Referência: Seção 6.3 do guia metodológico.
        """
        H, W = img.shape[:2]

        # 1. Segmentação do fundo branco via HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_white = np.array([0, 0, 200], dtype=np.uint8)
        upper_white = np.array([180, 30, 255], dtype=np.uint8)
        background_mask = cv2.inRange(hsv, lower_white, upper_white)

        # 2. Produto = complemento do fundo
        product_mask = cv2.bitwise_not(background_mask)

        # 3. Morfologia para remover ruído
        kernel = np.ones((5, 5), np.uint8)
        product_mask = cv2.morphologyEx(product_mask, cv2.MORPH_CLOSE, kernel)
        product_mask = cv2.morphologyEx(product_mask, cv2.MORPH_OPEN, kernel)

        # 4. Contorno do produto
        contours, _ = cv2.findContours(
            product_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return 0.0  # sem produto detectado → IoU = 0

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < 100:
            return 0.0  # produto muito pequeno → descartado

        # 5. BBox do produto
        px, py, pw, ph = cv2.boundingRect(largest)
        product_box = (px, py, px + pw, py + ph)

        # 6. Zona central (70% em cada dimensão)
        start_ratio, end_ratio = self._thresholds.central_bounds_ratio
        cx1 = int(start_ratio * W)
        cy1 = int(start_ratio * H)
        cx2 = int(end_ratio * W)
        cy2 = int(end_ratio * H)
        central_box = (cx1, cy1, cx2, cy2)

        # 7. IoU
        return self._box_iou(product_box, central_box)

    @staticmethod
    def _box_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        """
        Calcula IoU entre dois bounding boxes no formato (x1, y1, x2, y2).
        IoU = Intersec / União
        """
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b

        # Interseção
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0  # sem sobreposição

        intersection = (ix2 - ix1) * (iy2 - iy1)

        # União
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        union = area_a + area_b - intersection

        if union <= 0:
            return 0.0

        return float(intersection / union)
