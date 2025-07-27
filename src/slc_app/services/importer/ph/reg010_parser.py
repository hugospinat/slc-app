from slc_app.services.importer.ph.common import TableauParser
from slc_app.services.importer.ph.constants import REG010, REG010_POSTE
from slc_app.utils.logger import logger
from slc_app.utils.dataframe_mapper import create_objects_from_df
import os
import re
from typing import List, Tuple

import pandas as pd

from slc_app.models import Facture, Poste


def process_reg010(pdf_path: str) -> Tuple[List[Facture], List[Poste]]:
    """Traiter un fichier REG010 et retourner les objets sans controle_id"""
    logger.info(f"🔄 Traitement de {os.path.basename(pdf_path)}")

    # Extraction des données
    parser = TableauParser.from_pdf(pdf_path, min_columns=7)

    # Définir les colonnes du REG010
    colonnes_reg010 = [
        REG010.POSTE_ID,
        REG010.NUMERO_FACTURE,
        REG010.CODE_JOURNAL,
        REG010.NUMERO_COMPTE_COMPTABLE,
        REG010.MONTANT_COMPTABLE,
        REG010.LIBELLE_ECRITURE,
        REG010.REFERENCES_PARTENAIRE_FACTURE,
    ]

    try:
        # Configuration et nettoyage des données REG010
        factures_parser = (
            parser.definir_colonnes(colonnes_reg010)
            .filtre_regex(REG010.MONTANT_COMPTABLE, r"^-?\d+\.\d{1,2}$")
            .max_nb_cols(8)
            .col_to_float(REG010.MONTANT_COMPTABLE)
            .forward_fill(REG010.POSTE_ID)
        )

        # Extraction et traitement des postes
        postes = (
            parser.copy_tableau(REG010.POSTE_ID)
            .apply_regex(
                REG010.POSTE_ID,
                r"^([A-Z][A-Z0-9]*)  - (.*)$",
                [REG010_POSTE.NOM, REG010_POSTE.CODE],
                drop_source=True,
            )
            .supprimer_doublons([REG010_POSTE.NOM])
            .dropna()
            .to_objects(Poste)
        )

        # Créer les objets factures groupés par nom de poste (génial !)
        factures_par_poste = factures_parser.to_objects_with_field(Facture, REG010.POSTE_ID)

        # Créer un mapping nom -> objet Poste pour les relations
        poste_map = {poste.nom: poste for poste in postes}

        # Mapper les relations directement avec la fonction générique
        factures = TableauParser.map_relations_static(factures_par_poste, poste_map, "poste")

        logger.info(f"✅ {len(postes)} postes et {len(factures)} factures créés")
        return factures, postes

    except Exception as e:
        logger.error(f"Erreur lors du traitement des données: {str(e)}")
        import traceback

        traceback.print_exc()
        raise e
