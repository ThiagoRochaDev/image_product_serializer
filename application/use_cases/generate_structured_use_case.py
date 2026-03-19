"""
Use Case: GenerateStructuredUseCase
Cenário tratamento H₁: Gemini → JSON atributos → guardrails → SDXL.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.entities.image_result import ImageResult, Scenario
from domain.entities.product import Product
from domain.services.prompt_domain_service import PromptDomainService
from application.use_cases.validate_image_use_case import ValidateImageUseCase
from application.use_cases.generate_baseline_use_case import IImageGenerator
from domain.repositories.image_repository import IImageRepository


class IGeminiClient(ABC):
    """Port para o cliente Gemini."""
    @abstractmethod
    def extract_visual_attributes(self, product_name: str, description: str, category: str) -> dict:
        """
        Chama o Gemini e retorna JSON com:
        objeto, cor_principal, material, formato, detalhes_visuais, categoria_visual
        """
        ...


class GenerateStructuredUseCase:
    """
    Cenário ESTRUTURADO (grupo de tratamento H₁):
    1. Gemini extrai atributos visuais em JSON
    2. PromptDomainService monta prompt com guardrails
    3. SDXL gera imagem com prompt enriquecido
    4. OpenCV valida a imagem

    Esta é a hipótese central do TCC: o fluxo estruturado supera o baseline.
    """

    def __init__(
        self,
        gemini_client: IGeminiClient,
        prompt_service: PromptDomainService,
        image_generator: IImageGenerator,
        image_repository: IImageRepository,
        validate_use_case: ValidateImageUseCase,
        max_retries: int = 0,
        retry_iou_threshold: float = 0.20,
    ) -> None:
        self._gemini = gemini_client
        self._prompt_service = prompt_service
        self._generator = image_generator
        self._image_repo = image_repository
        self._validator = validate_use_case
        self._max_retries = max_retries
        self._retry_iou_threshold = retry_iou_threshold

    def execute(self, product: Product, product_index: int) -> ImageResult:
        result = ImageResult(
            product_id=product.id,
            product_name=product.name,
            scenario=Scenario.STRUCTURED,
        )

        try:
            # 1. Gemini — decomposição semântica
            attributes = self._gemini.extract_visual_attributes(
                product_name=product.name,
                description=product.description,
                category=product.category,
            )
            result.gemini_attributes = attributes

            # 2. Prompt enriquecido com guardrails
            prompt = self._prompt_service.build_structured_prompt(product, attributes)
            result.prompt_used = prompt.text

            filename = f"produto_{product_index:03d}_estruturado.png"
            best_bytes: bytes | None = None
            best_path: str | None = None
            best_validation = None
            last_error: Exception | None = None

            # 3-5. Gerar, persistir e validar (com retry opcional para falha severa de IoU)
            for attempt in range(self._max_retries + 1):
                try:
                    image_bytes = self._generator.generate(prompt.text, filename)
                    saved_path = self._image_repo.save(image_bytes, filename)
                    validation = self._validator.execute(saved_path)

                    if best_validation is None or validation.iou_score > best_validation.iou_score:
                        best_bytes = image_bytes
                        best_path = saved_path
                        best_validation = validation

                    # Retry apenas quando IoU está severamente baixo.
                    if validation.iou_score >= self._retry_iou_threshold:
                        break
                except Exception as exc:
                    last_error = exc

            if best_validation is None or best_bytes is None or best_path is None:
                raise RuntimeError(f"Falha ao gerar/validar imagem estruturada: {last_error}") from last_error

            # Garante que o arquivo final seja o "melhor" entre as tentativas.
            self._image_repo.save(best_bytes, filename)
            result.image_path = best_path
            result.validation = best_validation

        except Exception as exc:
            result.error = str(exc)

        return result
