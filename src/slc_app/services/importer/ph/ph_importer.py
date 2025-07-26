from sqlmodel import Session

from slc_app.models import ControleCharges, Groupe, engine
from slc_app.services.importer.ph.base_processor import BaseProcessor
from slc_app.services.importer.ph.eau008c_parser import ParserEAU008C
from slc_app.services.importer.ph.ged001_parser import ParserGED001
from slc_app.services.importer.ph.reg010_parser import ParserREG010
from slc_app.services.importer.ph.reg114_parser import ParserREG114
from slc_app.services.importer.ph.zip_importer import ZipProcessor
from slc_app.utils.file_storage import save_file_from_path


class PHImporter(BaseProcessor):
    """Classe principale pour traiter les fichiers ZIP et extraire les données des PDF"""

    def __init__(self, annee: int, groupe_id: int, path_to_zip: str) -> None:
        """Initialiser le processeur de fichiers"""
        super().__init__()
        # Initialiser les processeurs spécialisés
        self.zip_processor = ZipProcessor()
        self.reg010_parser = ParserREG010()
        self.reg114_parser = ParserREG114()
        self.ged001_parser = ParserGED001()
        self.eau008c_parser = ParserEAU008C()

        self.annee = annee
        self.groupe_id = groupe_id
        self.path_to_zip = path_to_zip

        # ARCHITECTURE CENTRALISÉE: Une seule session pour tout l'import
        with Session(engine) as session:
            # Récupérer le groupe par son ID
            groupe = session.get(Groupe, groupe_id)
            if not groupe:
                raise ValueError(f"Groupe avec l'ID {groupe_id} introuvable")

            self.groupe = groupe

            if groupe.id is None:
                raise ValueError(
                    "Groupe non valide sans ID, impossible de créer le contrôle des charges"
                )

            # Créer le contrôle des charges
            self.controle_charges = ControleCharges(annee=annee, groupe_id=groupe.id)
            session.add(self.controle_charges)
            session.commit()
            session.refresh(self.controle_charges)

            # Traiter le ZIP avec la session active
            self.process_zip_file(session)

    def process_zip_file(self, session: Session) -> None:
        """Traiter un fichier ZIP et extraire les données des PDF REG010, REG114 et GED001"""
        try:
            self.log_info(f"Début du traitement du fichier ZIP: {self.path_to_zip}")

            # Extraire le ZIP (pas besoin de session)
            self.zip_processor.extract_zip(self.path_to_zip)

            # Trouver les fichiers REG010, REG114, GED001 et EAU008C (pas besoin de session)
            reg010 = self.zip_processor.find_unique_pattern_pdfs("REG010")
            reg114 = self.zip_processor.find_unique_pattern_pdfs("REG114")
            ged001 = self.zip_processor.find_unique_pattern_pdfs("GED001")
            eau008c = self.zip_processor.find_unique_pattern_pdfs("EAU008C")

            # Traiter les fichiers REG010
            cdc_path = f"{self.controle_charges.annee}/{self.controle_charges.groupe.identifiant}"

            if reg010 is None or ged001 is None:
                self.log_error("Fichier REG010 ou GED001 manquant dans le ZIP")
                return
            if self.controle_charges.id is None:
                raise ValueError(
                    "L'identifiant du contrôle des charges est None, impossible de poursuivre l'import."
                )
            save_file_from_path(reg010, cdc_path, "reg010.pdf")

            # ARCHITECTURE CENTRALISÉE: Passer la session à tous les parsers
            factures, postes = self.reg010_parser.process_reg010(
                reg010, self.controle_charges.id, session
            )
            self.log_info(f"📊 Factures extraites: {len(factures)}")
            self.log_info(f"📊 Postes extraits: {len(postes)}")

            # Traiter les fichiers GED001 avec la même session
            if ged001:
                factures_path = f"{cdc_path}/factures"
                factures_pdf = self.ged001_parser.process_ged001(
                    ged001, factures, factures_path, session
                )
                self.log_info(f"📊 Pdfs facture extraits : {len(factures_pdf)}")

            # Traiter les fichiers REG114 avec la même session
            if reg114:
                tantiemes, bases_repartition = self.reg114_parser.process_reg114(
                    reg114, self.controle_charges.id, cdc_path, session
                )
                self.log_info(f"📊 Tantièmes extraits: {len(tantiemes)}")
                self.log_info(f"📊 Bases de répartition extraites: {len(bases_repartition)}")

            # Traiter les fichiers EAU008C avec la même session
            if eau008c:
                releves, postes_releve = self.eau008c_parser.process_eau008c(
                    eau008c, self.controle_charges.id, cdc_path, session
                )
                self.log_info(f"📊 Relevés individuels extraits: {len(releves)}")
                self.log_info(f"📊 Postes de relevé extraits: {len(postes_releve)}")

        except Exception as e:
            self.log_error(f"Erreur lors du traitement du ZIP: {e}")
            raise Exception(f"Erreur lors du traitement du ZIP: {e}")

        finally:
            self.zip_processor.cleanup_directory()

        return
