from typing import TYPE_CHECKING, ClassVar, List, Optional

import pandas as pd
from sqlmodel import Field, Relationship, SQLModel

from .columns import GED001Columns

if TYPE_CHECKING:
    from slc_app.models import Facture


class FacturePDF(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    identifiant: Optional[str] = Field(default=None, index=True)  # label pour associé aux factures
    type: Optional[str] = Field(default=None)
    chemin_fichier: str
    texte_brut: str

    # Relations - Un PDF peut contenir plusieurs factures
    factures: List["Facture"] = Relationship(back_populates="facture_pdf")

    # Mapping des colonnes pour from_df
    column_map: ClassVar[dict] = {
        "identifiant": GED001Columns.IDENTIFIANT,
        "type": GED001Columns.TYPE,
        "chemin_fichier": GED001Columns.PATH_TO_PDF_EXTRAIT,
        "texte_brut": GED001Columns.TEXTE_BRUT,
    }

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> List["FacturePDF"]:
        """
        Créer une liste de FacturePDF depuis un DataFrame
        """
        rename_map = {enum_val: field for field, enum_val in cls.column_map.items()}
        df = df.rename(columns=rename_map)
        return df.apply(lambda row: cls(**row.to_dict()), axis=1).tolist()  # type: ignore
