from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from slc_app.models import ControleCharges, Tantieme


class BaseRepartition(SQLModel, table=True):
    """Base de répartition des charges (ex: SRC - Base de répart. Charges)"""

    id: Optional[int] = Field(default=None, primary_key=True)
    controle_id: int = Field(foreign_key="controlecharges.id")
    code: str
    nom: str

    # Relations
    controle: "ControleCharges" = Relationship(back_populates="bases_repartition")
    tantiemes: List["Tantieme"] = Relationship(back_populates="base_repartition")
