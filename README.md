# TCC Pipeline — Geração Automatizada de Imagens de Produto para E-commerce


---

## Estrutura do Projeto

```
tcc_pipeline/
├── domain/                    # Entidades, VOs, interfaces, serviços de domínio
│   ├── entities/              # Product, ImageResult, ValidationResult
│   ├── value_objects/         # Prompt, QualityThresholds
│   ├── repositories/          # IProductRepository, IImageRepository (interfaces)
│   └── services/              # PromptDomainService (guardrails)
│
├── application/               # Casos de uso e DTOs
│   ├── use_cases/             # RunPipeline, GenerateBaseline, GenerateStructured, ValidateImage
│   └── dtos/                  # PipelineResultDTO, ImageResultDTO, ValidationDTO
│
├── infrastructure/            # Implementações concretas
│   ├── config/settings.py     # ← Único arquivo de configuração
│   ├── ai/                    # GeminiClient, StableDiffusionClient (3 backends)
│   ├── cv/                    # OpenCVValidator (resolução, Laplaciano, IoU)
│   ├── persistence/           # CSVProductRepository, FileImageRepository
│   └── reporting/             # JsonReporter → relatorio_final.json
│
├── interface/cli/             # Ponto de entrada
│   ├── pipeline.py            # ← EXECUTE ESTE ARQUIVO
│   └── report_presenter.py    # Saída formatada no terminal
│
├── data/
│   └── amazon_brasil.csv      # ← Coloque o dataset Kaggle aqui
├── output/
│   ├── imagens/               # PNGs gerados (baseline + estruturado)
│   └── relatorios/            # relatorio_final.json
├── .env.example               # Template de variáveis de ambiente
└── requirements.txt
```

---

## Instalação

```powershell
# 1. Ambiente virtual
python -m venv venv
venv\Scripts\Activate.ps1

# 2. Dependências base
pip install -r requirements.txt

# 3. (Opcional) GPU local NVIDIA >= 8GB
pip install diffusers transformers accelerate
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

---

## Configuração

```powershell
# Copie o template de variáveis de ambiente
copy .env.example .env
```

Edite o `.env` com suas chaves:

| Variável | Obrigatória | Onde obter |
|---|---|---|
| `GEMINI_API_KEY` | Sim | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `STABILITY_API_KEY` | Só se `SD_BACKEND=api` | [Stability AI](https://platform.stability.ai/account/keys) |
| `SD_BACKEND` | Não (padrão: `mock`) | `mock` / `api` / `local` |

---

## Execução

### Teste 1 — Mock completo (sem custo, sem API)
```powershell
python -m interface.cli.pipeline --mock
# (alternativo) python pipeline.py --mock
```

### Teste 2 — Gemini real + imagens mock
```powershell
# Exige GEMINI_API_KEY no .env
python -m interface.cli.pipeline --backend mock data/amazon_brasil.csv
# (alternativo) python pipeline.py --backend mock data/amazon_brasil.csv
```

### Teste 3 — Execução completa via Stability AI
```powershell
# Exige GEMINI_API_KEY + STABILITY_API_KEY no .env
python -m interface.cli.pipeline --backend api data/amazon_brasil.csv
# (alternativo) python pipeline.py --backend api data/amazon_brasil.csv
```

### Teste 4 — Execução completa via GPU local
```powershell
python -m interface.cli.pipeline --backend local data/amazon_brasil.csv
# (alternativo) python pipeline.py --backend local data/amazon_brasil.csv
```

---

## Métricas de Conformidade (Seção 06 do guia metodológico)

| Métrica | Limiar | Ferramenta | Fórmula |
|---|---|---|---|
| Resolução | ≥ 1000×1000 px | OpenCV/Pillow | `img.shape` |
| Nitidez | Var ≥ 100 | Laplaciano | `cv2.Laplacian(gray, CV_64F).var()` |
| Centralização | IoU ≥ 0.50 | HSV mask + BBox | `Intersec / União` |

---

## Design Experimental

| | **BASELINE** (H₀) | **ESTRUTURADO** (H₁) |
|---|---|---|
| Gemini | NÃO | SIM |
| Guardrails | NÃO | SIM |
| Prompt | Nome do produto | Atributos + guardrails |
| Hipótese | conformidade < 50% | conformidade ≥ 50% |

**H₁ é validada** se `taxa_conformidade_estruturado ≥ 50%` E superar o baseline por margem relevante.

---

## Relatório de Saída

O arquivo `output/relatorios/relatorio_final.json` contém:
- Bloco `hipotese`: resultado VALIDADA/NAO_VALIDADA
- Bloco `baseline` e `estruturado`: taxas, médias de nitidez e IoU
- Bloco `comparacao`: delta em pontos percentuais
- Bloco `detalhes_por_produto`: métricas individuais de todas as 30 imagens

---

## API (Swagger)

Este repositório inclui uma API local com FastAPI para executar o pipeline e acompanhar o status.

### Subir a API

```powershell
venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python -m uvicorn interface.api.app:app --reload --host 127.0.0.1 --port 8000
```

### Abrir o Swagger

- Swagger UI: http://127.0.0.1:8000/docs
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json

### Rodar o pipeline via API

No Swagger, use `POST /pipeline/run` e depois acompanhe em `GET /pipeline/status`.

Exemplos de body:

```json
{ "backend": "mock", "use_mock_products": true, "use_mock_gemini": true }
```

```json
{ "backend": "mock", "use_mock_products": false, "csv_path": "data/amazon_brasil.csv", "use_mock_gemini": false }
```
