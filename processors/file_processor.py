from typing import Dict, List, Tuple

import pandas as pd

from .association_processor import AssociationProcessor
from .base_processor import BaseProcessor
from .ged001_processor import Ged001Processor
from .reg010_processor import Reg010Processor
from .reg114_processor import Reg114Processor
from .zip_processor import ZipProcessor


class FileProcessor(BaseProcessor):
    """Classe principale pour traiter les fichiers ZIP et extraire les données des PDF"""

    def __init__(self, upload_dir: str = "uploads"):
        """Initialiser le processeur de fichiers"""
        super().__init__()
        self.upload_dir = upload_dir  # Gardé pour compatibilité

        # Initialiser les processeurs spécialisés
        self.zip_processor = ZipProcessor()
        self.reg010_processor = Reg010Processor()
        self.reg114_processor = Reg114Processor()
        self.ged001_processor = Ged001Processor()
        self.association_processor = AssociationProcessor()

    def extract_zip(self, zip_path: str) -> str:
        """Extraire un fichier ZIP et retourner le répertoire d'extraction"""
        return self.zip_processor.extract_zip(zip_path)

    def find_reg010_pdfs(self, directory: str) -> List[str]:
        """Trouver tous les fichiers PDF contenant 'REG010' dans le nom"""
        return self.zip_processor.find_reg010_pdfs(directory)

    def find_ged001_pdfs(self, directory: str) -> List[str]:
        """Trouver tous les fichiers PDF contenant 'GED001' dans le nom"""
        return self.zip_processor.find_ged001_pdfs(directory)

    def find_reg114_pdfs(self, directory: str) -> List[str]:
        """Trouver tous les fichiers PDF contenant 'REG114' dans le nom"""
        return self.zip_processor.find_reg114_pdfs(directory)

    def extract_data_from_pdf(self, pdf_path: str) -> pd.DataFrame:
        """Extraire les données d'un PDF REG010 de manière robuste"""
        return self.reg010_processor.extract_data_from_pdf(pdf_path)

    def extract_reg114_data(self, pdf_path: str) -> pd.DataFrame:
        """Extraire les données d'un PDF REG114 (tantièmes)"""
        return self.reg114_processor.extract_data_from_pdf(pdf_path)

    def process_reg114_files(self, pdf_files: List[str]) -> tuple[List[pd.DataFrame], List[str]]:
        """Traiter une liste de fichiers REG114"""
        return self.reg114_processor.process_reg114_files(pdf_files)

    def save_reg114_csv(self, dataframes: List[pd.DataFrame], filename: str = "reg114.csv") -> str:
        """Sauvegarder les DataFrames REG114 fusionnés en CSV"""
        return self.reg114_processor.save_combined_to_csv(dataframes, filename)

    def save_reg114_to_database(self, dataframes: List[pd.DataFrame], controle_id: int) -> int:
        """Sauvegarder les données REG114 (bases de répartition et tantièmes) en base de données"""
        if not dataframes:
            self.log_warning("Aucun DataFrame REG114 à sauvegarder")
            return 0

        total_saved = 0
        for df in dataframes:
            saved_count = self.reg114_processor.save_to_database(df, controle_id)
            total_saved += saved_count

        if total_saved > 0:
            self.log_success(f"💾 {total_saved} éléments REG114 sauvegardés en base (contrôle {controle_id})")
        else:
            self.log_warning("⚠️ Aucun élément REG114 sauvegardé en base")

        return total_saved

    def extraire_pages_facture(self, chemin_pdf: str, pages: List[int]) -> bytes:
        """Extraire certaines pages d'un PDF et retourner le contenu binaire"""
        return self.ged001_processor.extraire_pages_facture(chemin_pdf, pages)

    def analyser_et_extraire_factures_ged001(self, chemin_pdf: str) -> Dict[str, Dict]:
        """Analyser un PDF GED001 et extraire directement tous les PDFs de factures"""
        return self.ged001_processor.analyser_et_extraire_factures_ged001(chemin_pdf)

    def associer_factures_ged001_reg010(
        self, dataframes: List[pd.DataFrame], factures_ged001: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """Associer les factures GED001 aux lignes de données REG010"""
        return self.association_processor.associer_factures_ged001_reg010(dataframes, factures_ged001)

    def process_zip_file(self, zip_path: str) -> Tuple[List[pd.DataFrame], List[str], Dict[str, Dict]]:
        """Traiter un fichier ZIP et extraire les données des PDF REG010, REG114 et GED001"""
        dataframes = []
        processed_files = []
        toutes_factures_ged001 = {}
        extract_dir = None

        try:
            self.log_info(f"Début du traitement du fichier ZIP: {zip_path}")

            # Extraire le ZIP
            extract_dir = self.zip_processor.extract_zip(zip_path)

            # Trouver les fichiers REG010, REG114 et GED001
            reg010_files = self.zip_processor.find_reg010_pdfs(extract_dir)
            reg114_files = self.zip_processor.find_reg114_pdfs(extract_dir)
            ged001_files = self.zip_processor.find_ged001_pdfs(extract_dir)

            self.log_info(f"📄 Fichiers REG010 trouvés: {len(reg010_files)}")
            self.log_info(f"� Fichiers REG114 trouvés: {len(reg114_files)}")
            self.log_info(f"�📎 Fichiers GED001 trouvés: {len(ged001_files)}")

            # Traiter les fichiers GED001
            toutes_factures_ged001 = self.ged001_processor.process_ged001_files(ged001_files)

            # Traiter les fichiers REG010
            if reg010_files:
                dataframes, processed_files = self.reg010_processor.process_reg010_files(reg010_files)

            # Traiter les fichiers REG114 et sauvegarder en CSV
            if reg114_files:
                reg114_dataframes, reg114_files_processed = self.reg114_processor.process_reg114_files(reg114_files)
                if reg114_dataframes:
                    csv_path = self.reg114_processor.save_combined_to_csv(reg114_dataframes, "reg114.csv")
                    if csv_path:
                        self.log_success(f"📁 CSV REG114 sauvegardé: {csv_path}")
                        self.log_info(f"📊 Fichiers REG114 traités: {', '.join(reg114_files_processed)}")

            self.log_success(
                f"Traitement terminé: {len(dataframes)} fichiers REG010, {len(reg114_files)} fichiers REG114, {len(toutes_factures_ged001)} factures GED001"
            )

        except Exception as e:
            self.log_error(f"Erreur lors du traitement du ZIP: {e}")
            raise

        finally:
            # Nettoyer le répertoire temporaire
            if extract_dir:
                self.zip_processor.cleanup_directory(extract_dir)

        return dataframes, processed_files, toutes_factures_ged001
