from typing import TYPE_CHECKING, ClassVar, List, Optional

import pandas as pd
from sqlmodel import Field, Relationship, SQLModel

from slc_app.models.columns import SourceColBaseRep

if TYPE_CHECKING:
    from slc_app.models.controle_charges import ControleCharges
    from slc_app.models.tantieme import Tantieme


class BaseRepartition(SQLModel, table=True):
    """Base de répartition des charges (ex: SRC - Base de répart. Charges)"""

    id: Optional[int] = Field(default=None, primary_key=True)
    controle_id: int = Field(foreign_key="controlecharges.id")
    code: str
    nom: str
    fichier_source: str
    ligne_pdf: int

    # Relations

    controle: "ControleCharges" = Relationship(back_populates="bases_repartition")
    tantiemes: List["Tantieme"] = Relationship(back_populates="base_repartition")

    column_map: ClassVar[dict] = {
        "code": SourceColBaseRep.CODE,
        "nom": SourceColBaseRep.NOM,
        "controle_id": SourceColBaseRep.CONTROLE_ID,
        "fichier_source": SourceColBaseRep.FICHIER_SOURCE,
        "ligne_pdf": SourceColBaseRep.LIGNE_PDF,
    }

    @classmethod
    def from_df(cls, df: pd.DataFrame, controle_id: int) -> list["BaseRepartition"]:
        rename_map = {enum.value: field for field, enum in cls.column_map.items()}
        df = df.rename(columns=rename_map)
        df["controle_id"] = controle_id
        return df.apply(lambda row: cls(**row.to_dict()), axis=1).tolist()  # type: ignore
