import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from sqlmodel import Session, select

from slc_app.models import Facture, FactureElectricite, RegleExtractionChamp, engine
from slc_app.utils import logging_config  # noqa: F401

# Utilise le logger global configuré ailleurs
logger = logging.getLogger(__name__)


def extraire_champs_automatiques(facture_id: int) -> Dict[str, Any]:
    """
    Extrait automatiquement les champs d'une facture en utilisant les règles définies
    Retourne un dictionnaire avec les valeurs extraites par table
    """
    with Session(engine) as session:
        logger.debug(f"Début extraction automatique pour facture_id={facture_id}")
        facture = session.get(Facture, facture_id)
        if not facture:
            logger.error(f"Facture id={facture_id} introuvable.")
            return {}
        if not facture.fournisseur_id:
            logger.error(f"Facture id={facture_id} sans fournisseur_id.")
            return {}
        if not facture.texte_brut_pdf:
            logger.error(f"Facture id={facture_id} sans texte_brut_pdf.")
            return {}

        # Récupérer les règles actives pour ce fournisseur
        from sqlmodel import and_

        regles = session.exec(
            select(RegleExtractionChamp).where(
                and_(
                    RegleExtractionChamp.fournisseur_id == facture.fournisseur_id,
                    RegleExtractionChamp.actif == True,  # Correction ici
                )
            )
        ).all()

        logger.debug(
            f"{len(regles)} règle(s) active(s) trouvée(s) pour fournisseur_id={facture.fournisseur_id}"
        )

        resultats = {}

        for regle in regles:
            try:
                logger.debug(
                    f"Test règle id={regle.id} champ={regle.champ_cible} regex={regle.regex_extraction}"
                )
                # Appliquer la regex au texte brut
                match = re.search(
                    regle.regex_extraction, facture.texte_brut_pdf, re.IGNORECASE | re.MULTILINE
                )

                if match:
                    valeur = match.group(1) if match.groups() else match.group(0)
                    logger.info(
                        f"Extraction OK: {regle.table_cible.value}.{regle.champ_cible} = {valeur}"
                    )

                    # Organiser par table cible
                    if regle.table_cible.value not in resultats:
                        resultats[regle.table_cible.value] = {}

                    resultats[regle.table_cible.value][regle.champ_cible] = _convertir_valeur(
                        valeur, regle.champ_cible
                    )
                else:
                    logger.debug(f"Pas de match pour règle id={regle.id} ({regle.champ_cible})")
            except re.error as e:
                logger.error(f"Erreur regex dans règle {regle.id}: {e}")
                continue

        return resultats


def _convertir_valeur(valeur: str, champ: str) -> Any:
    """Convertit une valeur string selon le type de champ attendu"""
    valeur = valeur.strip()

    # Conversion pour les champs de dates
    if "date" in champ.lower():
        return _convertir_date(valeur)

    # Conversion pour les champs d'index/montants
    if "index" in champ.lower() or "montant" in champ.lower():
        return _convertir_nombre(valeur)

    # Par défaut, retourner la string
    return valeur


def _convertir_date(valeur: str) -> Optional[datetime]:
    """Tente de convertir une string en datetime"""
    formats_dates = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d %m %Y"]

    for fmt in formats_dates:
        try:
            return datetime.strptime(valeur, fmt)
        except ValueError:
            continue

    return None


def _convertir_nombre(valeur: str) -> Optional[float]:
    """Tente de convertir une string en float"""
    # Nettoyer la valeur (enlever espaces, remplacer virgules par points)
    valeur_clean = valeur.replace(" ", "").replace(",", ".")

    try:
        return float(valeur_clean)
    except ValueError:
        return None


def appliquer_extractions_automatiques(facture_id: int) -> bool:
    """
    Applique les extractions automatiques à une facture et met à jour la base de données
    Retourne True si des champs ont été mis à jour
    """
    extractions = extraire_champs_automatiques(facture_id)

    if not extractions:
        return False

    with Session(engine) as session:
        logger.debug(
            f"Ouverture session pour appliquer_extractions_automatiques sur facture_id={facture_id}"
        )
        facture = session.get(Facture, facture_id)
        if not facture:
            logger.error(f"Facture id={facture_id} introuvable.")
            return False

        modifications = False

        # Mettre à jour la table facture
        if "facture" in extractions:
            logger.debug(
                f"Extraction de champs pour table 'facture': {list(extractions['facture'].keys())}"
            )
            for champ, valeur in extractions["facture"].items():
                if hasattr(facture, champ) and valeur is not None:
                    logger.info(f"MAJ Facture: {champ} = {valeur}")
                    setattr(facture, champ, valeur)
                    modifications = True
                else:
                    logger.debug(f"Champ '{champ}' non trouvé ou valeur None pour Facture.")

        # Mettre à jour la table facture_electricite
        if "electricite" in extractions:
            logger.debug(
                f"Extraction de champs pour table 'electricite': {list(extractions['electricite'].keys())}"
            )
            details_elec = session.exec(
                select(FactureElectricite).where(FactureElectricite.facture_id == facture_id)
            ).first()

            if details_elec:
                for champ, valeur in extractions["electricite"].items():
                    if hasattr(details_elec, champ) and valeur is not None:
                        logger.info(f"MAJ FactureElectricite: {champ} = {valeur}")
                        setattr(details_elec, champ, valeur)
                        modifications = True
                    else:
                        logger.debug(
                            f"Champ '{champ}' non trouvé ou valeur None pour FactureElectricite."
                        )
            else:
                logger.debug(f"Aucun détail FactureElectricite trouvé pour facture_id={facture_id}")

        if modifications:
            logger.info(f"Commit des modifications pour facture_id={facture_id}")
            session.commit()
        else:
            logger.info(f"Aucune modification appliquée pour facture_id={facture_id}")

        return modifications


def tester_regle_extraction(fournisseur_id: int, texte_test: str, regex: str) -> Optional[str]:
    """
    Teste une règle d'extraction sur un texte donné
    Retourne la valeur extraite ou None
    """
    try:
        match = re.search(regex, texte_test, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1) if match.groups() else match.group(0)
        return None
    except re.error:
        return None


def obtenir_regles_fournisseur(fournisseur_id: int):
    """Récupère toutes les règles d'extraction pour un fournisseur"""
    with Session(engine) as session:
        return session.exec(
            select(RegleExtractionChamp)
            .where(RegleExtractionChamp.fournisseur_id == fournisseur_id)
            .order_by(RegleExtractionChamp.table_cible, RegleExtractionChamp.champ_cible)
        ).all()
