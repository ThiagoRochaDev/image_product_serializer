"""
Infrastructure: JsonReporter
Gera o arquivo output/relatorios/relatorio_final.json
com a estrutura de evidências do TCC.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from application.dtos.pipeline_result_dto import PipelineResultDTO
from infrastructure.config import settings


class JsonReporter:
    """
    Serializa o PipelineResultDTO no formato JSON definido na Seção 12
    do guia metodológico do TCC.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or settings.REPORTS_DIR
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, result: PipelineResultDTO, filename: str = "relatorio_final.json") -> str:
        """
        Gera o relatório completo e retorna o caminho do arquivo salvo.
        """
        report = self._build_report(result)
        target = self._output_dir / filename
        with open(target, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return str(target.resolve())

    def _build_report(self, r: PipelineResultDTO) -> dict:
        now = datetime.now(tz=timezone.utc).isoformat()

        baseline_sharpness = r.avg_metric(r.baseline_results, "sharpness_score")
        structured_sharpness = r.avg_metric(r.structured_results, "sharpness_score")
        baseline_iou = r.avg_metric(r.baseline_results, "iou_score")
        structured_iou = r.avg_metric(r.structured_results, "iou_score")

        return {
            "meta": {
                "gerado_em": now,
                "total_produtos": r.products_total,
                "total_imagens": r.images_total,
                "categorias": r.categories,
                "metricas": ["resolucao", "nitidez_laplaciano", "centralizacao_iou"],
                "limiares": {
                    "resolucao_minima_px": settings.MIN_RESOLUTION_PX,
                    "nitidez_minima_variancia": settings.MIN_SHARPNESS_VARIANCE,
                    "iou_minimo": settings.MIN_IOU,
                },
            },
            "hipotese": {
                "limiar_conformidade": r.hypothesis_threshold,
                "margem_minima": r.hypothesis_min_delta,
                "resultado": "VALIDADA" if r.hypothesis_validated else "NAO_VALIDADA",
                "cenario_avaliado": "estruturado",
                "h1_aceita": r.hypothesis_validated,
                "h0_refutada": r.hypothesis_validated,
            },
            "baseline": {
                "taxa_conformidade": round(r.baseline_compliance_rate, 4),
                "conformes": r.baseline_compliant_count,
                "nao_conformes": r.products_total - r.baseline_compliant_count,
                "media_nitidez": round(baseline_sharpness, 2),
                "media_iou": round(baseline_iou, 4),
                "resolucao_100pct": all(
                    res.validation.resolution_ok
                    for res in r.baseline_results
                    if res.validation
                ),
            },
            "estruturado": {
                "taxa_conformidade": round(r.structured_compliance_rate, 4),
                "conformes": r.structured_compliant_count,
                "nao_conformes": r.products_total - r.structured_compliant_count,
                "media_nitidez": round(structured_sharpness, 2),
                "media_iou": round(structured_iou, 4),
                "resolucao_100pct": all(
                    res.validation.resolution_ok
                    for res in r.structured_results
                    if res.validation
                ),
            },
            "comparacao": {
                "delta_taxa_conformidade": round(
                    r.structured_compliance_rate - r.baseline_compliance_rate, 4
                ),
                "delta_nitidez": round(structured_sharpness - baseline_sharpness, 2),
                "delta_iou": round(structured_iou - baseline_iou, 4),
                "melhoria_percentual": f"{(r.structured_compliance_rate - r.baseline_compliance_rate) * 100:+.1f}pp",
                "estruturado_superior": r.structured_compliance_rate > r.baseline_compliance_rate,
            },
            "detalhes_por_produto": {
                "baseline": [res.to_dict() if hasattr(res, "to_dict") else _dto_to_dict(res) for res in r.baseline_results],
                "estruturado": [res.to_dict() if hasattr(res, "to_dict") else _dto_to_dict(res) for res in r.structured_results],
            },
        }


def _dto_to_dict(dto) -> dict:
    """Serializa ImageResultDTO para dict."""
    return {
        "produto_id": dto.product_id,
        "produto_nome": dto.product_name,
        "cenario": dto.scenario,
        "caminho_imagem": dto.image_path,
        "prompt_utilizado": dto.prompt_used,
        "atributos_gemini": dto.gemini_attributes,
        "validacao": {
            "resolucao_ok": dto.validation.resolution_ok,
            "resolucao_dimensoes": f"{dto.validation.width}x{dto.validation.height}",
            "nitidez_laplaciano": round(dto.validation.sharpness_score, 2),
            "nitidez_ok": dto.validation.sharpness_score >= settings.MIN_SHARPNESS_VARIANCE,
            "centralizacao_iou": round(dto.validation.iou_score, 4),
            "centralizacao_ok": dto.validation.iou_score >= settings.MIN_IOU,
            "conforme": dto.validation.is_compliant,
        } if dto.validation else None,
        "erro": dto.error,
    }
