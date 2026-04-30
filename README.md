# TCC Pipeline — Geração Automatizada de Imagens de Produto para E-commerce

**AKCIT · 2026 · Thiago Guimarães Rocha · Thiago Soares da Cruz · Washington Luiz dos Santos**

---

## O que este projeto resolve

Plataformas de e-commerce como a Amazon Brasil exigem padrões técnicos mínimos para a imagem principal de cada produto: fundo branco, produto centralizado, resolução mínima de 1000×1000 px e nitidez comercial. Cumprir esses requisitos manualmente — com sessão fotográfica, tratamento de imagem e revisão — tem custo alto e não escala.

Este projeto implementa um **pipeline de três estágios** que automatiza essa geração:

1. **Estágio 1 — Decomposição semântica (Gemini 2.5 Flash Lite):** dado o nome, descrição e categoria do produto, o modelo de linguagem extrai atributos visuais estruturados em JSON — objeto, cor, material, formato e detalhes — que um prompt simples não capturaria.
2. **Estágio 2 — Geração de imagem (Stable Diffusion XL):** o prompt enriquecido com os atributos do Gemini e um conjunto fixo de guardrails de qualidade é enviado ao modelo de difusão, que gera uma imagem 1024×1024 px.
3. **Estágio 3 — Validação automática (OpenCV):** cada imagem gerada é avaliada em três métricas objetivas — resolução, nitidez (variância Laplaciana) e centralização (IoU) — e classificada como conforme ou não conforme.

O pipeline processa cada produto em **dois cenários paralelos** para validação científica:

| Cenário | Prompt | Gemini | Guardrails | Hipótese |
|---|---|---|---|---|
| **Baseline** (controle) | `english_name` do produto (mínimo) | Compartilhado | Não | H₀: conformidade < 50% |
| **Estruturado** (tratamento) | Atributos visuais + guardrails | Compartilhado | Sim | H₁: conformidade ≥ 50% |

> **Nota:** O Gemini é chamado **uma vez por produto** e o resultado é compartilhado entre os dois cenários. O baseline usa apenas o `english_name` extraído (prompt mínimo em inglês, compatível com todas as APIs de geração). O estruturado usa todos os atributos visuais. O Gemini é **multimodal**: quando o produto tem `imgUrl` no CSV, a foto real do produto é enviada junto ao texto para extrair atributos visuais com maior fidelidade.

A diferença de conformidade entre os dois cenários é a **evidência central do TCC**: provar que o fluxo estruturado gera imagens de qualidade comercial de forma consistente e superior ao fluxo sem estruturação.

---

## Como funciona — fluxo completo

```
data/amazon_brasil.csv
        |
        v
CSVProductRepository ──► amostragem estratificada (5 × 3 categorias = 15 produtos)
        |
        +──────────────────────────────────────────────+
        |                                              |
        v                                              v
  CENÁRIO BASELINE                          CENÁRIO ESTRUTURADO
  "product photo of {english_name}"   Gemini ──► {english_name, objeto, cor, ...}
        |                            (texto + foto real via imgUrl)
        v                                    PromptDomainService
  Gerador de Imagens                     (atributos + 5 guardrails fixos)
        |                                              |
        v                                              v
  output/imagens/                          Stable Diffusion XL
  produto_001_baseline.png                       |
        |                                          v
        |                               output/imagens/
        |                               produto_001_estruturado.png
        |                                          |
        +──────────────────────────────────────────+
                            |
                            v
                    OpenCV Validator
              resolução / nitidez / IoU
                            |
                            v
              output/relatorios/relatorio_final.json
              taxa_baseline vs taxa_estruturado
              H₀ refutada? H₁ validada?
```

### Os 5 Guardrails fixos (aplicados em todo prompt estruturado)

| Guardrail | Por que existe |
|---|---|
| `pure white background` | Exigência da Amazon Brasil para imagem principal |
| `soft studio lighting, even illumination` | Evita sombras duras que prejudicam a leitura do produto |
| `centered, front view, full product visible` | Garante que o produto ocupe o centro — diretamente relacionado à métrica IoU |
| `professional product photography, commercial grade` | Direciona o estilo estético do modelo |
| `high resolution, sharp focus, 8k` | Instrui o modelo a priorizar nitidez — relacionado à métrica Laplaciana |

### As 3 métricas de conformidade (OpenCV)

Uma imagem só é **conforme** se passar nas três simultaneamente:

| Métrica | Limiar | Fórmula |
|---|---|---|
| Resolução | ≥ 1000×1000 px | `img.shape[0] >= 1000 and img.shape[1] >= 1000` |
| Nitidez | Variância Laplaciana ≥ 100 | `cv2.Laplacian(gray, CV_64F).var()` |
| Centralização | IoU ≥ 0.50 | `Intersecção(bbox_produto, zona_central_70%) / União` |

---

## Estrutura de arquivos

```
image_product_serializer/
├── domain/                        # Regras de negócio puras, sem dependências externas
│   ├── entities/                  # Product, ImageResult, ValidationResult
│   ├── value_objects/             # Prompt, QualityThresholds
│   ├── repositories/              # Interfaces IProductRepository, IImageRepository
│   └── services/                  # PromptDomainService — monta prompts e aplica guardrails
│
├── application/                   # Orquestração dos casos de uso
│   ├── use_cases/                 # RunPipeline, GenerateBaseline, GenerateStructured, ValidateImage
│   └── dtos/                      # PipelineResultDTO — agrega resultados e calcula hipótese
│
├── infrastructure/                # Implementações concretas (APIs, arquivos, banco)
│   ├── config/settings.py         # Único arquivo de configuração — limiares, modelos, paths
│   ├── ai/gemini_client.py        # Chama Gemini 2.5 Flash Lite e devolve JSON de atributos
│   ├── ai/stable_diffusion_client.py  # 4 backends: mock / Stability AI API / HuggingFace / GPU local
│   ├── cv/opencv_validator.py     # Aplica as 3 métricas em cada imagem gerada
│   ├── persistence/               # CSVProductRepository (Kaggle), FileImageRepository
│   └── reporting/json_reporter.py # Gera relatorio_final.json
│
├── interface/
│   ├── cli/pipeline.py            # Ponto de entrada da linha de comando
│   └── api/app.py                 # API FastAPI com Swagger
│
├── data/
│   └── amazon_brasil.csv          # Base de produtos — substitua pelo dataset real do Kaggle
├── output/
│   ├── imagens/                   # PNGs gerados (produto_001_baseline.png, _estruturado.png)
│   └── relatorios/                # relatorio_final.json
├── .env.example                   # Template de variáveis de ambiente
└── requirements.txt
```

---

## Instalação

```powershell
# 1. Ambiente virtual
python -m venv venv
venv\Scripts\Activate.ps1          # Windows
# source venv/bin/activate         # Linux / Mac

# 2. Dependências base (sem GPU)
pip install -r requirements.txt

# 3. Backend HuggingFace — gratuito, recomendado
pip install huggingface-hub

# 4. GPU local NVIDIA >= 8GB VRAM (opcional)
pip install diffusers transformers accelerate
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

---

## Configuração

```powershell
copy .env.example .env
```

Edite o `.env`:

| Variável | Obrigatória                                     | Onde obter |
|---|-------------------------------------------------|---|
| `GEMINI_API_KEY` | Sim (exceto `--mock`)                           | [Google AI Studio](https://aistudio.google.com/app/apikey) — tier gratuito |
| `HF_API_KEY` | Só se `SD_BACKEND=hf`                           | [HuggingFace Settings](https://huggingface.co/settings/tokens) — token Read, gratuito |
| `STABILITY_API_KEY` | Só se `SD_BACKEND=api`                          | [Stability AI](https://platform.stability.ai/account/keys) — pago por crédito |
| `HF_MODEL_ID` | Não (padrão: `black-forest-labs/FLUX.1-schnell`) | ID de qualquer modelo de texto-para-imagem no HuggingFace |
| `SD_BACKEND` | Não (padrão: `mock`)                            | `mock` / `hf` / `api` / `local` |
| `OPENCV_DUMP_CONFIG` | Não (padrão: 1)                                 | |

### Dataset Amazon Brasil

O arquivo `data/amazon_brasil.csv` [amazon_brasil AI](https://www.kaggle.com/datasets/asaniczka/amazon-brazil-products-2023-1-3m-products?resource=download) já vem com 15 produtos de exemplo prontos para uso. Para usar o dataset real do Kaggle (Amazon Brasil), baixe o CSV e substitua o arquivo — o repositório já faz o mapeamento automático das colunas.

---

## Executando via linha de comando

### Modo 1 — Mock completo (sem custo, sem API, ideal para testar o pipeline)
```powershell
python -m interface.cli.pipeline --mock
```
Gera imagens placeholder e valida toda a lógica sem consumir nenhuma cota de API.

### Modo 2 — Gemini real + imagens mock (valida a extração de atributos)
```powershell
python -m interface.cli.pipeline --backend mock data/amazon_brasil.csv
```
Chama o Gemini de verdade para extrair atributos, mas usa imagens placeholder. Útil para validar a qualidade dos prompts gerados sem custo de geração.

### Modo 3 — Execução completa via Stability AI
```powershell
python -m interface.cli.pipeline --backend api data/amazon_brasil.csv
```
Pipeline completo. Gera as 30 imagens reais (15 baseline + 15 estruturado) via Stability AI (~R$ 3,00 no total).

### Modo 4 — Execução completa via GPU local
```powershell
python -m interface.cli.pipeline --backend local data/amazon_brasil.csv
```
Mesmo resultado do modo 3, sem custo por imagem (requer NVIDIA >= 8GB VRAM com CUDA).

### Saída esperada no terminal

```
================================================================
  TCC — Pipeline de Geracao de Imagens para E-commerce
  AKCIT 2026
================================================================
  Modo: COMPLETO (Gemini + Stable Diffusion)

[1/4] Carregando dataset...
  Produtos carregados: 15 (5 eletronicos, 5 vestuario, 5 utensilios)

Produto 1/15: Samsung Galaxy S23 128GB Preto [eletronicos]
  [Baseline]    Prompt: product photo of Samsung Galaxy S23...
  [Estruturado] Gemini -> JSON OK | Prompt: black aluminum smartphone...
  [Geracao]     baseline:    output/imagens/produto_001_baseline.png
  [Geracao]     estruturado: output/imagens/produto_001_estruturado.png
  [Validacao]   baseline:    resolucao=OK | nitidez=82.3 FALHA | iou=0.41 FALHA
  [Validacao]   estruturado: resolucao=OK | nitidez=148.7 OK   | iou=0.78 OK

...

================================================================
  RESUMO FINAL DO EXPERIMENTO
  Cenario Baseline:    33.3%  (5/15)  -> H0 nao refutada por este cenario
  Cenario Estruturado: 80.0%  (12/15) -> H1 VALIDADA (>= 50%)
  Delta: +46.7 pontos percentuais
  Conclusao: fluxo estruturado SUPERIOR ao baseline
================================================================
```

---

## Executando via API (Swagger)

### Subir o servidor

```powershell
venv\Scripts\Activate.ps1
python -m uvicorn interface.api.app:app --reload --host 127.0.0.1 --port 8000
```

Abra no navegador: **http://127.0.0.1:8000/docs**

### Endpoints disponíveis

#### `GET /products` — listar produtos da base Amazon Brasil

Lista os produtos do CSV com suporte a filtro por categoria e paginação.

```
GET /products?category=eletronicos&limit=10&offset=0
```

Resposta:
```json
{
  "products": [
    {
      "id": "fe9c52e9192c",
      "name": "Samsung Galaxy S23 128GB Preto",
      "description": "Smartphone premium com camera tripla, 8GB RAM, tela 120Hz.",
      "category": "eletronicos"
    }
  ],
  "total": 5,
  "csv_path": "data/amazon_brasil.csv"
}
```

#### `POST /product/generate` — gerar imagem de um produto com pipeline estruturado

Executa o pipeline completo para **um único produto** e retorna em uma chamada:
- Imagem baseline gerada (path no servidor)
- Imagem estruturada gerada (path no servidor)
- Atributos extraídos pelo Gemini (`objeto`, `cor_principal`, `material`, `formato`, `detalhes_visuais`)
- Prompt estruturado completo com guardrails
- Métricas OpenCV das duas imagens (resolução, nitidez Laplaciana, IoU)
- Comparação direta baseline × estruturado

Body da requisição:
```json
{
  "name": "Samsung Galaxy S23 128GB Preto",
  "description": "Smartphone premium com camera tripla, 8GB RAM",
  "category": "eletronicos",
  "backend": "mock",
  "use_mock_gemini": false
}
```

Resposta completa:
```json
{
  "produto": {
    "id": "fe9c52e9192c",
    "name": "Samsung Galaxy S23 128GB Preto",
    "description": "Smartphone premium com camera tripla, 8GB RAM",
    "category": "eletronicos"
  },
  "cenario_baseline": {
    "prompt": "product photo of Samsung Galaxy S23 128GB Preto",
    "imagem_path": "output/imagens/produto_000_baseline.png",
    "atributos_gemini": null,
    "resolucao_ok": true,
    "resolucao_dimensoes": "1024x1024",
    "nitidez_laplaciano": 82.3,
    "nitidez_ok": false,
    "centralizacao_iou": 0.41,
    "centralizacao_ok": false,
    "conforme": false,
    "score_conformidade": 0.333
  },
  "cenario_estruturado": {
    "prompt": "black aluminum smartphone, glossy AMOLED screen, triple camera module, USB-C port,\npure white background,\nsoft studio lighting, even illumination,\ncentered, front view, full product visible,\nprofessional product photography, commercial grade,\nhigh resolution, sharp focus, 8k",
    "imagem_path": "output/imagens/produto_000_estruturado.png",
    "atributos_gemini": {
      "objeto": "smartphone",
      "cor_principal": "black",
      "material": "glass and aluminum",
      "formato": "rectangular slab",
      "detalhes_visuais": "glossy AMOLED screen, triple camera module, USB-C port",
      "categoria_visual": "electronics"
    },
    "resolucao_ok": true,
    "resolucao_dimensoes": "1024x1024",
    "nitidez_laplaciano": 148.7,
    "nitidez_ok": true,
    "centralizacao_iou": 0.78,
    "centralizacao_ok": true,
    "conforme": true,
    "score_conformidade": 1.0
  },
  "comparacao": {
    "baseline_conforme": false,
    "estruturado_conforme": true,
    "delta_nitidez": 66.4,
    "delta_iou": 0.37,
    "melhoria": true
  }
}
```

#### `POST /pipeline/run` — executar o experimento completo (15 produtos)

Dispara o pipeline A/B para todos os produtos do CSV em background e retorna imediatamente.

```json
{ "backend": "mock", "use_mock_products": true, "use_mock_gemini": true }
```

Com CSV real:
```json
{ "backend": "api", "use_mock_products": false, "csv_path": "data/amazon_brasil.csv", "use_mock_gemini": false }
```

#### `GET /pipeline/status` — acompanhar o progresso

Retorna o status atual da execução, taxas de conformidade parciais e, ao terminar, o caminho do relatório JSON.

#### `POST /image/validate` — validar uma imagem existente

Faz upload de qualquer imagem PNG/JPG e retorna as 3 métricas de conformidade OpenCV. Útil para avaliar imagens de outras fontes com os mesmos critérios do pipeline.

---

## Relatório final JSON

O arquivo `output/relatorios/relatorio_final.json` é o documento de evidência do TCC:

```json
{
  "meta": {
    "total_produtos": 15,
    "total_imagens": 30,
    "categorias": ["eletronicos", "vestuario", "utensilios"],
    "metricas": ["resolucao", "nitidez_laplaciano", "centralizacao_iou"]
  },
  "hipotese": {
    "limiar_conformidade": 0.50,
    "resultado": "VALIDADA",
    "cenario_avaliado": "estruturado"
  },
  "baseline": {
    "taxa_conformidade": 0.333,
    "conformes": 5,
    "nao_conformes": 10,
    "media_nitidez": 78.4,
    "media_iou": 0.38
  },
  "estruturado": {
    "taxa_conformidade": 0.800,
    "conformes": 12,
    "nao_conformes": 3,
    "media_nitidez": 138.7,
    "media_iou": 0.72
  },
  "comparacao": {
    "delta_taxa_conformidade": 0.467,
    "delta_nitidez": 60.3,
    "delta_iou": 0.34,
    "melhoria_percentual": "+46.7pp",
    "estruturado_superior": true
  }
}
```

**Como citar na seção Resultados do TCC:**
> "O cenário estruturado atingiu taxa de conformidade de 80% (12/15 produtos), superando o limiar estabelecido de 50% e o cenário baseline de 33,3% em 46,7 pontos percentuais."

---

## Escolha do backend

| Opção | Custo | Velocidade | GPU | Quando usar |
|---|---|---|---|---|
| `mock` | Gratuito | Instantâneo | Não | Testar o pipeline sem custo — imagens placeholder |
| `api` | ~R$ 0,10/img | 10–20 s | Não | Sem GPU local — resultados reais rapidamente |
| `local` | Gratuito | 30–90 s/img | Sim (≥8GB VRAM) | Produção — controle total, sem custo por imagem |

---

## Stack tecnológica

| Tecnologia | Versão | Função |
|---|---|---|
| Python | 3.10+ | Runtime principal |
| FastAPI | 0.135+ | API REST com Swagger |
| Google Gemini | 2.5 Flash Lite | Decomposição semântica em JSON |
| Stable Diffusion XL | SDXL 1.0 | Geração de imagens 1024×1024 px |
| OpenCV | 4.9+ | Validação: Laplaciano, IoU, resolução |
| Pillow | 10+ | Leitura e conversão de imagens |
| Pandas | 2.1+ | Carregamento e amostragem do CSV |
| Pydantic | 2+ | Validação de contratos de dados |
| NumPy | 1.26+ | Operações matriciais nas métricas |
| python-dotenv | 1.0+ | Carregamento seguro de chaves de API |