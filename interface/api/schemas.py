"""
Interface API: Schemas Pydantic para request/response
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ─── Request Bodies ───────────────────────────────────────────────────────────

class ProductRequest(BaseModel):
    """Corpo da requisição para geração de imagem de um único produto."""
    name: str = Field(..., example="Samsung Galaxy S23 128GB Preto")
    description: str = Field("", example="Smartphone premium com câmera tripla")
    category: str = Field(..., example="eletronicos")


class PipelineRunRequest(BaseModel):
    """Opções para execução do pipeline completo."""
    backend: str = Field("mock", description="Backend SDXL: mock | api | local", example="mock")
    use_mock_products: bool = Field(
        True,
        description="Se True, usa produtos fictícios internos (não precisa de CSV)"
    )
    use_mock_gemini: bool = Field(
        False,
        description="Se True, usa Gemini fake (não chama a API Gemini)",
        example=False,
    )
    csv_path: Optional[str] = Field(
        None,
        description="Caminho para o CSV Kaggle (necessário quando use_mock_products=False)",
        example="data/amazon_brasil.csv"
    )


# ─── Response Bodies ──────────────────────────────────────────────────────────

class ValidationResponse(BaseModel):
    resolucao_ok: bool
    resolucao_dimensoes: str
    nitidez_laplaciano: float
    nitidez_ok: bool
    centralizacao_iou: float
    centralizacao_ok: bool
    conforme: bool
    score_conformidade: float


class ImageResultResponse(BaseModel):
    produto_id: str
    produto_nome: str
    cenario: str
    caminho_imagem: Optional[str]
    prompt_utilizado: Optional[str]
    atributos_gemini: Optional[dict]
    validacao: Optional[ValidationResponse]
    erro: Optional[str]
    conforme: bool


class GeminiAttributesResponse(BaseModel):
    objeto: Optional[str]
    cor_principal: Optional[str]
    material: Optional[str]
    formato: Optional[str]
    detalhes_visuais: Optional[str]
    categoria_visual: Optional[str]


class PromptResponse(BaseModel):
    baseline: str
    estruturado: str
    gemini_attributes: Optional[dict]
    baseline_word_count: int
    estruturado_word_count: int


class PipelineStatus(BaseModel):
    status: str                  # "running" | "completed" | "idle"
    produtos_processados: int
    total_produtos: int
    baseline_conformes: int
    estruturado_conformes: int
    taxa_baseline: float
    taxa_estruturado: float
    hipotese_validada: Optional[bool]
    relatorio_path: Optional[str]


class ImageUploadValidationResponse(BaseModel):
    """Resultado da análise de uma imagem enviada via upload."""
    resolucao_ok: bool = Field(..., description="Resolução ≥ 1000×1000 px")
    resolucao_dimensoes: str = Field(..., description="Dimensões reais da imagem (LxA)")
    nitidez_laplaciano: float = Field(..., description="Variância Laplaciana (nitidez)")
    nitidez_ok: bool = Field(..., description="Nitidez ≥ threshold mínimo")
    centralizacao_iou: float = Field(..., description="IoU produto vs. zona central")
    centralizacao_ok: bool = Field(..., description="IoU ≥ 0.50")
    conforme: bool = Field(..., description="True se TODAS as métricas passarem")
    score_conformidade: float = Field(..., description="Proporção de métricas aprovadas (0.0 a 1.0)")
