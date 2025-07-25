#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour importer un fichier ZIP avec PHImporter
Usage: python tests/test_import/test_import_ph.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Ajouter le répertoire src au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

if os.path.exists("database.db"):
    os.remove("database.db")


def test_import_ph():
    """Test d'importation d'un fichier ZIP avec PHImporter"""

    print("[START] Début du test d'importation...")

    try:
        # Imports locaux pour éviter les erreurs de linting
        print("[IMPORT] Importation des modules...")
        from sqlmodel import Session

        from slc_app.models import ControleCharges, FacturePDF, Groupe, engine
        from slc_app.services.importer.ph.ph_importer import PHImporter

        print("[OK] Modules importés avec succès")

        # Chemin vers le fichier de test
        zip_file = Path(__file__).parent.parent / "data" / "113RU.zip"

        if not zip_file.exists():
            print(f"[ERROR] Fichier de test non trouvé: {zip_file}")
            return False

        print(f"[TEST] Test d'importation de: {zip_file}")

        # Obtenir des paramètres de test uniques
        annee, groupe_id = 9999, 9999
        from slc_app.models.db import create_db_and_tables

        create_db_and_tables()
        # Créer un répertoire temporaire pour l'extraction
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Copier le fichier ZIP dans le répertoire temporaire
            tmp_zip = Path(tmp_dir) / "113RU.zip"
            shutil.copy2(zip_file, tmp_zip)

            print(f"[FILE] Fichier copié vers: {tmp_zip}")

            # Paramètres de test
            print(f"[TEST] Paramètres de test - Année: {annee}, Groupe ID: {groupe_id}")

            # Créer le groupe de test
            with Session(engine) as session:
                groupe = Groupe(
                    id=groupe_id, nom=f"Groupe Test {annee}", identifiant=f"TEST{annee}"
                )
                session.add(groupe)
                session.commit()
                print(f"[OK] Groupe créé: {groupe.nom}")

            # Lancer l'importation
            print("[IMPORT] Lancement de l'importation...")
            print(f"   - Année: {annee}")
            print(f"   - Groupe ID: {groupe_id}")
            print(f"   - Fichier: {tmp_zip}")

            PHImporter(annee, groupe_id, str(tmp_zip))

            print("[OK] Importation terminée avec succès!")

            # Vérifier les résultats
            with Session(engine) as session:
                from sqlmodel import select

                controle = session.exec(
                    select(ControleCharges)
                    .where(ControleCharges.annee == annee)
                    .where(ControleCharges.groupe_id == groupe_id)
                ).first()

                if controle:
                    print(f"[OK] Contrôle créé: ID {controle.id}")
                    print(f"   - Année: {controle.annee}")
                    print(f"   - Groupe: {controle.groupe_id}")

                    # Compter les éléments importés
                    from slc_app.models import BaseRepartition, Facture, Poste, Tantieme

                    nb_factures = len(session.exec(select(Facture)).all())
                    nb_postes = len(session.exec(select(Poste)).all())
                    nb_bases = len(session.exec(select(BaseRepartition)).all())
                    nb_tantiemes = len(session.exec(select(Tantieme)).all())
                    nb_factures_pdf = len(session.exec(select(FacturePDF)).all())

                    print("[DATA] Données importées:")
                    print(f"   - Factures: {nb_factures}")
                    print(f"   - Postes: {nb_postes}")
                    print(f"   - Factures PDF: {nb_factures_pdf}")
                    print(f"   - Bases de répartition: {nb_bases}")
                    print(f"   - Tantièmes: {nb_tantiemes}")

                else:
                    print("[WARNING] Aucun contrôle trouvé")
                    return False

            return True

    except Exception as e:
        print(f"[ERROR] Erreur lors de l'importation: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("[TEST] Test d'importation PHImporter")
    print("=" * 50)

    success = test_import_ph()

    if success:
        print("\n[SUCCESS] Test réussi!")
        sys.exit(0)
    else:
        print("\n[FAILED] Test échoué!")
        sys.exit(1)
