import logging

import streamlit as st
from sqlmodel import Session, select

from slc_app.utils.logger import logger


def run_test_import():
    """Lancer le test d'importation au démarrage"""
    try:
        import subprocess
        import sys
        from pathlib import Path

        # Chemin vers le script de test
        script_path = (
            Path(__file__).parent.parent.parent / "tests" / "test_import" / "test_import_ph.py"
        )

        if script_path.exists():
            logger.info("🧪 Lancement du test d'importation...")

            # Lancer le script de test
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                cwd=str(script_path.parent.parent.parent),
            )

            if result.returncode == 0:
                logger.info("✅ Test d'importation réussi")
                logger.info(f"📄 Output: {result.stdout}")
            else:
                logger.warning("⚠️ Test d'importation échoué")
                logger.warning(f"📄 Output: {result.stdout}")
                logger.warning(f"❌ Error: {result.stderr}")
        else:
            logger.warning(f"⚠️ Script de test non trouvé: {script_path}")

    except Exception as e:
        logger.error(f"❌ Erreur lors du lancement du test: {e}")


def init_database():
    """Initialiser la base de données"""
    try:
        logger.info("🔧 Initialisation de la base de données...")

        # Importer les modèles pour enregistrer les tables

        # Importer les fonctions de DB après les modèles
        from slc_app.models import create_db_and_tables, engine

        create_db_and_tables()
        logger.info("✅ Base de données initialisée avec succès")

        # Vérifier la connexion
        with Session(engine) as session:
            from slc_app.models import Groupe

            groupes_count = len(session.exec(select(Groupe)).all())
            logger.info(f"📊 Groupes existants: {groupes_count}")

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation de la base: {e}")
        import traceback

        traceback.print_exc()


def main():
    st.set_page_config(page_title="Contrôle des Charges", page_icon="📊", layout="wide")
    # Initialiser la base de données
    init_database()


if __name__ == "__main__":
    main()
