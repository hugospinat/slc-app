"""
Module de traitement des fichiers pour l'application SLC
"""

from .association_processor import AssociationProcessor
from .base_processor import BaseProcessor
from .file_processor import FileProcessor
from .ged001_processor import Ged001Processor
from .reg010_processor import Reg010Processor
from .zip_processor import ZipProcessor

__all__ = [
    "FileProcessor",
    "BaseProcessor",
    "ZipProcessor",
    "Reg010Processor",
    "Ged001Processor",
    "AssociationProcessor",
]
