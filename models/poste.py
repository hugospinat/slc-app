from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


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
