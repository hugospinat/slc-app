from enum import Enum


class TypeFacture(str, Enum):
    """Types de factures gérés par l'application"""

    ELECTRICITE = "electricite"
    GAZ = "gaz"
    EAU = "eau"
    FACTURE = "facture"  # Pour les règles d'extraction sur la table facture générale
