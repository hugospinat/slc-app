import re
from typing import List

import fitz
import pandas as pd
from sqlmodel import Session

from slc_app.models import Facture, FacturePDF, GED001Columns
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
                    self.log_info(
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
                    self.log_info(
                        f"[DEBUG] Page {num_page} (sans identifiant) ajoutée à la facture {identifiant_courant}"
                    )

            # Deuxième passe: créer les PDFs groupés pour chaque facture
            for identifiant, infos in factures_groupees.items():
                pages_facture = infos["pages"]
                type_facture = infos["type"]

                self.log_info(
                    f"[DEBUG] Création PDF pour facture {identifiant} avec {len(pages_facture)} pages: {pages_facture}"
                )

                # Extraire le contenu PDF pour toutes les pages de cette facture
                contenu_pdf = extraire_pages_pdf(ged_file, pages_facture)
                texte_brut = extraire_texte_brut_pdf(contenu_pdf)

                data.append(
                    {
                        GED001Columns.IDENTIFIANT: identifiant,
                        GED001Columns.TYPE: type_facture,
                        GED001Columns.TEXTE_BRUT: texte_brut,
                        GED001Columns.CONTENU_PDF: contenu_pdf,
                    }
                )

            doc.close()

            self.log_info(f"📊 Extraction terminée: {len(factures_groupees)} factures regroupées")

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

    def _associe_factures_a_pdf(
        self, factures_pdf: List[FacturePDF], factures: List[Facture], session: Session
    ) -> None:
        """
        Associe les factures à leurs PDF correspondants dans le DataFrame
        SOLUTION ARCHITECTURALE: Recharger proprement les objets depuis la DB
        """
        self.log_info(
            f"[DEBUG] Association de {len(factures)} factures avec {len(factures_pdf)} PDFs"
        )

        associations_reussies = 0

        for pdf in factures_pdf:
            for f in factures:
                # SOLUTION PROPRE: Recharger la facture depuis la DB dans la session courante
                # Ceci garantit que l'objet est attaché à la session active
                facture_attachee = session.get(Facture, f.id)

                if (
                    facture_attachee
                    and pdf.identifiant is not None
                    and pdf.identifiant in facture_attachee.libelle_ecriture
                ):
                    facture_attachee.facture_pdf = pdf
                    associations_reussies += 1
                    self.log_info(
                        f"[DEBUG] ✅ Facture {facture_attachee.numero_facture} associée au PDF {pdf.identifiant}"
                    )

        session.commit()
        self.log_info(f"📊 Associations réussies: {associations_reussies}/{len(factures)}")
        return

    def _save_to_db(
        self, df: pd.DataFrame, factures: List[Facture], session: Session
    ) -> List[FacturePDF]:
        """
        Enregistrer les factures extraites dans la base de données
        ARCHITECTURE AMÉLIORÉE: Session passée en paramètre
        """
        factures_pdf = FacturePDF.from_df(df)
        session.add_all(factures_pdf)
        session.commit()

        # Rafraîchir les PDFs pour avoir leurs IDs
        for f in factures_pdf:
            session.refresh(f)

        # Association avec la même session
        self._associe_factures_a_pdf(factures_pdf, factures, session)
        return factures_pdf

    def process_ged001(
        self, ged_file: str, factures: List[Facture], pdfSavePath: str, session: Session
    ) -> List[FacturePDF]:
        """
        Traiter une liste de fichiers GED001
        ARCHITECTURE AMÉLIORÉE: Session gérée par l'appelant
        """
        df_data = self._extract_data_from_pdf(ged_file)
        df_processed = self._process_extracted_data(df_data, pdfSavePath)
        factures_pdf = self._save_to_db(df_processed, factures, session)
        return factures_pdf
