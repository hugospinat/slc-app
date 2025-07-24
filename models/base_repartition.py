from typing import List, Optional

import pandas as pd
from sqlmodel import Field, Relationship, SQLModel

from .columns import SourceColBaseRepartition


class BaseRepartition(SQLModel, table=True):
    """Base de répartition des charges (ex: SRC - Base de répart. Charges)"""

    id: Optional[int] = Field(default=None, primary_key=True)
    controle_id: int = Field(foreign_key="controlecharges.id")
    code: str
    nom: str
    cdc_concerne: Optional[str] = None
    fichier_source: str
    ligne_pdf: int

    # Relations
    controle: "ControleCharges" = Relationship(back_populates="bases_repartition")
    tantiemes: List["Tantieme"] = Relationship(back_populates="base_repartition")

    column_map = {
        "code": SourceColBaseRepartition.CODE,
        "nom": SourceColBaseRepartition.NOM,
        "cdc_concerne": SourceColBaseRepartition.CDC_CONCERNE,
        "fichier_source": SourceColBaseRepartition.FICHIER_SOURCE,
        "ligne_pdf": SourceColBaseRepartition.LIGNE_PDF,
    }

    @classmethod
    def from_df(cls, df: pd.DataFrame, controle_id: int) -> list["BaseRepartition"]:
        rename_map = {enum.value: field for field, enum in cls.column_map.items()}
        df = df.rename(columns=rename_map)
        df["controle_id"] = controle_id
        return [cls(**row) for row in df.to_dict(orient="records")]
