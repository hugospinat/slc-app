"""
Test pour vérifier le regroupement correct des pages GED001 ayant le même identifiant
"""

from unittest.mock import Mock, patch

from slc_app.models.columns import GED001Columns
from slc_app.services.importer.ph.ged001_parser import ParserGED001


def test_ged001_same_identifier_grouping():
    """Test que les pages avec le même identifiant sont correctement regroupées"""

    # Créer un parser
    parser = ParserGED001()

    # Simuler les données de pages avec le même identifiant
    mock_pages_data = [
        # Page 0: Première page de la facture ABC123
        ("1) BONTRV01 ABC123/2024 BONTRV01", "ABC123", "BONTRV01"),
        # Page 1: Deuxième page de la même facture ABC123 (même identifiant)
        ("1) BONTRV01 ABC123/2024 BONTRV01", "ABC123", "BONTRV01"),
        # Page 2: Page sans identifiant (fait partie de la facture ABC123)
        ("Suite de la facture...", "", ""),
        # Page 3: Nouvelle facture DEF456
        ("2) FACFOU01 DEF456/2024 FACFOU01", "DEF456", "FACFOU01"),
        # Page 4: Deuxième page de la facture DEF456
        ("2) FACFOU01 DEF456/2024 FACFOU01", "DEF456", "FACFOU01"),
    ]

    # Mock des fonctions d'extraction PDF
    def mock_detect_facture_identifiant(texte_page):
        for texte, identifiant, type_facture in mock_pages_data:
            if texte_page == texte:
                return identifiant, type_facture
        return "", ""

    # Mock fitz.open et les extractions PDF
    with patch("fitz.open") as mock_fitz_open, patch.object(
        parser, "_detect_facture_identifiant", side_effect=mock_detect_facture_identifiant
    ), patch(
        "slc_app.services.importer.ph.ged001_parser.extraire_pages_pdf"
    ) as mock_extraire_pages, patch(
        "slc_app.services.importer.ph.ged001_parser.extraire_texte_brut_pdf"
    ) as mock_extraire_texte:

        # Configuration du mock PDF
        mock_doc = Mock()
        mock_doc.__len__.return_value = 5  # 5 pages

        mock_pages = []
        for i, (texte, _, _) in enumerate(mock_pages_data):
            mock_page = Mock()
            mock_textpage = Mock()
            mock_textpage.extractText.return_value = texte
            mock_page.get_textpage.return_value = mock_textpage
            mock_pages.append(mock_page)

        mock_doc.load_page.side_effect = lambda i: mock_pages[i]
        mock_fitz_open.return_value = mock_doc

        # Configuration des mocks d'extraction
        mock_extraire_pages.return_value = b"fake_pdf_content"
        mock_extraire_texte.return_value = "fake_text_content"

        # Exécuter l'extraction
        result_df = parser._extract_data_from_pdf("fake_path.pdf")

        # Vérifications
        print(f"Nombre de factures extraites: {len(result_df)}")
        print("Données extraites:")
        for idx, row in result_df.iterrows():
            print(f"  Facture {idx}: {row[GED001Columns.IDENTIFIANT]} - {row[GED001Columns.TYPE]}")

        # On doit avoir exactement 2 factures (pas 4)
        assert len(result_df) == 2, f"Attendu 2 factures, obtenu {len(result_df)}"

        # Vérifier les identifiants
        identifiants = result_df[GED001Columns.IDENTIFIANT].tolist()
        assert "ABC123" in identifiants, "La facture ABC123 doit être présente"
        assert "DEF456" in identifiants, "La facture DEF456 doit être présente"

        # Vérifier qu'il n'y a pas de doublons
        assert len(set(identifiants)) == 2, "Il ne doit pas y avoir de doublons d'identifiants"

        # Vérifier les appels aux fonctions d'extraction
        # La facture ABC123 doit inclure les pages 0, 1, 2 (3 pages)
        # La facture DEF456 doit inclure les pages 3, 4 (2 pages)
        assert mock_extraire_pages.call_count == 2, "extraire_pages_pdf doit être appelé 2 fois"

        # Récupérer les arguments des appels pour vérifier les pages
        appels = mock_extraire_pages.call_args_list
        pages_extraites = [appel[0][1] for appel in appels]  # Deuxième argument = liste des pages

        # Vérifier que les bonnes pages sont regroupées
        pages_abc123 = None
        pages_def456 = None

        for pages in pages_extraites:
            if 0 in pages:  # Pages contenant la page 0 = facture ABC123
                pages_abc123 = pages
            elif 3 in pages:  # Pages contenant la page 3 = facture DEF456
                pages_def456 = pages

        assert pages_abc123 == [
            0,
            1,
            2,
        ], f"Les pages 0, 1, 2 doivent être regroupées pour ABC123, obtenu: {pages_abc123}"
        assert pages_def456 == [
            3,
            4,
        ], f"Les pages 3, 4 doivent être regroupées pour DEF456, obtenu: {pages_def456}"

        print("✅ Test de regroupement des pages réussi !")


if __name__ == "__main__":
    test_ged001_same_identifier_grouping()
