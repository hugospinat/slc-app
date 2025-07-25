from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from slc_app.models.controle_charges import ControleCharges


class Groupe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    identifiant: str

    # Relations
    controles: List["ControleCharges"] = Relationship(back_populates="groupe")
