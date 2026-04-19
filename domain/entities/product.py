"""
Domain Entity: Product
Representa um produto do catálogo Amazon Brasil.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Product:
    VALID_CATEGORIES = frozenset({"eletronicos", "vestuario", "utensilios"})

    id: str
    name: str
    description: str
    category: str
    image_url: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Product name cannot be empty.")
        if not self.category or not self.category.strip():
            raise ValueError("Product category cannot be empty.")

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        category: str,
        product_id: str | None = None,
        image_url: str = "",
    ) -> "Product":
        """Factory method para criar um produto com id gerado automaticamente."""
        return cls(
            id=product_id or str(uuid.uuid4()),
            name=name.strip(),
            description=(description or "").strip(),
            category=category.strip().lower(),
            image_url=(image_url or "").strip(),
        )

    def __str__(self) -> str:
        return f"Product(id={self.id[:8]}, name='{self.name}', category='{self.category}')"
