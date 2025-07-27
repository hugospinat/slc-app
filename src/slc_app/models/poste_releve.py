from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from slc_app.models import ReleveIndividuel, ControleCharges


class PosteReleve(SQLModel, table=True):
    """Poste de relevé individuel (ex: EAU CHAUDE INDIVIDUELLE, EAU FROIDE INDIVIDUELLE, COMPTEUR DE CALORIE)"""

    id: Optional[int] = Field(default=None, primary_key=True)
    controle_id: int = Field(foreign_key="controlecharges.id")
    nom: str  # Nom du poste de relevé

    # Relations
    controle: "ControleCharges" = Relationship(back_populates="postes_releve")
    releves_individuels: List["ReleveIndividuel"] = Relationship(back_populates="poste_releve")
