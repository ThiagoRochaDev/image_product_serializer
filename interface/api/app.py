"""
Interface API: FastAPI app para expor o pipeline via HTTP + Swagger.

Swagger UI:
  http://127.0.0.1:8000/docs
OpenAPI JSON:
  http://127.0.0.1:8000/openapi.json
"""
from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Garante imports absolutos ao rodar via `python -m uvicorn ...` a partir da raiz do repo.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import tempfile
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile

from application.dtos.pipeline_result_dto import PipelineResultDTO
from application.use_cases.generate_baseline_use_case import GenerateBaselineUseCase
from application.use_cases.generate_structured_use_case import GenerateStructuredUseCase
from application.use_cases.run_pipeline_use_case import RunPipelineUseCase
from application.use_cases.validate_image_use_case import ValidateImageUseCase
from domain.services.prompt_domain_service import PromptDomainService
from domain.value_objects.metrics import QualityThresholds
from infrastructure.ai.stable_diffusion_client import StableDiffusionClient
from infrastructure.config import settings
from infrastructure.cv.opencv_validator import OpenCVValidator
from infrastructure.persistence.file_image_repository import FileImageRepository
from infrastructure.reporting.json_reporter import JsonReporter
from interface.api.schemas import (
    GenerateProductResponse,
    ImageUploadValidationResponse,
    PipelineRunRequest,
    PipelineStatus,
    ProductGenerateRequest,
    ProductItem,
    ProductListResponse,
    ScenarioResult,
)

# Reusa os mocks já existentes na CLI (evita duplicar template de produtos/atributos).
from interface.cli.pipeline import MockGeminiClient, MockProductRepository


@dataclass
class _State:
    lock: threading.Lock
    status: str = "idle"  # "idle" | "running" | "completed" | "error"
    produtos_processados: int = 0
    total_produtos: int = 0
    baseline_conformes: int = 0
    estruturado_conformes: int = 0
    taxa_baseline: float = 0.0
    taxa_estruturado: float = 0.0
    hipotese_validada: Optional[bool] = None
    relatorio_path: Optional[str] = None

    def to_schema(self) -> PipelineStatus:
        return PipelineStatus(
            status=self.status,
            produtos_processados=self.produtos_processados,
            total_produtos=self.total_produtos,
            baseline_conformes=self.baseline_conformes,
            estruturado_conformes=self.estruturado_conformes,
            taxa_baseline=self.taxa_baseline,
            taxa_estruturado=self.taxa_estruturado,
            hipotese_validada=self.hipotese_validada,
            relatorio_path=self.relatorio_path,
        )


STATE = _State(lock=threading.Lock())

app = FastAPI(
    title="TCC Pipeline API",
    version="0.1.0",
    description="API local para executar o pipeline e inspecionar status via Swagger.",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/pipeline/status", response_model=PipelineStatus)
def pipeline_status() -> PipelineStatus:
    with STATE.lock:
        return STATE.to_schema()


def _run_pipeline_job(req: PipelineRunRequest) -> None:
    # Monta dependências do pipeline (manual DI) sem saída no terminal.
    with STATE.lock:
        STATE.status = "running"
        STATE.produtos_processados = 0
        STATE.total_produtos = 0
        STATE.baseline_conformes = 0
        STATE.estruturado_conformes = 0
        STATE.taxa_baseline = 0.0
        STATE.taxa_estruturado = 0.0
        STATE.hipotese_validada = None
        STATE.relatorio_path = None

    backend = req.backend
    use_mock_products = req.use_mock_products
    csv_path = req.csv_path

    if not use_mock_products and not csv_path:
        with STATE.lock:
            STATE.status = "error"
        return

    if use_mock_products:
        product_repo = MockProductRepository()
    else:
        from infrastructure.persistence.csv_product_repository import CSVProductRepository

        product_repo = CSVProductRepository(csv_path)

    if req.use_mock_gemini:
        gemini_client = MockGeminiClient()
    else:
        from infrastructure.ai.gemini_client import GeminiClient

        gemini_client = GeminiClient()

    sd_client = StableDiffusionClient(backend=backend)
    image_repo = FileImageRepository()

    thresholds = QualityThresholds(
        min_resolution_px=settings.MIN_RESOLUTION_PX,
        min_sharpness_variance=settings.MIN_SHARPNESS_VARIANCE,
        min_iou=settings.MIN_IOU,
        central_zone_ratio=settings.CENTRAL_ZONE_RATIO,
    )
    validator = OpenCVValidator(thresholds)
    validate_uc = ValidateImageUseCase(validator, thresholds)
    prompt_service = PromptDomainService()

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

    def on_progress(idx, total, product, baseline, structured):
        with STATE.lock:
            STATE.produtos_processados = idx
            STATE.total_produtos = total
            if baseline is not None and getattr(baseline, "is_compliant", False):
                STATE.baseline_conformes += 1
            if structured is not None and getattr(structured, "is_compliant", False):
                STATE.estruturado_conformes += 1

    pipeline = RunPipelineUseCase(
        product_repository=product_repo,
        generate_baseline=generate_baseline,
        generate_structured=generate_structured,
        on_progress=on_progress,
        hypothesis_threshold=settings.HYPOTHESIS_THRESHOLD,
        hypothesis_min_delta=settings.HYPOTHESIS_MIN_DELTA,
    )

    try:
        result: PipelineResultDTO = pipeline.execute()
        report_path = JsonReporter().generate(result)
    except Exception:
        with STATE.lock:
            STATE.status = "error"
        return

    with STATE.lock:
        STATE.status = "completed"
        STATE.baseline_conformes = result.baseline_compliant_count
        STATE.estruturado_conformes = result.structured_compliant_count
        STATE.taxa_baseline = result.baseline_compliance_rate
        STATE.taxa_estruturado = result.structured_compliance_rate
        STATE.hipotese_validada = result.hypothesis_validated
        STATE.relatorio_path = report_path


@app.post("/pipeline/run", response_model=PipelineStatus)
def pipeline_run(req: PipelineRunRequest, background: BackgroundTasks) -> PipelineStatus:
    with STATE.lock:
        if STATE.status == "running":
            raise HTTPException(status_code=409, detail="Pipeline já está em execução.")
        # Reseta aqui para refletir imediatamente no /pipeline/status.
        STATE.status = "running"
        STATE.produtos_processados = 0
        STATE.total_produtos = 0
        STATE.baseline_conformes = 0
        STATE.estruturado_conformes = 0
        STATE.taxa_baseline = 0.0
        STATE.taxa_estruturado = 0.0
        STATE.hipotese_validada = None
        STATE.relatorio_path = None

    if not req.use_mock_products and not req.csv_path:
        with STATE.lock:
            STATE.status = "error"
        raise HTTPException(status_code=400, detail="csv_path é obrigatório quando use_mock_products=false.")

    background.add_task(_run_pipeline_job, req)
    with STATE.lock:
        return STATE.to_schema()


@app.post(
    "/image/validate",
    response_model=ImageUploadValidationResponse,
    summary="Analisa uma imagem enviada por upload",
    description=(
        "Recebe um arquivo de imagem (PNG, JPG, WEBP, etc.) e aplica as mesmas "
        "3 métricas de qualidade usadas no pipeline:\n\n"
        "- **Resolução** — mínimo 1000×1000 px\n"
        "- **Nitidez** — variância Laplaciana ≥ 100\n"
        "- **Centralização** — IoU do produto vs. zona central ≥ 0.50"
    ),
    tags=["Imagem"],
)
async def validate_uploaded_image(
    file: UploadFile = File(..., description="Arquivo de imagem a ser analisado"),
) -> ImageUploadValidationResponse:
    """Valida uma imagem enviada diretamente via upload."""
    thresholds = QualityThresholds(
        min_resolution_px=settings.MIN_RESOLUTION_PX,
        min_sharpness_variance=settings.MIN_SHARPNESS_VARIANCE,
        min_iou=settings.MIN_IOU,
        central_zone_ratio=settings.CENTRAL_ZONE_RATIO,
    )
    validator = OpenCVValidator(thresholds)
    validate_uc = ValidateImageUseCase(validator, thresholds)

    suffix = "." + (file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "png")

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode="wb") as tmp:
            tmp_path = tmp.name
            contents = await file.read()
            tmp.write(contents)

        result = validate_uc.execute(tmp_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao processar imagem: {exc}") from exc
    finally:
        if tmp_path:
            import os
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    data = result.to_dict()
    return ImageUploadValidationResponse(**data)


# ─── Base Amazon Brasil ───────────────────────────────────────────────────────

@app.get(
    "/products",
    response_model=ProductListResponse,
    summary="Lista produtos da base Amazon Brasil",
    description=(
        "Carrega o CSV da base Amazon Brasil e retorna os produtos disponíveis.\n\n"
        "- Use `csv_path` para apontar para o arquivo (padrão: `data/amazon_brasil.csv`)\n"
        "- Use `category` para filtrar por categoria (`eletronicos`, `vestuario`, `utensilios`)\n"
        "- Use `limit` e `offset` para paginação"
    ),
    tags=["Produtos"],
)
def list_products(
    csv_path: str = Query("data/amazon_brasil.csv", description="Caminho para o CSV da base Amazon Brasil"),
    category: Optional[str] = Query(None, description="Filtrar por categoria (opcional)"),
    limit: int = Query(50, ge=1, le=500, description="Número máximo de produtos retornados"),
    offset: int = Query(0, ge=0, description="Índice inicial (paginação)"),
) -> ProductListResponse:
    from infrastructure.persistence.csv_product_repository import CSVProductRepository

    try:
        repo = CSVProductRepository(csv_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    df = repo._df.copy()
    if category:
        df = df[df["category_normalized"].str.contains(category.lower().strip(), na=False)]

    total = len(df)
    page = df.iloc[offset: offset + limit]

    import hashlib
    items = [
        ProductItem(
            id=hashlib.md5(str(row.get("name", "")).encode()).hexdigest()[:12],
            name=str(row.get("name", "")),
            description=str(row.get("description", "")),
            category=str(row.get("category", "")),
        )
        for _, row in page.iterrows()
    ]
    return ProductListResponse(products=items, total=total, csv_path=str(csv_path))


# ─── Geração de imagem para um produto ──────────────────────────────────────

def _build_scenario_result(image_result) -> ScenarioResult:
    """Converte ImageResult em ScenarioResult para a resposta da API."""
    validation = getattr(image_result, "validation", None)
    v_dict = validation.to_dict() if validation else {}
    return ScenarioResult(
        prompt=image_result.prompt_used or "",
        imagem_path=getattr(image_result, "image_path", None),
        atributos_gemini=getattr(image_result, "gemini_attributes", None),
        resolucao_ok=v_dict.get("resolucao_ok"),
        resolucao_dimensoes=v_dict.get("resolucao_dimensoes"),
        nitidez_laplaciano=v_dict.get("nitidez_laplaciano"),
        nitidez_ok=v_dict.get("nitidez_ok"),
        centralizacao_iou=v_dict.get("centralizacao_iou"),
        centralizacao_ok=v_dict.get("centralizacao_ok"),
        conforme=v_dict.get("conforme"),
        score_conformidade=v_dict.get("score_conformidade"),
        erro=getattr(image_result, "error", None),
    )


@app.post(
    "/product/generate",
    response_model=GenerateProductResponse,
    summary="Gera imagem de um produto via pipeline estruturado",
    description=(
        "Executa o pipeline completo para **um único produto**:\n\n"
        "1. **Baseline** — prompt mínimo: `product photo of {nome}`\n"
        "2. **Estruturado** — Gemini extrai atributos visuais → guardrails → SDXL\n\n"
        "Retorna:\n"
        "- Imagem gerada (caminho no servidor)\n"
        "- JSON com atributos Gemini (`objeto`, `cor_principal`, `material`, etc.)\n"
        "- Prompt estruturado completo usado\n"
        "- Métricas de validação OpenCV (resolução, nitidez Laplaciana, IoU)\n"
        "- Comparação baseline × estruturado"
    ),
    tags=["Produtos"],
)
def generate_product_image(req: ProductGenerateRequest) -> GenerateProductResponse:
    from domain.entities.product import Product as DomainProduct

    import hashlib
    product_id = hashlib.md5(req.name.encode()).hexdigest()[:12]
    product = DomainProduct.create(
        name=req.name,
        description=req.description,
        category=req.category,
        product_id=product_id,
    )

    if req.use_mock_gemini:
        gemini_client = MockGeminiClient()
    else:
        from infrastructure.ai.gemini_client import GeminiClient
        gemini_client = GeminiClient()

    sd_client = StableDiffusionClient(backend=req.backend)
    image_repo = FileImageRepository()
    thresholds = QualityThresholds(
        min_resolution_px=settings.MIN_RESOLUTION_PX,
        min_sharpness_variance=settings.MIN_SHARPNESS_VARIANCE,
        min_iou=settings.MIN_IOU,
        central_zone_ratio=settings.CENTRAL_ZONE_RATIO,
    )
    validator = OpenCVValidator(thresholds)
    validate_uc = ValidateImageUseCase(validator, thresholds)
    prompt_service = PromptDomainService()

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

    try:
        baseline_result = generate_baseline.execute(product, product_index=0)
        structured_result = generate_structured.execute(product, product_index=0)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro na geração: {exc}") from exc

    base_ok = getattr(baseline_result.validation, "is_compliant", False) if baseline_result.validation else False
    struct_ok = getattr(structured_result.validation, "is_compliant", False) if structured_result.validation else False

    base_lap = getattr(baseline_result.validation, "sharpness_score", 0.0) if baseline_result.validation else 0.0
    struct_lap = getattr(structured_result.validation, "sharpness_score", 0.0) if structured_result.validation else 0.0
    base_iou = getattr(baseline_result.validation, "iou_score", 0.0) if baseline_result.validation else 0.0
    struct_iou = getattr(structured_result.validation, "iou_score", 0.0) if structured_result.validation else 0.0

    comparacao = {
        "baseline_conforme": base_ok,
        "estruturado_conforme": struct_ok,
        "delta_nitidez": round(struct_lap - base_lap, 2),
        "delta_iou": round(struct_iou - base_iou, 4),
        "melhoria": struct_ok and not base_ok or (struct_iou > base_iou),
    }

    return GenerateProductResponse(
        produto=ProductItem(
            id=product_id,
            name=req.name,
            description=req.description,
            category=req.category,
        ),
        cenario_baseline=_build_scenario_result(baseline_result),
        cenario_estruturado=_build_scenario_result(structured_result),
        comparacao=comparacao,
    )
