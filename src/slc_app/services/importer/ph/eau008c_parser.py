from slc_app.services.importer.ph.common import TableauParser
from slc_app.services.importer.ph.constants import EAU008C, EAU008C_POSTE
from slc_app.utils.logger import logger
from slc_app.utils.dataframe_mapper import create_objects_from_df
import os
from typing import List, Tuple

import pandas as pd

from slc_app.models import PosteReleve, ReleveIndividuel


def process_eau008c(pdf_path: str) -> Tuple[List[ReleveIndividuel], List[PosteReleve]]:
    """Traiter un fichier EAU008C et retourner les objets sans relations controle_id"""
    logger.info(f"🔄 Traitement de {os.path.basename(pdf_path)}")

    # Extraction des données
    parser = TableauParser.from_pdf(pdf_path, min_columns=11)

    # Nommer les colonnes selon le modèle de données EAU008C
    colonnes_eau008c = [
        EAU008C.NUMERO_UG,  # Colonne 1: N°UG
        EAU008C.NATURE_UG,  # Colonne 2: Nature UG
        EAU008C.NUMERO_CA,  # Colonne 3: N°CA
        EAU008C.POINT_COMPTAGE,  # Colonne 4: Point de Comptage
        EAU008C.NUMERO_SERIE_COMPTEUR,  # Colonne 5: N° Série compteur
        EAU008C.DATE_RELEVE,  # Colonne 6: Date du Relevé
        EAU008C.DATE_VALEUR,  # Colonne 7: Date de valeur
        EAU008C.TYPE_RELEVE,  # Colonne 8: Type de Relevé
        EAU008C.OBSERVATIONS,  # Colonne 9: Observations
        EAU008C.INDEX_RELEVE,  # Colonne 10: Index
        EAU008C.EVOLUTION_INDEX,  # Colonne 11: Evolution Index
    ]

    try:
        # Pattern pour détecter les postes de relevé
        pattern_poste = r"^([A-Z][A-Z\s]+)$"
        parser.definir_colonnes(colonnes_eau008c)

        # Extraire les postes de relevé
        postes = (
            parser.copy_tableau(EAU008C.NUMERO_UG)  # Prendre la première colonne
            .apply_regex(EAU008C.NUMERO_UG, pattern_poste, [EAU008C_POSTE.NOM], drop_source=True)
            .supprimer_doublons([EAU008C_POSTE.NOM])
            .dropna()
            .to_objects(PosteReleve)
        )

        # Traitement principal avec composition - on garde le nom du poste dans les objets
        releves_parser = (
            parser.remove_empty_lines()
            .max_nb_cols(12)  # Supprimer les lignes avec 12 colonnes ou plus non vides
            .apply_regex(EAU008C.NUMERO_UG, pattern_poste, [EAU008C_POSTE.NOM], drop_source=False)
            .forward_fill(EAU008C_POSTE.NOM)
            .filtre_regex(EAU008C.NUMERO_UG, r"^\d+$")
            .filtre_regex(EAU008C.NUMERO_CA, r"^\d+$")
            .filtre_regex(EAU008C.INDEX_RELEVE, r"^-?\d+$")
            .to_date([EAU008C.DATE_RELEVE, EAU008C.DATE_VALEUR])  # Convertir les dates
        )

        # Créer les objets groupés par nom de poste (génial !)
        releves_par_poste = releves_parser.to_objects_with_field(
            ReleveIndividuel, EAU008C_POSTE.NOM
        )

        # Créer un mapping nom -> objet PosteReleve pour les relations
        poste_map = {poste.nom: poste for poste in postes}

        # Mapper les relations directement avec la fonction générique
        releves = TableauParser.map_relations_static(releves_par_poste, poste_map, "poste_releve")

        logger.info(
            f"✅ {len(postes)} postes de relevé et {len(releves)} relevés individuels créés"
        )
        return releves, postes

    except Exception as e:
        logger.error(f"Erreur lors du traitement des données: {str(e)}")
        import traceback

        traceback.print_exc()
        raise e
