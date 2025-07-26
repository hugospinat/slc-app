from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Optional

import pandas as pd
from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from slc_app.models import PosteReleve

from .columns import SourceColReleveIndividuel


class ReleveIndividuel(SQLModel, table=True):
    """Table des relevés individuels pour les compteurs"""

    id: Optional[int] = Field(default=None, primary_key=True)
    poste_releve_id: int = Field(foreign_key="postereleve.id")
    numero_ug: str
    nature_ug: Optional[str] = None
    numero_ca: str
    point_comptage: Optional[str] = None
    numero_serie_compteur: Optional[str] = None
    date_releve: Optional[datetime] = None
    date_valeur: Optional[datetime] = None
    type_releve: Optional[str] = None
    observations: Optional[str] = None
    index_releve: Optional[float] = None
    evolution_index: Optional[float] = None

    # Relations
    poste_releve: "PosteReleve" = Relationship(back_populates="releves_individuels")

    @field_validator("date_releve", "date_valeur", mode="before")
    @classmethod
    def parse_date_string(cls, v) -> Optional[datetime]:
        """Parse les dates au format français (jj/mm/aaaa) vers datetime"""
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return None

        if isinstance(v, datetime):
            return v

        if isinstance(v, str):
            v = v.strip()
            # Format français : jj/mm/aaaa
            try:
                return datetime.strptime(v, "%d/%m/%Y")
            except ValueError:
                # Essayer d'autres formats courants
                try:
                    return datetime.strptime(v, "%d-%m-%Y")
                except ValueError:
                    try:
                        return datetime.strptime(v, "%Y-%m-%d")
                    except ValueError:
                        # Si aucun format ne marche, retourner None
                        return None

        return None

    @field_validator("index_releve", "evolution_index", mode="before")
    @classmethod
    def parse_float_string(cls, v) -> Optional[float]:
        """Parse les valeurs numériques vers float"""
        if v is None or v == "" or (isinstance(v, str) and v.strip() == ""):
            return None

        if isinstance(v, (int, float)):
            return float(v)

        if isinstance(v, str):
            v = v.strip().replace(",", ".")  # Remplacer virgule par point
            try:
                return float(v)
            except ValueError:
                return None

        return None

    column_map: ClassVar[dict] = {
        "poste_releve_id": SourceColReleveIndividuel.POSTE_RELEVE_ID,
        "numero_ug": SourceColReleveIndividuel.NUMERO_UG,
        "nature_ug": SourceColReleveIndividuel.NATURE_UG,
        "numero_ca": SourceColReleveIndividuel.NUMERO_CA,
        "point_comptage": SourceColReleveIndividuel.POINT_COMPTAGE,
        "numero_serie_compteur": SourceColReleveIndividuel.NUMERO_SERIE_COMPTEUR,
        "date_releve": SourceColReleveIndividuel.DATE_RELEVE,
        "date_valeur": SourceColReleveIndividuel.DATE_VALEUR,
        "type_releve": SourceColReleveIndividuel.TYPE_RELEVE,
        "observations": SourceColReleveIndividuel.OBSERVATIONS,
        "index_releve": SourceColReleveIndividuel.INDEX,
        "evolution_index": SourceColReleveIndividuel.EVOLUTION_INDEX,
    }

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> list["ReleveIndividuel"]:
        rename_map = {enum.value: field for field, enum in cls.column_map.items()}
        df = df.rename(columns=rename_map)
        df = df[df["poste_releve_id"].notna()].copy()
        return df.apply(lambda row: cls.model_validate(row.to_dict()), axis=1).tolist()  # type: ignore
