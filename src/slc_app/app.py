import logging

import streamlit as st

from slc_app.utils import logging_config  # noqa: F401

logger = logging.getLogger(__name__)


def init_database():
    """Initialiser la base de données"""
    try:
        logger.info("🔧 Initialisation de la base de données...")

        # Importer les modèles pour enregistrer les tables
        from sqlmodel import Session, select

        import slc_app.models  # noqa: F401

        # Importer les fonctions de DB après les modèles
        from slc_app.models.db import create_db_and_tables, engine

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
    st.set_page_config(page_title="Contrôle des Charges", page_icon="📊", layout="wide")

    # Initialiser la base de données
    init_database()


if __name__ == "__main__":
    main()
