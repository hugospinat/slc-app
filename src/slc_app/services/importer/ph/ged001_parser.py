from slc_app.utils.logger import logger
from slc_app.utils.dataframe_mapper import create_objects_from_df
from slc_app.services.importer.ph.constants import GED001
import re
from typing import List, Tuple
import fitz
import pandas as pd
from slc_app.models import Facture, FacturePDF
from slc_app.utils.pdf_utils import extraire_pages_pdf, extraire_texte_brut_pdf


class ParserGED001:
    """Processeur spécialisé pour l'extraction des factures des PDF GED001"""

    def __init__(self):
        pass

    def _extract_data_from_pdf(self, ged_file: str) -> pd.DataFrame:
        """
        Extraire les données du PDF GED001 et retourner un DataFrame
        avec colonnes: identifiant, type, texte_brut, path_to_pdf_extrait
        """
        data = []

        try:
            # Ouvrir le PDF
            doc = fitz.open(ged_file)

            # Dictionnaire pour regrouper les pages par identifiant
            # Structure: {identifiant: {"pages": [num_page1, num_page2, ...], "type": "BONTRV01"}}
            factures_groupees = {}
            identifiant_courant = None

            # Première passe: identifier tous les identifiants et leurs pages
            for num_page in range(len(doc)):
                page = doc.load_page(num_page)
                texte_page = page.get_textpage().extractText()

                # Détecter si c'est une nouvelle facture
                identifiant, type_facture = self._detect_facture_identifiant(texte_page)

                if identifiant:  # Identifiant détecté sur cette page
                    logger.info(
                        f"[DEBUG] Page {num_page}: Identifiant détecté: {identifiant} - Type: {type_facture}"
                    )

                    # Créer ou mettre à jour l'entrée pour cet identifiant
                    if identifiant not in factures_groupees:
                        factures_groupees[identifiant] = {"pages": [], "type": type_facture}

                    factures_groupees[identifiant]["pages"].append(num_page)
                    identifiant_courant = identifiant

                elif identifiant_courant:
                    # Page sans identifiant, l'ajouter à la facture courante
                    factures_groupees[identifiant_courant]["pages"].append(num_page)
                    logger.info(
                        f"[DEBUG] Page {num_page} (sans identifiant) ajoutée à la facture {identifiant_courant}"
                    )

            # Deuxième passe: créer les PDFs groupés pour chaque facture
            for identifiant, infos in factures_groupees.items():
                pages_facture = infos["pages"]
                type_facture = infos["type"]

                logger.info(
                    f"[DEBUG] Création PDF pour facture {identifiant} avec {len(pages_facture)} pages: {pages_facture}"
                )

                # Extraire le contenu PDF pour toutes les pages de cette facture
                contenu_pdf = extraire_pages_pdf(ged_file, pages_facture)
                texte_brut = extraire_texte_brut_pdf(contenu_pdf)

                data.append(
                    {
                        GED001.IDENTIFIANT: identifiant,
                        GED001.TYPE: type_facture,
                        GED001.TEXTE_BRUT: texte_brut,
                        GED001.CHEMIN_FICHIER: contenu_pdf,
                    }
                )

            doc.close()

            logger.info(f"📊 Extraction terminée: {len(factures_groupees)} factures regroupées")

        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des données du PDF: {e}")
            raise

        return pd.DataFrame(data)

    def _detect_facture_identifiant(self, texte_page: str) -> tuple[str, str]:
        """
        Détecter l'identifiant et le type de facture dans le texte d'une page
        Retourne: (identifiant, type) ou (None, None) si rien trouvé
        """
        pattern_bontrv = r"(\d+\s*\)\s*BONTRV01\s+([A-Z0-9]+)/.*BONTRV01)"
        pattern_facfou = r"(\d+\s*\)\s*FACFOU01\s+([A-Z0-9]+)/.*FACFOU01)"

        match_bontrv = re.search(pattern_bontrv, texte_page)
        match_facfou = re.search(pattern_facfou, texte_page)

        if match_bontrv:
            return match_bontrv.group(2), "BONTRV01"
        elif match_facfou:
            return match_facfou.group(2), "FACFOU01"
        else:
            return "", ""

    def _associe_factures_a_pdf(
        self, factures_pdf: List[FacturePDF], factures: List[Facture]
    ) -> None:
        """
        Associe les factures à leurs PDF correspondants dans le DataFrame
        """
        logger.info(
            f"[DEBUG] Association de {len(factures)} factures avec {len(factures_pdf)} PDFs"
        )

        associations_reussies = 0

        for pdf in factures_pdf:
            for f in factures:
                if f and pdf.identifiant is not None and pdf.identifiant in f.libelle_ecriture:
                    f.facture_pdf = pdf
                    associations_reussies += 1
                    logger.info(
                        f"[DEBUG] ✅ Facture {f.numero_facture} associée au PDF {pdf.identifiant}"
                    )

        logger.info(f"📊 Associations réussies: {associations_reussies}/{len(factures)}")
        return

    def process_ged001(self, ged_file: str) -> List[Tuple[FacturePDF, bytes]]:
        """
        Traiter une liste de fichiers GED001
        et retourner les objets FacturePDFs avec leurs bytes
        """
        df_processed = self._extract_data_from_pdf(ged_file)
        bytes_data = df_processed[GED001.CHEMIN_FICHIER].tolist()
        factures_pdf = create_objects_from_df(
            FacturePDF, df_processed.drop(columns=[GED001.CHEMIN_FICHIER])
        )

        # Créer la liste de tuples (FacturePDF, bytes)
        result = [(factures_pdf[i], bytes_data[i]) for i in range(len(factures_pdf))]

        return result
