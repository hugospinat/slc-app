from slc_app.services.importer.ph.common import TableauParser
from slc_app.services.importer.ph.constants import REG114, REG114_BASE
from slc_app.utils.logger import logger
from slc_app.utils.dataframe_mapper import create_objects_from_df
import os
from typing import List, Tuple

import pandas as pd

from slc_app.models import BaseRepartition, Tantieme


def process_reg114(pdf_path: str) -> Tuple[List[Tantieme], List[BaseRepartition]]:
    """Traiter un fichier REG114 et retourner les objets sans controle_id"""
    logger.info(f"🔄 Extraction du PDF: {os.path.basename(pdf_path)}")

    # Extraction des données avec tabula
    parser = TableauParser.from_pdf(pdf_path, min_columns=6)

    # Nommer les colonnes selon le modèle de données REG114
    colonnes_reg114 = [
        REG114.NUMERO_UG,  # Colonne 0: numéros UG
        REG114.NUMERO_CA,  # Colonne 1: numéro compte auxiliaire
        REG114.DEBUT_OCCUPATION,  # Colonne 2: date début occupation
        REG114.FIN_OCCUPATION,  # Colonne 3: date fin occupation
        REG114.TANTIEME,  # Colonne 4: montant tantième
        REG114.RELIQUAT,  # Colonne 5: montant reliquat
    ]

    try:
        # Pattern pour détecter les codes de base de répartition
        regex_code_et_nom = r"^([A-Z][A-Z0-9]+) - (.*)$"
        regex_code = r"^([A-Z][A-Z0-9]+) - .*$"

        parser.definir_colonnes(colonnes_reg114)

        # Extraire les bases de répartition
        bases = (
            parser.copy_tableau(REG114.NUMERO_UG)  # Prendre la première colonne
            .apply_regex(
                REG114.NUMERO_UG,
                regex_code_et_nom,
                [REG114_BASE.CODE, REG114_BASE.NOM],
                drop_source=True,
            )
            .dropna([REG114_BASE.CODE])
            .supprimer_doublons([REG114_BASE.CODE])
            .to_objects(BaseRepartition)
        )

        # Traitement principal avec composition
        tantiemes_parser = (
            parser.remove_empty_lines()
            .max_nb_cols(7)  # Supprimer les lignes avec 7 colonnes ou plus non vides
            .apply_regex(REG114.NUMERO_UG, regex_code, [REG114_BASE.CODE])
            .forward_fill(REG114_BASE.CODE)
            .filtre_regex(REG114.TANTIEME, r"^-?\d+\.\d{1,2}$")
            .to_date([REG114.DEBUT_OCCUPATION, REG114.FIN_OCCUPATION])  # Convertir les dates
        )

        if not bases:
            logger.warning("Aucune base de répartition trouvée dans le document")
            raise ValueError("❌ Aucune base de répartition trouvée")

        # Créer les objets tantièmes groupés par code de base (génial !)
        tantiemes_par_base = tantiemes_parser.to_objects_with_field(Tantieme, REG114_BASE.CODE)

        # Créer un mapping code -> objet BaseRepartition pour les relations
        base_map = {base.code: base for base in bases}

        # Mapper les relations directement avec la fonction générique
        tantiemes = TableauParser.map_relations_static(
            tantiemes_par_base, base_map, "base_repartition", clean_key=False
        )

        logger.info(f"✅ {len(tantiemes)} tantièmes et {len(bases)} bases de répartition créés")
        return tantiemes, bases

    except Exception as e:
        logger.error(f"Erreur lors du traitement des données: {str(e)}")
        import traceback

        traceback.print_exc()
        raise e
