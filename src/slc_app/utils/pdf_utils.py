from typing import List

import fitz


def extraire_texte_brut_pdf(contenu_pdf: bytes) -> str:
    """
    Extraire le texte brut d'un PDF à partir de son contenu binaire.
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
        raise Exception(f"Erreur lors de l'extraction du texte brut : {e}")


def extraire_pages_pdf(chemin_pdf: str, pages: List[int]) -> bytes:
    """
    Extraire certaines pages d'un PDF et retourner le contenu binaire.
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
        raise Exception(f"Erreur lors de l'extraction des pages : {e}")
