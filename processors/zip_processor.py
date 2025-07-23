import os
import shutil
import tempfile
import zipfile
from typing import List

from .base_processor import BaseProcessor


class ZipProcessor(BaseProcessor):
    """Processeur pour l'extraction et la gestion des fichiers ZIP"""

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

        return extract_dir

    def find_reg010_pdfs(self, directory: str) -> List[str]:
        """Trouver tous les fichiers PDF contenant 'REG010' dans le nom"""
        pdf_files = []

        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(".pdf") and "REG010" in file:
                    pdf_files.append(os.path.join(root, file))

        self.log_info(f"Fichiers REG010 trouvés: {len(pdf_files)}")
        return pdf_files

    def find_ged001_pdfs(self, directory: str) -> List[str]:
        """Trouver tous les fichiers PDF contenant 'GED001' dans le nom"""
        pdf_files = []

        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(".pdf") and "GED001" in file:
                    pdf_files.append(os.path.join(root, file))

        self.log_info(f"Fichiers GED001 trouvés: {len(pdf_files)}")
        return pdf_files

    def cleanup_directory(self, directory: str):
        """Nettoyer un répertoire temporaire"""
        if directory and os.path.exists(directory):
            try:
                shutil.rmtree(directory, ignore_errors=True)
                self.log_info(f"Répertoire temporaire nettoyé: {directory}")
            except Exception as e:
                self.log_warning(f"Impossible de nettoyer le répertoire {directory}: {e}")
