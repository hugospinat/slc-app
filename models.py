from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, Session, SQLModel, create_engine


class Groupe(SQLModel, table=True):
    """Table pour les groupes"""

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(index=True)
    identifiant: str = Field(unique=True)

    # Relation vers ControleCharges
    controles: List["ControleCharges"] = Relationship(back_populates="groupe")


class ControleCharges(SQLModel, table=True):
    """Table pour le contrôle des charges par année et groupe"""

    id: Optional[int] = Field(default=None, primary_key=True)
    annee: int = Field(index=True)
    groupe_id: int = Field(foreign_key="groupe.id")
    created_at: datetime = Field(default_factory=datetime.now)

    # Relations
    groupe: Groupe = Relationship(back_populates="controles")
    factures: List["Facture"] = Relationship(back_populates="controle")


class Facture(SQLModel, table=True):
    """Table pour les factures extraites des PDF"""

    id: Optional[int] = Field(default=None, primary_key=True)
    controle_id: int = Field(foreign_key="controlecharges.id")

    # Champs extraits du PDF
    nature: str
    numero_facture: str
    code_journal: str
    numero_compte_comptable: str
    montant_comptable: float
    libelle_ecriture: str
    references_partenaire_facture: str

    # Statut de validation
    statut: str = Field(default="en_attente")  # en_attente, validee, contestee
    commentaire_contestation: Optional[str] = None
    date_traitement: Optional[datetime] = None

    # Métadonnées
    fichier_source: str
    ligne_pdf: int
    created_at: datetime = Field(default_factory=datetime.now)

    # Relations
    controle: ControleCharges = Relationship(back_populates="factures")


# Configuration de la base de données
DATABASE_URL = "sqlite:///charge_control.db"
engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables():
    """Créer la base de données et les tables"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Obtenir une session de base de données"""
    with Session(engine) as session:
        yield session
