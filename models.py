from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel, create_engine


class TypeFacture(str, Enum):
    """Types de factures gérés par l'application"""

    ELECTRICITE = "electricite"
    GAZ = "gaz"
    EAU = "eau"
    FACTURE = "facture"  # Pour les règles d'extraction sur la table facture générale


# Définition des modèles
class Groupe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    identifiant: str

    # Relations
    controles: List["ControleCharges"] = Relationship(back_populates="groupe")


class Poste(SQLModel, table=True):
    """Poste de charges (ex: Eau Froide, Chauffage, etc.)"""

    id: Optional[int] = Field(default=None, primary_key=True)
    controle_id: int = Field(foreign_key="controlecharges.id")
    code: str  # Code du poste (ex: EFF, ECF, etc.)
    nom: str  # Nom du poste
    rapport: Optional[str] = None  # Rapport de contrôle au format markdown

    # Relations
    controle: "ControleCharges" = Relationship(back_populates="postes")
    factures: List["Facture"] = Relationship(back_populates="poste")


class ControleCharges(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    groupe_id: int = Field(foreign_key="groupe.id")
    annee: int
    remarque_globale: Optional[str] = Field(default=None)

    # Relations
    groupe: Groupe = Relationship(back_populates="controles")
    postes: List["Poste"] = Relationship(back_populates="controle")


class RegleExtractionChamp(SQLModel, table=True):
    """Règles d'extraction automatique de champs à partir du texte PDF"""

    id: Optional[int] = Field(default=None, primary_key=True)
    fournisseur_id: int = Field(foreign_key="fournisseur.id")
    table_cible: TypeFacture  # Table à modifier (facture, electricite, gaz, eau, autre)
    champ_cible: str  # Nom du champ à remplir
    regex_extraction: str  # Regex pour extraire la valeur du texte PDF
    description: Optional[str] = None  # Description de ce que fait cette règle
    actif: bool = Field(default=True)  # Permet de désactiver temporairement une règle

    # Relations
    fournisseur: "Fournisseur" = Relationship(back_populates="regles_extraction")


class Fournisseur(SQLModel, table=True):
    """Fournisseur de services (électricité, gaz, etc.)"""

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(index=True)
    type_facture: TypeFacture
    champ_detection: str = Field(default="libelle_ecriture")  # Champ utilisé pour la détection
    regex_detection: Optional[str] = None  # Expression régulière pour détecter le fournisseur

    # Relations
    factures: List["Facture"] = Relationship(back_populates="fournisseur")
    regles_extraction: List["RegleExtractionChamp"] = Relationship(back_populates="fournisseur")


class Facture(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    poste_id: int = Field(foreign_key="poste.id")
    nature: str
    numero_facture: str
    code_journal: str
    numero_compte_comptable: str
    montant_comptable: float
    libelle_ecriture: str
    references_partenaire_facture: str
    fichier_source: str
    ligne_pdf: int
    statut: str = "en_attente"  # en_attente, validee, contestee
    commentaire_contestation: Optional[str] = None
    date_traitement: Optional[datetime] = None
    pdf_facture_nom: Optional[str] = None
    pdf_facture_contenu: Optional[bytes] = None
    texte_brut_pdf: Optional[str] = None  # Texte brut extrait du PDF pour l'extraction de champs
    fournisseur_id: Optional[int] = Field(default=None, foreign_key="fournisseur.id")

    # Relations
    poste: Poste = Relationship(back_populates="factures")
    details_electricite: Optional["FactureElectricite"] = Relationship(back_populates="facture")
    fournisseur: Optional[Fournisseur] = Relationship(back_populates="factures")


class FactureElectricite(SQLModel, table=True):
    """Facture d'électricité avec ses champs spécifiques"""

    id: Optional[int] = Field(default=None, primary_key=True)
    facture_id: int = Field(foreign_key="facture.id")
    index_debut: Optional[float] = None
    index_fin: Optional[float] = None
    date_debut: Optional[datetime] = None
    date_fin: Optional[datetime] = None

    # Relations
    facture: "Facture" = Relationship(back_populates="details_electricite")


# Configuration de la base de données
DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL)


def clear_registry():
    """Nettoyer le registre SQLModel pour éviter les conflits"""
    SQLModel.metadata.clear()


def create_db_and_tables():
    """Créer les tables de base de données"""
    SQLModel.metadata.create_all(engine)
