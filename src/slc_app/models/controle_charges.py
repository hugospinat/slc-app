from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .base_repartition import BaseRepartition
    from .groupe import Groupe
    from .poste import Poste


class ControleCharges(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    groupe_id: int = Field(foreign_key="groupe.id")
    annee: int
    remarque_globale: Optional[str] = Field(default=None)

    # Relations
    groupe: "Groupe" = Relationship(back_populates="controles")
    postes: List["Poste"] = Relationship(back_populates="controle")
    bases_repartition: List["BaseRepartition"] = Relationship(back_populates="controle")
