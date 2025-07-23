import logging

import streamlit as st
from sqlmodel import Session, select

from models import Groupe, create_db_and_tables
from utils import logging_config  # noqa: F401
from utils.database import engine

logger = logging.getLogger(__name__)


def init_database():
    """Initialiser la base de données"""
    try:
        logger.info("🔧 Initialisation de la base de données...")
        create_db_and_tables()
        logger.info("✅ Base de données initialisée avec succès")

        # Vérifier la connexion
        with Session(engine) as session:
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
