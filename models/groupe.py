from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class Groupe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    identifiant: str

    # Relations
    controles: List["ControleCharges"] = Relationship(back_populates="groupe")
