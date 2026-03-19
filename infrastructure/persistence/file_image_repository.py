"""
Infrastructure: FileImageRepository
Implementa IImageRepository salvando PNGs no filesystem local.
"""
from __future__ import annotations

from pathlib import Path

from domain.repositories.image_repository import IImageRepository
from infrastructure.config import settings


class FileImageRepository(IImageRepository):
    """
    Persiste imagens geradas em output/imagens/ com nomenclatura rastreável.
    Nomenclatura: produto_{index:03d}_{cenario}.png
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or settings.IMAGES_DIR
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, image_bytes: bytes, filename: str) -> str:
        """Salva os bytes e retorna o caminho absoluto."""
        target = self._output_dir / filename
        target.write_bytes(image_bytes)
        return str(target.resolve())

    def exists(self, filename: str) -> bool:
        return (self._output_dir / filename).exists()
