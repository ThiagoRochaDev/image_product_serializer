"""
Use Case: ValidateImageUseCase
Recebe o caminho de uma imagem e retorna o ValidationResult via OpenCV.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.entities.validation_result import ValidationResult
from domain.value_objects.metrics import QualityThresholds, DEFAULT_THRESHOLDS


class IImageValidator(ABC):
    """Port (interface) para o validador de imagens."""
    @abstractmethod
    def validate(self, image_path: str) -> ValidationResult:
        ...


class ValidateImageUseCase:
    """
    Caso de uso isolado para validação de imagem.
    Depende da interface IImageValidator — não de OpenCV diretamente.
    """

    def __init__(
        self,
        validator: IImageValidator,
        thresholds: QualityThresholds = DEFAULT_THRESHOLDS,
    ) -> None:
        self._validator = validator
        self._thresholds = thresholds

    def execute(self, image_path: str) -> ValidationResult:
        """
        Args:
            image_path: caminho absoluto para o arquivo PNG gerado

        Returns:
            ValidationResult com as 3 métricas e flag de conformidade
        """
        return self._validator.validate(image_path)
