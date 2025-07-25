import logging

from sqlmodel import Session

from src.slc_app.models import Poste, engine
from src.slc_app.utils import logging_config  # noqa: F401

logger = logging.getLogger(__name__)


def update_rapport_poste(poste_id: int, nouveau_rapport: str):
    """Mettre à jour le rapport d'un poste"""
    try:
        with Session(engine) as session:
            poste = session.get(Poste, poste_id)
            if poste:
                poste.rapport = nouveau_rapport
                session.add(poste)
                session.commit()
    except Exception as e:
        logger.error(f"❌ Erreur lors de la mise à jour du rapport: {e}")
