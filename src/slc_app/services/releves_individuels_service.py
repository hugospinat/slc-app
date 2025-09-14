from typing import List, Optional

from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from slc_app.models import (
    ControleCharges,
    PosteReleve,
    ReleveIndividuel,
    Groupe,
)
from slc_app.models import engine


def get_all_controles_charges() -> List[ControleCharges]:
    """Récupère tous les contrôles de charges disponibles"""
    with Session(engine) as session:
        statement = (
            select(ControleCharges)
            .options(selectinload(ControleCharges.groupe))
            .order_by(ControleCharges.annee.desc(), ControleCharges.groupe_id)
        )
        return list(session.exec(statement).all())


def get_postes_releve_by_controle(controle_charges_id: int) -> List[PosteReleve]:
    """Récupère tous les postes relevé pour un contrôle de charges donné"""
    with Session(engine) as session:
        statement = (
            select(PosteReleve)
            .where(PosteReleve.controle_id == controle_charges_id)
            .order_by(PosteReleve.nom)
        )
        return list(session.exec(statement).all())


def get_releves_individuels(
    controle_charges_id: Optional[int] = None, poste_releve_id: Optional[int] = None
) -> List[ReleveIndividuel]:
    """
    Récupère les relevés individuels filtrés par contrôle de charges et/ou poste relevé
    """
    with Session(engine) as session:
        statement = (
            select(ReleveIndividuel)
            .join(PosteReleve)
            .options(selectinload(ReleveIndividuel.poste_releve))
        )

        if controle_charges_id:
            statement = statement.where(PosteReleve.controle_id == controle_charges_id)

        if poste_releve_id:
            statement = statement.where(ReleveIndividuel.poste_releve_id == poste_releve_id)

        statement = statement.order_by(ReleveIndividuel.numero_ug, ReleveIndividuel.date_releve)

        return list(session.exec(statement).all())


def get_stats_releves(releves: List[ReleveIndividuel]) -> dict:
    """Calcule des statistiques sur les relevés"""
    if not releves:
        return {
            "total": 0,
            "avec_evolution": 0,
            "sans_evolution": 0,
            "evolution_moyenne": 0,
            "evolution_min": None,
            "evolution_max": None,
            "consommation_totale": 0,
        }

    avec_evolution = [r for r in releves if r.evolution_index is not None]
    evolutions = [r.evolution_index for r in avec_evolution if r.evolution_index is not None]

    return {
        "total": len(releves),
        "avec_evolution": len(avec_evolution),
        "sans_evolution": len(releves) - len(avec_evolution),
        "evolution_moyenne": sum(evolutions) / len(evolutions) if evolutions else 0,
        "evolution_min": min(evolutions) if evolutions else None,
        "evolution_max": max(evolutions) if evolutions else None,
        "consommation_totale": sum(evolutions) if evolutions else 0,
    }
