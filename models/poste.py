from typing import List, Optional

import pandas as pd
from sqlmodel import Field, Relationship, SQLModel

from models.columns import SourceColPoste
from models.controle_charges import ControleCharges
from models.facture import Facture


class Poste(SQLModel, table=True):
    """Poste de charges (ex: Eau Froide, Chauffage, etc.)"""

    id: Optional[int] = Field(default=None, primary_key=True)
    controle_id: int = Field(foreign_key="controlecharges.id")
    code: str  # Code du poste (ex: EFF, ECF, etc.)
    nom: str  # Nom du poste
    rapport: Optional[str] = None  # Rapport de contrôle au format markdown

    # Relations
    controle: ControleCharges = Relationship(back_populates="postes")
    factures: List[Facture] = Relationship(back_populates="poste")

    column_map = {
        "code": SourceColPoste.CODE,
        "nom": SourceColPoste.NOM,
    }

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> list["Poste"]:
        """Convertir un DataFrame en liste d'objets Poste"""
        rename_map = {enum.value: field for field, enum in cls.column_map.items()}
        df = df.rename(columns=rename_map)
        return df.apply(lambda row: cls(**row.to_dict()), axis=1).tolist()  # type: ignore
