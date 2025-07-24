from datetime import datetime
from typing import Optional

import pandas as pd
from sqlmodel import Field, Relationship, SQLModel

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

    column_map = {
        "base_code": SourceColTantieme.BASE_CODE,
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
    def from_df(cls, df: pd.DataFrame, base_id_map: dict[str, int]) -> list["Tantieme"]:
        rename_map = {enum.value: field for field, enum in cls.column_map.items()}
        df = df.rename(columns=rename_map)
        df["base_repartition_id"] = df.pop("base_code").map(base_id_map)
        df = df[df["base_repartition_id"].notna()].copy()
        return [cls(**row) for row in df.to_dict(orient="records")]
