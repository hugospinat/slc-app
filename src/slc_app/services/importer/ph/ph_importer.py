from sqlmodel import Session

from slc_app.models.controle_charges import ControleCharges
from slc_app.models.db import engine
from slc_app.models.groupe import Groupe
from slc_app.services.importer.ph.base_processor import BaseProcessor
from slc_app.services.importer.ph.ged001_parser import ParserGED001
from slc_app.services.importer.ph.reg010_parser import ParserREG010
from slc_app.services.importer.ph.reg114_parser import ParserREG1114
from slc_app.services.importer.ph.zip_importer import ZipProcessor


class PHImporter(BaseProcessor):
    """Classe principale pour traiter les fichiers ZIP et extraire les données des PDF"""

    def __init__(self, annee: int, groupe: Groupe, path_to_zip: str) -> None:
        """Initialiser le processeur de fichiers"""
        super().__init__()
        # Initialiser les processeurs spécialisés
        self.zip_processor = ZipProcessor()
        self.reg010_parser = ParserREG010()
        self.reg114_parser = ParserREG1114()
        self.ged001_parser = ParserGED001()
        with Session(engine) as session:
            session.refresh(groupe)
            if groupe.id is None:
                raise ValueError(
                    "Groupe non valide sans ID, impossible de créer le contrôle des charges"
                )
            self.controle_charges = ControleCharges(annee=annee, groupe_id=groupe.id)
            session.add(self.controle_charges)
            session.commit()
            session.refresh(self.controle_charges)
            self.path_to_zip = path_to_zip
            self.process_zip_file()

    def process_zip_file(self) -> None:
        """Traiter un fichier ZIP et extraire les données des PDF REG010, REG114 et GED001"""
        try:
            self.log_info(f"Début du traitement du fichier ZIP: {self.path_to_zip}")

            # Extraire le ZIP
            self.zip_processor.extract_zip(self.path_to_zip)

            # Trouver les fichiers REG010, REG114 et GED001
            reg010 = self.zip_processor.find_unique_pattern_pdfs("REG010")
            reg114 = self.zip_processor.find_unique_pattern_pdfs("REG114")
            ged001 = self.zip_processor.find_unique_pattern_pdfs("GED001")

            # Traiter les fichiers REG010
            if reg010 is None or ged001 is None:
                self.log_error("Fichier REG010 ou GED001 manquant dans le ZIP")
                return
            if self.controle_charges.id is None:
                raise ValueError(
                    "L'identifiant du contrôle des charges est None, impossible de poursuivre l'import."
                )
            factures, postes = self.reg010_parser.process_reg010(reg010, self.controle_charges.id)
            self.log_info(f"📊 Factures extraites: {len(factures)}")
            self.log_info(f"📊 Postes extraits: {len(postes)}")

            # Traiter les fichiers GED001
            if ged001:
                pdfSavePath = f"{self.controle_charges.annee}/{self.controle_charges.groupe.identifiant}/factures"
                factures_pdf = self.ged001_parser.process_ged001(ged001, factures, pdfSavePath)
                self.log_info(f"📊 Pdfs facture extraits : {len(factures_pdf)}")

            # Traiter les fichiers REG114
            if reg114:
                tantiemes, bases_repartition = self.reg114_parser.process_reg114(
                    reg114, self.controle_charges.id
                )
                self.log_info(f"📊 Tantièmes extraits: {len(tantiemes)}")
                self.log_info(f"📊 Bases de répartition extraites: {len(bases_repartition)}")

        except Exception as e:
            self.log_error(f"Erreur lors du traitement du ZIP: {e}")
            raise Exception(f"Erreur lors du traitement du ZIP: {e}")

        finally:
            self.zip_processor.cleanup_directory()

        return
