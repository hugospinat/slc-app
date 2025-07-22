from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel, create_engine


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

    # Relations
    poste: Poste = Relationship(back_populates="factures")


# Configuration de la base de données
DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
