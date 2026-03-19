"""
Interface CLI: ReportPresenter
Formata e imprime no terminal a saída estruturada do pipeline.
"""
from __future__ import annotations

from domain.entities.image_result import ImageResult, Scenario
from domain.entities.product import Product
from application.dtos.pipeline_result_dto import PipelineResultDTO

# Cores ANSI para o terminal
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"

_SEP = "=" * 72


def _ok(flag: bool) -> str:
    return f"{_GREEN}OK{_RESET}" if flag else f"{_RED}FALHA{_RESET}"


class ReportPresenter:
    """Responsável por toda a saída formatada do pipeline no terminal."""

    def print_header(self, backend: str) -> None:
        print(f"\n{_BOLD}{_SEP}{_RESET}")
        print(f"{_BOLD}  TCC — Pipeline de Geração de Imagens para E-commerce{_RESET}")
        print(f"  AKCIT · 2026  |  Antigravity · Clean Architecture + DDD")
        print(f"{_BOLD}{_SEP}{_RESET}")
        print(f"  Modo: {_CYAN}{backend.upper()}{_RESET}\n")

    def print_loading(self, total: int, categories: list[str]) -> None:
        cat_str = ", ".join(categories)
        print(f"[1/4] Carregando dataset...")
        print(f"  Produtos carregados: {_BOLD}{total}{_RESET}  ({cat_str})\n")

    def print_product_progress(
        self,
        idx: int,
        total: int,
        product: Product,
        baseline: ImageResult,
        structured: ImageResult,
    ) -> None:
        """Imprime o resultado de um par (baseline, estruturado) para um produto."""
        print(f"{_BOLD}Produto {idx}/{total}: {product.name} [{product.category}]{_RESET}")

        # Baseline
        b_prompt = (baseline.prompt_used or "")[:70]
        print(f"  {_DIM}[Baseline   ]{_RESET} Prompt: {b_prompt}")

        # Estruturado
        if structured.gemini_attributes:
            print(f"  {_CYAN}[Estruturado]{_RESET} Gemini -> JSON OK | Prompt: {(structured.prompt_used or '')[:60]}")
        else:
            print(f"  {_CYAN}[Estruturado]{_RESET} Prompt: {(structured.prompt_used or '')[:60]}")

        # Caminhos das imagens
        if baseline.image_path:
            print(f"  [Geração   ] baseline:    {baseline.image_path}")
        if structured.image_path:
            print(f"  [Geração   ] estruturado: {structured.image_path}")

        # Validação Baseline
        if baseline.validation:
            v = baseline.validation
            print(
                f"  [Validação ] baseline:    "
                f"resolução={_ok(v.resolution_ok)} | "
                f"nitidez={v.sharpness_score:.1f} {_ok(v.sharpness_ok)} | "
                f"iou={v.iou_score:.2f} {_ok(v.iou_ok)}"
            )
        elif baseline.error:
            print(f"  [Validação ] baseline:    {_RED}ERRO: {baseline.error}{_RESET}")

        # Validação Estruturado
        if structured.validation:
            v = structured.validation
            print(
                f"  [Validação ] estruturado: "
                f"resolução={_ok(v.resolution_ok)} | "
                f"nitidez={v.sharpness_score:.1f} {_ok(v.sharpness_ok)} | "
                f"iou={v.iou_score:.2f} {_ok(v.iou_ok)}"
            )
        elif structured.error:
            print(f"  [Validação ] estruturado: {_RED}ERRO: {structured.error}{_RESET}")

        print()

    def print_final_summary(self, result: PipelineResultDTO, report_path: str) -> None:
        """Imprime o resumo final com a conclusao sobre H1."""
        bl_rate = result.baseline_compliance_rate * 100
        st_rate = result.structured_compliance_rate * 100
        delta = st_rate - bl_rate
        validated = result.hypothesis_validated
        threshold = result.hypothesis_threshold * 100
        min_delta = result.hypothesis_min_delta * 100
        rule_delta = (
            f"superior ao baseline por >= {min_delta:.1f}pp"
            if result.hypothesis_min_delta > 0
            else "superior ao baseline"
        )

        print(f"\n{_BOLD}{_SEP}{_RESET}")
        print(f"{_BOLD}  RESUMO FINAL DO EXPERIMENTO{_RESET}")
        print(f"{_SEP}")
        print(
            f"  Cenário Baseline:    {_BOLD}{bl_rate:.1f}%{_RESET}"
            f"  ({result.baseline_compliant_count}/{result.products_total})"
        )
        print(
            f"  Cenário Estruturado: {_BOLD}{st_rate:.1f}%{_RESET}"
            f"  ({result.structured_compliant_count}/{result.products_total})"
            f"  -> H1 {'VALIDADA' if validated else 'NAO VALIDADA'} (>= {threshold:.0f}% e {rule_delta})"
        )
        print(f"  Delta: {_GREEN if delta > 0 else _RED}{delta:+.1f} pontos percentuais{_RESET}")
        print()
        if validated:
            print(f"  {_GREEN}{_BOLD}Conclusao: fluxo ESTRUTURADO SUPERIOR ao baseline{_RESET}")
            print(f"  {_GREEN}  H1 aceita - a decomposicao semantica + guardrails melhora a qualidade{_RESET}")
        else:
            reasons: list[str] = []
            if result.structured_compliance_rate < result.hypothesis_threshold:
                reasons.append(f"taxa_estruturado < {threshold:.0f}%")
            if result.structured_compliance_rate <= result.baseline_compliance_rate:
                reasons.append("taxa_estruturado <= taxa_baseline")
            if (result.structured_compliance_rate - result.baseline_compliance_rate) < result.hypothesis_min_delta:
                reasons.append(f"delta < {min_delta:.1f}pp")

            details = f" ({', '.join(reasons)})" if reasons else ""
            print(f"  {_YELLOW}Conclusao: H1 NAO validada{details}{_RESET}")
            print(f"  {_YELLOW}  H0 nao refutada - revisar parametros e dataset{_RESET}")
        print()
        print(f"  Relatório completo: {_CYAN}{report_path}{_RESET}")
        print(f"{_BOLD}{_SEP}{_RESET}\n")
