from typing import TYPE_CHECKING, ClassVar, List, Optional

import pandas as pd
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from slc_app.models import ReleveIndividuel, ControleCharges

from .columns import SourceColPosteReleve


class PosteReleve(SQLModel, table=True):
    """Poste de relevé individuel (ex: EAU CHAUDE INDIVIDUELLE, EAU FROIDE INDIVIDUELLE, COMPTEUR DE CALORIE)"""

    id: Optional[int] = Field(default=None, primary_key=True)
    controle_id: int = Field(foreign_key="controlecharges.id")
    nom: str  # Nom du poste de relevé

    # Relations
    controle: "ControleCharges" = Relationship(back_populates="postes_releve")
    releves_individuels: List["ReleveIndividuel"] = Relationship(back_populates="poste_releve")

    column_map: ClassVar[dict] = {
        "controle_id": SourceColPosteReleve.CONTROLE_ID,
        "nom": SourceColPosteReleve.NOM,
    }

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> list["PosteReleve"]:
        """Convertir un DataFrame en liste d'objets PosteReleve"""
        rename_map = {enum.value: field for field, enum in cls.column_map.items()}
        df = df.rename(columns=rename_map)
        return df.apply(lambda row: cls(**row.to_dict()), axis=1).tolist()  # type: ignore
