#!/usr/bin/env python3
"""
Test de validation de l'architecture refactorisée
"""

import sys
from pathlib import Path

# Ajouter le répertoire src au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def test_architecture_validation():
    """Test de validation de toute l'architecture refactorisée"""

    print("🔍 Validation de l'architecture refactorisée...")

    # Test 1: Imports des utilitaires
    try:
        from slc_app.services.importer.ph.ph_importer import (
            assign_controle_id,
            process_pdf_type,
            create_controle_charges,
            save_all_pdfs,
            importer_ph,
        )

        print("✅ Import des utilitaires réussi")
    except Exception as e:
        print(f"❌ Erreur import utilitaires: {e}")
        return False

    # Test 2: Imports des parsers
    try:
        from slc_app.services.importer.ph.reg010_parser import process_reg010
        from slc_app.services.importer.ph.reg114_parser import process_reg114
        from slc_app.services.importer.ph.eau008c_parser import process_eau008c
        from slc_app.services.importer.ph.ged001_parser import ParserGED001

        print("✅ Import des parsers réussi")
    except Exception as e:
        print(f"❌ Erreur import parsers: {e}")
        return False

    # Test 3: Imports des composants de base
    try:
        from slc_app.services.importer.ph.common import TableauParser
        from slc_app.services.importer.ph.constants import REG010, REG114, EAU008C
        from slc_app.utils.dataframe_mapper import create_objects_from_df

        print("✅ Import des composants de base réussi")
    except Exception as e:
        print(f"❌ Erreur import composants: {e}")
        return False

    # Test 4: Vérification de la structure des parsers (pure functions)
    try:
        # Les parsers doivent être des fonctions pures sans session
        import inspect

        reg010_sig = inspect.signature(process_reg010)
        reg114_sig = inspect.signature(process_reg114)
        eau008c_sig = inspect.signature(process_eau008c)

        # Vérifier qu'ils ne prennent qu'un seul paramètre (le path)
        assert len(reg010_sig.parameters) == 1, "process_reg010 doit prendre un seul paramètre"
        assert len(reg114_sig.parameters) == 1, "process_reg114 doit prendre un seul paramètre"
        assert len(eau008c_sig.parameters) == 1, "process_eau008c doit prendre un seul paramètre"

        print("✅ Structure des parsers validée (fonctions pures)")
    except Exception as e:
        print(f"❌ Erreur validation structure: {e}")
        return False

    # Test 5: Test des méthodes TableauParser
    try:
        import pandas as pd
        from slc_app.models.facture import Facture

        # Créer un DataFrame test
        test_df = pd.DataFrame(
            {
                "numero_local": ["F001", "F002"],
                "poste_code": ["P001", "P001"],
                "montant": [100.0, 200.0],
                "date_test": ["31/12/2024", "01/01/2025"],
            }
        )

        parser = TableauParser(test_df)

        # Test de to_date
        result = parser.to_date(["date_test"])
        assert "date_test" in result.df.columns, "Colonne date doit exister"

        # Test de to_objects_with_field (avec données factices)
        grouped = parser.to_objects_with_field(Facture, "poste_code")
        assert isinstance(grouped, dict), "Doit retourner un dictionnaire"
        assert "P001" in grouped, "Doit contenir la clé de groupage"

        print("✅ Méthodes TableauParser validées")
    except Exception as e:
        print(f"❌ Erreur validation TableauParser: {e}")
        return False

    print("🎉 Validation complète de l'architecture réussie!")
    return True


if __name__ == "__main__":
    success = test_architecture_validation()
    sys.exit(0 if success else 1)
