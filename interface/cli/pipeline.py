"""
Interface CLI: pipeline.py
Ponto de entrada do sistema. Orquestra todos os módulos via injeção de dependência.

Uso:
  python -m interface.cli.pipeline --mock
  python -m interface.cli.pipeline --backend mock data/amazon_brasil.csv
  python -m interface.cli.pipeline --backend api  data/amazon_brasil.csv
  python -m interface.cli.pipeline --backend local data/amazon_brasil.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Adiciona a raiz do projeto ao PYTHONPATH (necessário para imports absolutos)
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from domain.entities.image_result import ImageResult
from domain.entities.product import Product
from domain.services.prompt_domain_service import PromptDomainService
from domain.value_objects.metrics import QualityThresholds

from application.use_cases.run_pipeline_use_case import RunPipelineUseCase
from application.use_cases.generate_baseline_use_case import GenerateBaselineUseCase
from application.use_cases.generate_structured_use_case import GenerateStructuredUseCase
from application.use_cases.validate_image_use_case import ValidateImageUseCase

from infrastructure.config import settings
from infrastructure.ai.stable_diffusion_client import StableDiffusionClient
from infrastructure.cv.opencv_validator import OpenCVValidator
from infrastructure.persistence.file_image_repository import FileImageRepository
from infrastructure.reporting.json_reporter import JsonReporter

from interface.cli.report_presenter import ReportPresenter

# ─────────────────────────────────────────────────────────────
# Mock do repositório de produtos (modo --mock)
# ─────────────────────────────────────────────────────────────
from domain.repositories.product_repository import IProductRepository


class MockProductRepository(IProductRepository):
    """Repositório mock com 15 produtos fictícios para testes sem CSV."""

    _MOCK_PRODUCTS = [
        # Eletrônicos
        ("Samsung Galaxy S23 128GB Preto", "Smartphone premium com câmera tripla", "eletronicos"),
        ("iPhone 14 Pro 256GB Azul", "Smartphone Apple com chip A16", "eletronicos"),
        ("Notebook Dell Inspiron 15 i7", "Notebook com tela Full HD 15 polegadas", "eletronicos"),
        ("Fone de Ouvido Sony WH-1000XM5", "Headphone com cancelamento de ruído", "eletronicos"),
        ("Tablet Samsung Galaxy Tab S8", "Tablet Android com tela AMOLED", "eletronicos"),
        # Vestuário
        ("Camiseta Polo Lacoste Branca M", "Camiseta polo de algodão piqué premium", "vestuario"),
        ("Calça Jeans Levi's 511 Slim Azul", "Calça jeans slim fit com stretch", "vestuario"),
        ("Tênis Nike Air Max 270 Preto 42", "Tênis de corrida com câmara de ar", "vestuario"),
        ("Vestido Floral Midi Feminino", "Vestido em viscose com estampa floral", "vestuario"),
        ("Jaqueta Corta-Vento Adidas Azul", "Jaqueta esportiva impermeável", "vestuario"),
        # Utensílios
        ("Panela de Pressão Tramontina 6L", "Panela de pressão em alumínio polido", "utensilios"),
        ("Jogo de Facas Cuisinart 7 peças", "Conjunto de facas de aço inoxidável", "utensilios"),
        ("Liquidificador Philips Walita RI2620", "Liquidificador 1200W com copo de vidro", "utensilios"),
        ("Frigideira Antiaderente Tefal 26cm", "Frigideira com revestimento antiaderente", "utensilios"),
        ("Cafeteira Nespresso Essenza Mini", "Cafeteira de cápsulas compacta 19 bar", "utensilios"),
    ]

    def get_stratified_sample(self, categories, samples_per_category=5):
        from domain.entities.product import Product
        products = []
        for i, (name, desc, cat) in enumerate(self._MOCK_PRODUCTS):
            products.append(Product.create(
                name=name, description=desc, category=cat,
                product_id=f"mock_{i:03d}"
            ))
        return products

    def count_by_category(self, category: str) -> int:
        return sum(1 for _, _, cat in self._MOCK_PRODUCTS if cat == category)


# ─────────────────────────────────────────────────────────────
# Mock do cliente Gemini (modo --mock)
# ─────────────────────────────────────────────────────────────
from application.use_cases.generate_structured_use_case import IGeminiClient


class MockGeminiClient(IGeminiClient):
    """Retorna atributos visuais genéricos sem chamar a API."""

    _TEMPLATES = {
        "eletronicos": {
            "english_name": "electronic device",
            "objeto": "electronic device",
            "cor_principal": "black",
            "material": "glass and aluminum",
            "formato": "rectangular slab",
            "detalhes_visuais": "glossy screen, metallic frame, premium finish",
            "categoria_visual": "electronics",
        },
        "vestuario": {
            "english_name": "clothing item",
            "objeto": "clothing item",
            "cor_principal": "blue",
            "material": "cotton",
            "formato": "flat lay garment",
            "detalhes_visuais": "clean stitching, fabric texture, label visible",
            "categoria_visual": "clothing",
        },
        "utensilios": {
            "english_name": "kitchen utensil",
            "objeto": "kitchen utensil",
            "cor_principal": "silver",
            "material": "stainless steel",
            "formato": "cylindrical",
            "detalhes_visuais": "polished surface, ergonomic handle, professional grade",
            "categoria_visual": "kitchenware",
        },
    }

    def extract_visual_attributes(self, product_name, description, category, image_url=""):
        key = category.lower()
        for k in self._TEMPLATES:
            if k in key:
                return dict(self._TEMPLATES[k])
        return dict(self._TEMPLATES["eletronicos"])


# ─────────────────────────────────────────────────────────────
# Composição e execução do pipeline (DI Container manual)
# ─────────────────────────────────────────────────────────────
def build_and_run(args: argparse.Namespace) -> None:
    presenter = ReportPresenter()
    is_full_mock = args.mock
    backend = "mock" if is_full_mock else args.backend

    presenter.print_header(backend)

    # ── Repositório de produtos ──────────────────────────────
    if is_full_mock or not args.csv:
        product_repo = MockProductRepository()
    else:
        from infrastructure.persistence.csv_product_repository import CSVProductRepository
        product_repo = CSVProductRepository(args.csv)

    # ── Cliente Gemini ───────────────────────────────────────
    # No modo "--mock" usamos Gemini fake. Caso contrário, usamos Gemini real,
    # mesmo quando o backend de imagens é "mock" (teste barato de prompts).
    if is_full_mock:
        gemini_client = MockGeminiClient()
    else:
        from infrastructure.ai.gemini_client import GeminiClient
        gemini_client = GeminiClient()

    # ── Gerador de imagens (Strategy) ──────────────────────
    sd_client = StableDiffusionClient(backend=backend)

    # ── Repositório de imagens e validador ─────────────────
    image_repo = FileImageRepository()
    thresholds = QualityThresholds(
        min_resolution_px=settings.MIN_RESOLUTION_PX,
        min_sharpness_variance=settings.MIN_SHARPNESS_VARIANCE,
        min_iou=settings.MIN_IOU,
        central_zone_ratio=settings.CENTRAL_ZONE_RATIO,
    )
    validator = OpenCVValidator(thresholds)
    validate_uc = ValidateImageUseCase(validator, thresholds)

    # ── Serviço de domínio de prompt ───────────────────────
    prompt_service = PromptDomainService()

    # ── Casos de uso ────────────────────────────────────────
    generate_baseline = GenerateBaselineUseCase(
        prompt_service=prompt_service,
        image_generator=sd_client,
        image_repository=image_repo,
        validate_use_case=validate_uc,
        max_retries=settings.MAX_RETRIES,
        retry_iou_threshold=settings.RETRY_IOU_THRESHOLD,
    )
    generate_structured = GenerateStructuredUseCase(
        gemini_client=gemini_client,
        prompt_service=prompt_service,
        image_generator=sd_client,
        image_repository=image_repo,
        validate_use_case=validate_uc,
        max_retries=settings.MAX_RETRIES,
        retry_iou_threshold=settings.RETRY_IOU_THRESHOLD,
    )

    # ── Callback de progresso ───────────────────────────────
    def on_progress(idx, total, product, baseline, structured):
        presenter.print_product_progress(idx, total, product, baseline, structured)

    pipeline = RunPipelineUseCase(
        product_repository=product_repo,
        generate_baseline=generate_baseline,
        generate_structured=generate_structured,
        gemini_client=gemini_client,
        on_progress=on_progress,
        hypothesis_threshold=settings.HYPOTHESIS_THRESHOLD,
        hypothesis_min_delta=settings.HYPOTHESIS_MIN_DELTA,
    )

    # ── Execução ────────────────────────────────────────────
    products_count = len(product_repo.get_stratified_sample(
        settings.EXPERIMENT_CATEGORIES, settings.SAMPLES_PER_CATEGORY
    ))
    presenter.print_loading(products_count, settings.EXPERIMENT_CATEGORIES)

    pipeline_result = pipeline.execute()

    # ── Relatório JSON ──────────────────────────────────────
    reporter = JsonReporter()
    report_path = reporter.generate(pipeline_result)

    presenter.print_final_summary(pipeline_result, report_path)


# ─────────────────────────────────────────────────────────────
# CLI Argument Parser
# ─────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TCC Pipeline — Geração Automatizada de Imagens de Produto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python -m interface.cli.pipeline --mock
  python -m interface.cli.pipeline --backend mock  data/amazon_brasil.csv
  python -m interface.cli.pipeline --backend api   data/amazon_brasil.csv
  python -m interface.cli.pipeline --backend local data/amazon_brasil.csv
        """,
    )
    parser.add_argument(
        "csv",
        nargs="?",
        default=None,
        help="Caminho para o CSV Kaggle Amazon Brasil (opcional se --mock)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Modo mock completo: produtos fictícios + Gemini fake + imagens Pillow",
    )
    parser.add_argument(
        "--backend",
        choices=["mock", "api", "hf", "local"],
        default=settings.SD_BACKEND,
        help="Backend do Stable Diffusion (padrão: valor de SD_BACKEND no .env)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_and_run(args)
