from slc_app.utils.logger import logger
from slc_app.utils.logger import logger
from sqlmodel import Session
from typing import List, Tuple, Optional, Any

from slc_app.models import ControleCharges, Groupe, engine
from slc_app.services.importer.ph.eau008c_parser import process_eau008c
from slc_app.services.importer.ph.ged001_parser import ParserGED001
from slc_app.services.importer.ph.reg010_parser import process_reg010
from slc_app.services.importer.ph.reg114_parser import process_reg114
from slc_app.services.importer.ph.zip_importer import ZipProcessor
from slc_app.utils.file_storage import save_file_from_path


def assign_controle_id(objects: List[Any], controle_id: int) -> None:
    """Assigne le controle_id à tous les objets qui en ont besoin"""
    for obj in objects:
        if hasattr(obj, "controle_id"):
            obj.controle_id = controle_id


def process_pdf_type(
    pdf_path: Optional[str],
    processor_func,
    obj_to_save: List[Any],
    controle_id: int,
    type_name: str,
) -> Optional[Tuple[List[Any], List[Any]]]:
    """Pattern générique pour traiter un type de PDF"""
    if pdf_path:
        result = processor_func(pdf_path)
        objects_1, objects_2 = result

        # Ajouter à la liste de sauvegarde
        obj_to_save.extend(objects_1 + objects_2)

        # Assigner le controle_id
        assign_controle_id(objects_1 + objects_2, controle_id)

        logger.info(f"📊 {type_name} - Type 1 extraits: {len(objects_1)}")
        logger.info(f"📊 {type_name} - Type 2 extraits: {len(objects_2)}")

        return objects_1, objects_2
    return None, None


def save_all_pdfs(pdf_files: dict, base_path: str) -> None:
    """Sauvegarde tous les PDFs dans leurs répertoires"""
    pdf_paths = {
        "reg010": f"{base_path}/reg010.pdf",
        "reg114": f"{base_path}/reg114.pdf",
        "ged001": f"{base_path}/ged001.pdf",
        "eau008c": f"{base_path}/eau008c.pdf",
    }

    for key, path in pdf_paths.items():
        if key in pdf_files and pdf_files[key]:
            save_file_from_path(pdf_files[key], path)


def create_controle_charges(annee: int, groupe_id: int) -> Tuple[ControleCharges, str]:
    """Crée le contrôle des charges avec gestion d'erreur et retourne aussi l'identifiant du groupe"""
    with Session(engine) as session:
        groupe = session.get(Groupe, groupe_id)
        if not groupe:
            raise ValueError(f"Groupe avec l'ID {groupe_id} introuvable")

        if groupe.id is None:
            raise ValueError(
                "Groupe non valide sans ID, impossible de créer le contrôle des charges"
            )

        # Créer le contrôle des charges
        controle_charges = ControleCharges(annee=annee, groupe_id=groupe.id)
        session.add(controle_charges)
        session.commit()
        session.refresh(controle_charges)

        # Récupérer l'identifiant du groupe avant de fermer la session
        groupe_identifiant = groupe.identifiant

        return controle_charges, groupe_identifiant


def importer_ph(annee: int, groupe_id: int, path_to_zip: str) -> None:
    """Fonction principale pour traiter les fichiers ZIP et extraire les données des PDF"""

    # Initialiser les processeurs
    zip_processor = ZipProcessor()
    ged001_parser = ParserGED001()

    # Créer le contrôle des charges
    try:
        controle_charges, groupe_identifiant = create_controle_charges(annee, groupe_id)
    except Exception as e:
        logger.error(f"Erreur lors de la création du contrôle des charges: {e}")
        raise e

    logger.info(f"Début du traitement du fichier ZIP: {path_to_zip}")

    try:
        # Extraire le ZIP et trouver les fichiers
        zip_processor.extract_zip(path_to_zip)
        pdf_files = {
            "reg010": zip_processor.find_unique_pattern_pdfs("REG010"),
            "reg114": zip_processor.find_unique_pattern_pdfs("REG114"),
            "ged001": zip_processor.find_unique_pattern_pdfs("GED001"),
            "eau008c": zip_processor.find_unique_pattern_pdfs("EAU008C"),
        }

        # Vérifications obligatoires
        if pdf_files["reg010"] is None or pdf_files["ged001"] is None:
            logger.error("Fichier REG010 ou GED001 manquant dans le ZIP")
            return

        if controle_charges.id is None:
            raise ValueError(
                "L'identifiant du contrôle des charges est None, impossible de poursuivre l'import."
            )

        # Chemin de sauvegarde
        cdc_path = f"{controle_charges.annee}/{groupe_identifiant}"

        # Liste centralisée pour tous les objets à sauvegarder
        obj_to_save = []

        # Traiter REG010 (obligatoire)
        factures, postes = process_pdf_type(
            pdf_files["reg010"],
            process_reg010,
            obj_to_save,
            controle_charges.id,
            "REG010 (Factures/Postes)",
        )

        # Traiter REG114 (optionnel)
        tantiemes, bases_repartition = process_pdf_type(
            pdf_files["reg114"],
            process_reg114,
            obj_to_save,
            controle_charges.id,
            "REG114 (Tantièmes/Bases)",
        )

        # Traiter EAU008C (optionnel)
        releves, postes_releve = process_pdf_type(
            pdf_files["eau008c"],
            process_eau008c,
            obj_to_save,
            controle_charges.id,
            "EAU008C (Relevés/Postes)",
        )

        # SAUVEGARDE CENTRALISÉE
        try:
            with Session(engine) as session:
                # Sauvegarder tous les objets d'un coup
                session.add_all(obj_to_save)

                # Traiter GED001 (garde sa logique actuelle)
                if pdf_files["ged001"]:
                    factures_path = f"{cdc_path}/factures"
                    factures_pdf = ged001_parser.process_ged001(
                        pdf_files["ged001"], factures, factures_path, session
                    )
                    logger.info(f"📊 PDFs facture extraits: {len(factures_pdf)}")

                session.commit()
                logger.info("✅ Toutes les données sauvegardées avec succès")

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            raise e

        # Sauvegarder les PDFs
        save_all_pdfs(pdf_files, cdc_path)

    except Exception as e:
        logger.error(f"Erreur lors du traitement du ZIP: {e}")
        raise e
    finally:
        zip_processor.cleanup_directory()

    return
