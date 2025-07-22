from sqlmodel import Session

from models import Poste, engine


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
        print(f"❌ Erreur lors de la mise à jour du rapport: {e}")
