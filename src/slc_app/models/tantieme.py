from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Optional

import pandas as pd
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .base_repartition import BaseRepartition

from .columns import SourceColTantieme


class Tantieme(SQLModel, table=True):
    """Table des tantièmes pour la répartition des charges"""

    id: Optional[int] = Field(default=None, primary_key=True)
    base_repartition_id: int = Field(foreign_key="baserepartition.id")
    numero_ug: str
    numero_ca: str
    debut_occupation: Optional[datetime] = None
    fin_occupation: Optional[datetime] = None
    tantieme: Optional[float] = None
    reliquat: Optional[float] = None
    fichier_source: str
    ligne_pdf: int

    # Relations
    base_repartition: "BaseRepartition" = Relationship(back_populates="tantiemes")

    column_map: ClassVar[dict] = {
        "base_repartition_id": SourceColTantieme.BASE_ID,
        "numero_ug": SourceColTantieme.NUMERO_UG,
        "numero_ca": SourceColTantieme.NUMERO_CA,
        "debut_occupation": SourceColTantieme.DEBUT_OCCUPATION,
        "fin_occupation": SourceColTantieme.FIN_OCCUPATION,
        "tantieme": SourceColTantieme.TANTIEME,
        "reliquat": SourceColTantieme.RELIQUAT,
        "fichier_source": SourceColTantieme.FICHIER_SOURCE,
        "ligne_pdf": SourceColTantieme.LIGNE_PDF,
    }

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> list["Tantieme"]:
        rename_map = {enum.value: field for field, enum in cls.column_map.items()}
        df = df.rename(columns=rename_map)
        df = df[df["base_repartition_id"].notna()].copy()
        return df.apply(lambda row: cls(**row.to_dict()), axis=1).tolist()  # type: ignore
