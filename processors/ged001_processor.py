import os
import re
from typing import Dict, List

import fitz

from .base_processor import BaseProcessor


class Ged001Processor(BaseProcessor):
    """Processeur spécialisé pour l'extraction des factures des PDF GED001"""

    def __init__(self):
        super().__init__()

    def extraire_texte_brut_pdf(self, contenu_pdf: bytes) -> str:
        """
        Extraire le texte brut d'un PDF à partir de son contenu binaire
        """
        try:
            # Ouvrir le PDF depuis les bytes
            doc = fitz.open(stream=contenu_pdf, filetype="pdf")

            texte_complet = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                textpage = page.get_textpage()
                texte_page = textpage.extractText()
                texte_complet += f"\n--- Page {page_num + 1} ---\n{texte_page}"

            doc.close()
            return texte_complet.strip()

        except Exception as e:
            self.log_error(f"Erreur lors de l'extraction du texte brut: {e}")
            return ""

    def extraire_pages_facture(self, chemin_pdf: str, pages: List[int]) -> bytes:
        """
        Extraire certaines pages d'un PDF et retourner le contenu binaire
        """
        try:
            # Ouvrir le PDF source
            doc_source = fitz.open(chemin_pdf)

            # Créer un nouveau PDF avec seulement les pages voulues
            doc_nouveau = fitz.open()

            for num_page in pages:
                if num_page < len(doc_source):
                    doc_nouveau.insert_pdf(doc_source, from_page=num_page, to_page=num_page)

            # Récupérer le contenu binaire
            contenu_binaire = doc_nouveau.tobytes()

            doc_source.close()
            doc_nouveau.close()

            return contenu_binaire

        except Exception as e:
            self.log_error(f"Erreur lors de l'extraction des pages: {e}")
            return b""

    def analyser_et_extraire_factures_ged001(self, chemin_pdf: str) -> Dict[str, Dict]:
        """
        Analyser un PDF GED001 en un seul passage et extraire directement tous les PDFs de factures
        Retourne: {identifiant_facture: {'type': 'BONTRV01'|'FACFOU01', 'pdf_contenu': bytes, 'nb_pages': int}}
        """
        factures_extraites = {}

        try:
            # Ouvrir le PDF source
            doc_source = fitz.open(chemin_pdf)
            self.log_info(f"Analyse du PDF: {os.path.basename(chemin_pdf)} ({len(doc_source)} pages)")

            facture_courante = None
            type_facture = None
            pages_courantes = []

            def finaliser_facture():
                """Fonction interne pour finaliser une facture et extraire son PDF"""
                if facture_courante and pages_courantes:
                    # Créer un nouveau PDF pour cette facture
                    doc_facture = fitz.open()

                    # Ajouter toutes les pages de cette facture
                    for num_page in pages_courantes:
                        if num_page < len(doc_source):
                            doc_facture.insert_pdf(doc_source, from_page=num_page, to_page=num_page)

                    # Récupérer le contenu binaire
                    contenu_pdf = doc_facture.tobytes()
                    doc_facture.close()

                    # Stocker la facture
                    factures_extraites[facture_courante] = {
                        "type": type_facture,
                        "pdf_contenu": contenu_pdf,
                        "nb_pages": len(pages_courantes),
                    }

                    self.log_success(
                        f"Facture {facture_courante} ({type_facture}): {len(pages_courantes)} pages, PDF généré ({len(contenu_pdf)} octets)"
                    )

            # Parcourir toutes les pages UNE SEULE fois
            for num_page in range(len(doc_source)):
                page = doc_source[num_page]
                textpage = page.get_textpage()
                texte_page = textpage.extractText()

                # Chercher les patterns BONTRV01 ou FACFOU01
                nouvel_identifiant, nouveau_type = self._detect_facture_identifiant(texte_page)

                # Si on change de facture, finaliser la précédente
                if nouvel_identifiant and nouvel_identifiant != facture_courante:
                    # Finaliser la facture précédente
                    finaliser_facture()

                    # Commencer une nouvelle facture
                    facture_courante = nouvel_identifiant
                    type_facture = nouveau_type
                    pages_courantes = [num_page]

                else:
                    # Ajouter la page à la facture courante
                    if facture_courante:
                        pages_courantes.append(num_page)

            # Finaliser la dernière facture
            finaliser_facture()

            doc_source.close()
            self.log_success(f"Total des factures extraites: {len(factures_extraites)}")

        except Exception as e:
            self.log_error(f"Erreur lors de l'analyse du PDF {chemin_pdf}: {e}")

        return factures_extraites

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

    def process_ged001_files(self, ged_files: List[str]) -> Dict[str, Dict]:
        """Traiter une liste de fichiers GED001"""
        toutes_factures_ged001 = {}

        if ged_files:
            self.log_info("Analyse et extraction des fichiers GED001")
            for ged_file in ged_files:
                nom_fichier = os.path.basename(ged_file)
                self.log_info(f"🔍 Traitement de {nom_fichier}")

                factures_extraites = self.analyser_et_extraire_factures_ged001(ged_file)

                if factures_extraites:
                    self.log_info(f"  📊 {len(factures_extraites)} factures extraites:")
                    for id_facture, info in factures_extraites.items():
                        toutes_factures_ged001[id_facture] = info
                        self.log_info(f"    - {id_facture} ({info['type']}): {info['nb_pages']} pages")
                else:
                    self.log_warning(f"Aucune facture extraite de {nom_fichier}")

        return toutes_factures_ged001
