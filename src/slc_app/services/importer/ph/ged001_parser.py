import re
from typing import List

import fitz
import pandas as pd
from sqlmodel import Session

from slc_app.models.columns import GED001Columns
from slc_app.models.db import engine
from slc_app.models.facture import Facture
from slc_app.models.facture_pdf import FacturePDF
from slc_app.services.importer.ph.base_processor import BaseProcessor
from slc_app.utils.file_storage import save_file
from slc_app.utils.pdf_utils import extraire_pages_pdf, extraire_texte_brut_pdf


class ParserGED001(BaseProcessor):
    """Processeur spécialisé pour l'extraction des factures des PDF GED001"""

    def __init__(self):
        super().__init__()

    def _extract_data_from_pdf(self, ged_file: str) -> pd.DataFrame:
        """
        Extraire les données du PDF GED001 et retourner un DataFrame
        avec colonnes: identifiant, type, texte_brut, path_to_pdf_extrait
        """
        data = []

        try:
            # Ouvrir le PDF
            doc = fitz.open(ged_file)

            # Variables pour tracker la facture courante
            identifiant_courant = None
            type_courant = None
            pages_facture_courante = []

            # Parcourir toutes les pages
            for num_page in range(len(doc)):
                page = doc.load_page(num_page)
                texte_page = page.get_textpage().extractText()

                # Détecter si c'est une nouvelle facture
                identifiant, type_facture = self._detect_facture_identifiant(texte_page)

                if identifiant:  # Nouvelle facture détectée
                    # Si on avait une facture en cours, la sauvegarder
                    if identifiant_courant and pages_facture_courante:
                        # Extraire le contenu de la facture précédente
                        contenu_pdf = extraire_pages_pdf(ged_file, pages_facture_courante)
                        texte_brut = extraire_texte_brut_pdf(contenu_pdf)

                        data.append(
                            {
                                GED001Columns.IDENTIFIANT: identifiant_courant,
                                GED001Columns.TYPE: type_courant,
                                GED001Columns.TEXTE_BRUT: texte_brut,
                                GED001Columns.CONTENU_PDF: contenu_pdf,  # Pour la sauvegarde ultérieure
                            }
                        )

                    # Commencer une nouvelle facture
                    identifiant_courant = identifiant
                    type_courant = type_facture
                    pages_facture_courante = [num_page]

                elif identifiant_courant:
                    # Page suivante de la facture courante
                    pages_facture_courante.append(num_page)

            # Ne pas oublier la dernière facture
            if identifiant_courant and pages_facture_courante:
                contenu_pdf = extraire_pages_pdf(ged_file, pages_facture_courante)
                texte_brut = extraire_texte_brut_pdf(contenu_pdf)

                data.append(
                    {
                        GED001Columns.IDENTIFIANT: identifiant_courant,
                        GED001Columns.TYPE: type_courant,
                        GED001Columns.TEXTE_BRUT: texte_brut,
                        GED001Columns.CONTENU_PDF: contenu_pdf,
                    }
                )

            doc.close()

        except Exception as e:
            self.log_error(f"Erreur lors de l'extraction des données du PDF: {e}")
            raise

        return pd.DataFrame(data)

    def _save_pdf_for_row(self, row: pd.Series, savePath: str) -> str:
        """
        Sauvegarde le PDF pour une ligne donnée et retourne le chemin du fichier.

        Args:
            row (pd.Series): Ligne du DataFrame contenant les données.
            savePath (str): Chemin de sauvegarde pour le PDF.

        Returns:
            str: Chemin du fichier sauvegardé.
        """

        # Générer le nom de fichier
        filename = f"{row[GED001Columns.IDENTIFIANT]}_{row[GED001Columns.TYPE]}.pdf"

        # Sauvegarder le fichier et retourner le chemin
        return save_file(row[GED001Columns.CONTENU_PDF], savePath, filename)

    def _process_extracted_data(self, df: pd.DataFrame, savePath: str) -> pd.DataFrame:
        """
        Traiter le DataFrame extrait et retourner un DataFrame prêt pour la sauvegarde.
        """
        # Appliquer la méthode _save_pdf_for_row à chaque ligne du DataFrame
        df[GED001Columns.PATH_TO_PDF_EXTRAIT] = df.apply(
            lambda row: self._save_pdf_for_row(row, savePath), axis=1
        )

        # Supprimer la colonne de contenu binaire après sauvegarde
        df = df.drop(columns=[GED001Columns.CONTENU_PDF])

        return df

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

    def _save_to_db(self, df: pd.DataFrame, factures: List[Facture]) -> List[FacturePDF]:
        """
        Enregistrer les factures extraites dans la base de données
        """
        factures_pdf = FacturePDF.from_df(df)
        with Session(engine) as session:
            session.add_all(factures_pdf)
            session.commit()
            session.refresh(factures_pdf)

        return factures_pdf

    def process_ged001(
        self, ged_file: str, factures: List[Facture], pdfSavePath: str
    ) -> List[FacturePDF]:
        """Traiter une liste de fichiers GED001"""
        df_data = self._extract_data_from_pdf(ged_file)
        df_processed = self._process_extracted_data(df_data, pdfSavePath)
        factures_pdf = self._save_to_db(df_processed, factures)
        return factures_pdf
