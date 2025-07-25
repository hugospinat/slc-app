import re
from typing import Dict, Optional

from sqlmodel import Session, select

from slc_app.models import Fournisseur, engine
from src.slc_app.utils import logging_config  # noqa: F401


def detecter_fournisseur(row_data: Dict) -> Optional[int]:
    """
    Détecter automatiquement le fournisseur basé sur les données de la ligne
    Utilise le champ spécifié dans champ_detection et le regex_detection du fournisseur
    Retourne l'ID du fournisseur s'il est détecté, None sinon
    """
    with Session(engine) as session:
        fournisseurs = session.exec(select(Fournisseur)).all()

        for fournisseur in fournisseurs:
            # Récupérer la valeur du champ à analyser
            champ_valeur = str(row_data.get(fournisseur.champ_detection, ""))

            if not champ_valeur or champ_valeur == "nan":
                continue

            # Recherche par regex si définie
            if fournisseur.regex_detection:
                try:
                    if re.search(fournisseur.regex_detection, champ_valeur, re.IGNORECASE):
                        return fournisseur.id
                except re.error:
                    # Regex invalide, continuer avec la recherche simple
                    pass
    return None


def detecter_fournisseurs_depuis_dataframe(df) -> Dict[str, int]:
    """
    Analyser le DataFrame pour détecter automatiquement les fournisseurs existants
    Retourne un dictionnaire {numero_facture: fournisseur_id}
    """
    associations = {}

    for _, row in df.iterrows():
        numero_facture = str(row["numero_facture"])

        # Convertir la ligne en dictionnaire pour faciliter l'accès aux champs
        row_data = {
            "nature": str(row.get("nature", "")),
            "numero_facture": str(row.get("numero_facture", "")),
            "code_journal": str(row.get("code_journal", "")),
            "numero_compte_comptable": str(row.get("numero_compte_comptable", "")),
            "libelle_ecriture": str(row.get("libelle_ecriture", "")),
            "references_partenaire_facture": str(row.get("references_partenaire_facture", "")),
        }

        # Détecter le fournisseur existant
        fournisseur_id = detecter_fournisseur(row_data)

        if fournisseur_id:
            associations[numero_facture] = fournisseur_id

    return associations


def obtenir_statistiques_detection(associations: Dict[str, int]) -> Dict:
    """
    Obtenir des statistiques sur la détection des fournisseurs
    """
    with Session(engine) as session:
        stats = {
            "total_factures": len(associations),
            "fournisseurs_detectes": len(set(associations.values())),
            "details_fournisseurs": {},
        }

        for fournisseur_id in set(associations.values()):
            fournisseur = session.get(Fournisseur, fournisseur_id)
            if fournisseur:
                nb_factures = list(associations.values()).count(fournisseur_id)
                stats["details_fournisseurs"][fournisseur.nom] = {
                    "type": fournisseur.type_facture,
                    "nb_factures": nb_factures,
                }

        return stats
