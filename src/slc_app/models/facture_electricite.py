from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .facture import Facture


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
