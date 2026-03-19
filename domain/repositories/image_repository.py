"""
Domain Repository Interface: IImageRepository
Contrato para persistência de imagens geradas.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class IImageRepository(ABC):
    """
    Interface de repositório de imagens.
    Desacopla a lógica de geração do mecanismo de persistência.
    """

    @abstractmethod
    def save(self, image_bytes: bytes, filename: str) -> str:
        """
        Persiste os bytes de uma imagem e retorna o caminho absoluto do arquivo salvo.

        Args:
            image_bytes: conteúdo binário da imagem PNG
            filename: nome do arquivo desejado (sem extensão de diretório)

        Returns:
            Caminho absoluto para o arquivo salvo
        """
        ...

    @abstractmethod
    def exists(self, filename: str) -> bool:
        """Verifica se um arquivo de imagem já existe (usado para reprocessamento)."""
        ...
