"""
Use Case: RunPipelineUseCase
Orquestrador principal do experimento TCC.
Itera pelos 15 produtos e executa baseline + estruturado para cada um.
"""
from __future__ import annotations

from typing import Callable, Optional

from domain.entities.product import Product
from domain.repositories.product_repository import IProductRepository
from application.use_cases.generate_baseline_use_case import GenerateBaselineUseCase
from application.use_cases.generate_structured_use_case import GenerateStructuredUseCase
from application.dtos.pipeline_result_dto import (
    PipelineResultDTO,
    ImageResultDTO,
    ValidationDTO,
)
from domain.entities.image_result import ImageResult

# Categorias do experimento definidas no guia metodológico (Seção 04)
EXPERIMENT_CATEGORIES = ["eletronicos", "vestuario", "utensilios"]
SAMPLES_PER_CATEGORY = 5


def _image_result_to_dto(result: ImageResult) -> ImageResultDTO:
    """Converte entidade de domínio para DTO de saída."""
    validation_dto = None
    if result.validation is not None:
        v = result.validation
        validation_dto = ValidationDTO(
            resolution_ok=v.resolution_ok,
            sharpness_score=v.sharpness_score,
            iou_score=v.iou_score,
            is_compliant=v.is_compliant,
            width=v.width,
            height=v.height,
        )
    return ImageResultDTO(
        product_id=result.product_id,
        product_name=result.product_name,
        scenario=result.scenario.value,
        image_path=result.image_path,
        prompt_used=result.prompt_used,
        gemini_attributes=result.gemini_attributes,
        validation=validation_dto,
        error=result.error,
    )


class RunPipelineUseCase:
    """
    Caso de uso orquestrador — coordena:
    1. Carregamento dos 15 produtos (amostragem estratificada)
    2. Para cada produto: GenerateBaseline + GenerateStructured
    3. Agregação dos resultados em PipelineResultDTO

    O callback `on_progress` permite que a CLI exiba o progresso em tempo real.
    """

    def __init__(
        self,
        product_repository: IProductRepository,
        generate_baseline: GenerateBaselineUseCase,
        generate_structured: GenerateStructuredUseCase,
        on_progress: Optional[Callable[[int, int, Product, ImageResult, ImageResult], None]] = None,
        hypothesis_threshold: float = 0.50,
        hypothesis_min_delta: float = 0.00,
    ) -> None:
        self._product_repo = product_repository
        self._generate_baseline = generate_baseline
        self._generate_structured = generate_structured
        self._on_progress = on_progress
        self._hypothesis_threshold = hypothesis_threshold
        self._hypothesis_min_delta = hypothesis_min_delta

    def execute(self) -> PipelineResultDTO:
        """
        Executa o experimento completo e retorna o DTO de resultado agregado.

        Returns:
            PipelineResultDTO com todas as 30 imagens (15 baseline + 15 estruturado),
            taxas de conformidade e flag de validação da hipótese H₁.
        """
        # 1. Carregamento estratificado
        products: list[Product] = self._product_repo.get_stratified_sample(
            categories=EXPERIMENT_CATEGORIES,
            samples_per_category=SAMPLES_PER_CATEGORY,
        )

        result_dto = PipelineResultDTO(
            products_total=len(products),
            images_total=len(products) * 2,
            categories=EXPERIMENT_CATEGORIES,
            hypothesis_threshold=self._hypothesis_threshold,
            hypothesis_min_delta=self._hypothesis_min_delta,
        )

        # 2. Processar cada produto
        for idx, product in enumerate(products, start=1):
            # Baseline
            baseline_result = self._generate_baseline.execute(product, idx)
            # Estruturado
            structured_result = self._generate_structured.execute(product, idx)

            # Acumular resultados
            result_dto.baseline_results.append(_image_result_to_dto(baseline_result))
            result_dto.structured_results.append(_image_result_to_dto(structured_result))

            # 3. Callback de progresso para a CLI
            if self._on_progress:
                self._on_progress(idx, len(products), product, baseline_result, structured_result)

        return result_dto
