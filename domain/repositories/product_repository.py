"""
Domain Repository Interface: IProductRepository
Contrato que a camada de infraestrutura deve implementar para fornecer produtos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from domain.entities.product import Product


class IProductRepository(ABC):
    """
    Interface de repositório de produtos — princípio de inversão de dependência (DIP).
    A camada de domínio não sabe se os dados vêm de CSV, banco de dados ou mock.
    """

    @abstractmethod
    def get_stratified_sample(
        self,
        categories: List[str],
        samples_per_category: int = 5,
    ) -> List[Product]:
        """
        Retorna uma amostra estratificada de produtos.

        Args:
            categories: lista de categorias a incluir
            samples_per_category: número de produtos por categoria

        Returns:
            Lista de produtos amostrados (total = len(categories) × samples_per_category)
        """
        ...

    @abstractmethod
    def count_by_category(self, category: str) -> int:
        """Retorna o total de produtos disponíveis para uma categoria."""
        ...
