from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from slc_app.models import PosteReleve


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
    index_releve: int = None
    evolution_index: Optional[int] = None

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
