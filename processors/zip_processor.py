import os
import shutil
import tempfile
import zipfile
from typing import List

from .base_processor import BaseProcessor


class ZipProcessor(BaseProcessor):
    """Processeur pour l'extraction et la gestion des fichiers ZIP"""

    dir_path: str

    def __init__(self):
        super().__init__()

    def extract_zip(self, zip_path: str) -> str:
        """Extraire un fichier ZIP et retourner le répertoire d'extraction"""
        # Créer un répertoire temporaire unique
        extract_dir = tempfile.mkdtemp(prefix="charge_extract_")

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            self.log_success(f"ZIP extrait vers: {extract_dir}")
        except Exception as e:
            self.log_error(f"Erreur lors de l'extraction du ZIP: {e}")
            # Nettoyer en cas d'erreur
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir, ignore_errors=True)
            raise
        self.dir_path = extract_dir
        return extract_dir

    def find_pattern_pdfs(self, pattern: str) -> List[str]:
        """Trouver tous les fichiers PDF contenant un motif dans le nom"""
        pdf_files = []

        for root, dirs, files in os.walk(self.dir_path):
            for file in files:
                if file.lower().endswith(".pdf") and pattern in file:
                    pdf_files.append(os.path.join(root, file))

        self.log_info(f"Fichiers trouvés avec le motif '{pattern}': {len(pdf_files)}")
        return pdf_files

    def find_unique_pattern_pdfs(self, pattern: str) -> str | None:
        """Trouver le fichier PDF contenant un motif unique dans le nom"""
        results = self.find_pattern_pdfs(pattern)
        self.log_info(f"Fichiers trouvés avec le motif '{pattern}': {len(results)}")
        if not results:
            self.log_warning(f"Aucun fichier trouvé avec le motif '{pattern}'")
        if len(results) > 1:
            self.log_warning(f"Plusieurs fichiers trouvés avec le motif '{pattern}': {results}")
        return results[0] if len(results) == 1 else None

    def cleanup_directory(self):
        """Nettoyer un répertoire temporaire"""
        if self.dir_path and os.path.exists(self.dir_path):
            try:
                shutil.rmtree(self.dir_path, ignore_errors=True)
                self.log_info(f"Répertoire temporaire nettoyé: {self.dir_path}")
            except Exception as e:
                self.log_warning(f"Impossible de nettoyer le répertoire {self.dir_path}: {e}")
