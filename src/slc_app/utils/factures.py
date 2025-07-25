import logging
from datetime import datetime

from sqlmodel import Session

from models import Facture, engine
from utils import logging_config  # noqa: F401

logger = logging.getLogger(__name__)


def update_facture_statut(facture_id: int, nouveau_statut: str):
    """Mettre à jour le statut d'une facture automatiquement"""
    try:
        with Session(engine) as session:
            facture = session.get(Facture, facture_id)
            if facture:
                facture.statut = nouveau_statut
                facture.date_traitement = datetime.now()
                session.add(facture)
                session.commit()
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du statut: {e}")


def update_facture_commentaire(facture_id: int, nouveau_commentaire: str):
    """Mettre à jour le commentaire d'une facture automatiquement"""
    try:
        with Session(engine) as session:
            facture = session.get(Facture, facture_id)
            if facture:
                facture.commentaire_contestation = nouveau_commentaire if nouveau_commentaire else None
                facture.date_traitement = datetime.now()
                session.add(facture)
                session.commit()
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du commentaire: {e}")
