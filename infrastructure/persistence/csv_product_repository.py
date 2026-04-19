"""
Infrastructure: CSVProductRepository
Implementa IProductRepository lendo o dataset Kaggle (Amazon Brasil) via Pandas.
Faz amostragem estratificada: 5 produtos por categoria, randomizada com seed fixa.
"""
from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path
from typing import List

import pandas as pd

from domain.entities.product import Product
from domain.repositories.product_repository import IProductRepository

# Mapeamento de colunas — ajuste conforme o CSV real do Kaggle
_COLUMN_MAP = {
    "name": ["product_name", "nome", "name", "title", "product_title", "titulo"],
    "description": ["product_description", "description", "descricao", "about_product", "description_product"],
    "category": ["category", "categoria", "product_category", "main_category", "categoryname", "category_name"],
}

_RANDOM_SEED = 42


def _strip_accents(text) -> str:
    if not isinstance(text, str):
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


class CSVProductRepository(IProductRepository):
    """
    Repositório que carrega os dados do CSV Kaggle e retorna amostras estratificadas.
    Tolerante a variações nos nomes das colunas do dataset.
    """

    def __init__(self, csv_path: str | Path) -> None:
        self._csv_path = Path(csv_path)
        if not self._csv_path.exists():
            raise FileNotFoundError(
                f"CSV não encontrado: {self._csv_path}\n"
                "Baixe o dataset Amazon Brasil do Kaggle e coloque em data/"
            )
        self._df = self._load_and_normalize()

    # ─────────────────────────────────────────────────────────
    # Interface pública
    # ─────────────────────────────────────────────────────────
    def get_stratified_sample(
        self,
        categories: List[str],
        samples_per_category: int = 5,
    ) -> List[Product]:
        products: list[Product] = []
        for category in categories:
            cat_df = self._filter_category(category)
            n = min(samples_per_category, len(cat_df))
            if n == 0:
                continue
            sampled = cat_df.sample(n=n, random_state=_RANDOM_SEED)
            for _, row in sampled.iterrows():
                products.append(self._row_to_product(row, category))
        return products

    def count_by_category(self, category: str) -> int:
        return len(self._filter_category(category))

    # ─────────────────────────────────────────────────────────
    # Helpers privados
    # ─────────────────────────────────────────────────────────
    def _load_and_normalize(self) -> pd.DataFrame:
        """Carrega o CSV e normaliza os nomes das colunas."""
        df = pd.read_csv(self._csv_path, encoding="utf-8", on_bad_lines="skip")
        df.columns = [c.strip().lower() for c in df.columns]

        # Resolve nomes de colunas alternativos
        col_mapping: dict[str, str] = {}
        for canonical, variants in _COLUMN_MAP.items():
            for variant in variants:
                if variant in df.columns:
                    col_mapping[variant] = canonical
                    break

        df = df.rename(columns=col_mapping)

        # Mantém apenas colunas relevantes
        keep = [c for c in ["name", "description", "category", "imgurl"] if c in df.columns]
        df = df[keep].dropna(subset=["name"])
        df["description"] = df.get("description", pd.Series([""] * len(df))).fillna("")
        df["category"] = df.get("category", pd.Series(["geral"] * len(df))).fillna("geral")
        df["imgurl"] = df.get("imgurl", pd.Series([""] * len(df))).fillna("")
        df["category_normalized"] = df["category"].str.lower().str.strip().apply(_strip_accents)
        return df

    def _filter_category(self, category: str) -> pd.DataFrame:
        """Filtra produtos pela categoria, tolerando diferenças de caixa e acentos."""
        cat_lower = _strip_accents(category.lower().strip())
        return self._df[self._df["category_normalized"].str.contains(cat_lower, na=False, regex=False)]

    @staticmethod
    def _row_to_product(row: pd.Series, category: str) -> Product:
        """Converte uma linha do DataFrame em entidade Product."""
        name = str(row.get("name", "Produto sem nome")).strip()
        description = str(row.get("description", "")).strip()
        image_url = str(row.get("imgurl", "")).strip()
        product_id = hashlib.md5(name.encode()).hexdigest()[:12]
        return Product.create(
            name=name,
            description=description,
            category=category,
            product_id=product_id,
            image_url=image_url,
        )
