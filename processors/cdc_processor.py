from sqlmodel import Session

from models import engine
from models.groupe import Groupe
from pages.dashboard_page import ControleCharges

from .association_processor import AssociationProcessor
from .base_processor import BaseProcessor
from .ged001_processor import Ged001Processor
from .reg010_processor import Reg010Processor
from .reg114_processor import Reg114Processor
from .zip_processor import ZipProcessor


class CDCProcessor(BaseProcessor):
    """Classe principale pour traiter les fichiers ZIP et extraire les données des PDF"""

    def __init__(self, annee: int, groupe: Groupe, upload_dir: str = "uploads") -> None:
        """Initialiser le processeur de fichiers"""
        super().__init__()
        # Initialiser les processeurs spécialisés
        self.zip_processor = ZipProcessor()
        self.reg010_processor = Reg010Processor()
        self.reg114_processor = Reg114Processor()
        self.ged001_processor = Ged001Processor()
        self.association_processor = AssociationProcessor()
        with Session(engine) as session:
            session.refresh(groupe)
            if groupe.id is None:
                raise ValueError("Groupe non valide sans ID, impossible de créer le contrôle des charges")
            self.controle_charges = session.add(ControleCharges(annee=annee, groupe_id=groupe.id))

    def process_zip_file(self, zip_path: str, annee: int, groupe: Groupe) -> None:
        """Traiter un fichier ZIP et extraire les données des PDF REG010, REG114 et GED001"""
        try:
            self.log_info(f"Début du traitement du fichier ZIP: {zip_path}")

            # Extraire le ZIP
            self.zip_processor.extract_zip(zip_path)

            # Trouver les fichiers REG010, REG114 et GED001
            reg010 = self.zip_processor.find_unique_pattern_pdfs("REG010")
            reg114 = self.zip_processor.find_unique_pattern_pdfs("REG114")
            ged001 = self.zip_processor.find_unique_pattern_pdfs("GED001")

            # Traiter les fichiers REG010
            if reg010 is None or ged001 is None:
                self.log_error("Fichier REG010 ou GED001 manquant dans le ZIP")
                return
            factures, postes = self.reg010_processor.process_reg010(reg010, controle_id)
            self.log_info(f"📊 Factures extraites: {len(factures)}")
            self.log_info(f"📊 Postes extraits: {len(postes)}")

            # Traiter les fichiers GED001
            if ged001:
                factures_pdf = self.ged001_processor.process_ged001(ged001, factures)
                self.log_info(f"📊 Pdfs facture extraits : {len(factures_pdf)}")

            # Traiter les fichiers REG114 et sauvegarder en CSV
            if reg114:
                tantiemes, bases_repartition = self.reg114_processor.process_reg114(reg114, controle_id)
                self.log_info(f"📊 Tantièmes extraits: {len(tantiemes)}")
                self.log_info(f"📊 Bases de répartition extraites: {len(bases_repartition)}")

        except Exception as e:
            self.log_error(f"Erreur lors du traitement du ZIP: {e}")
            raise Exception(f"Erreur lors du traitement du ZIP: {e}")

        finally:
            self.zip_processor.cleanup_directory()

        return
