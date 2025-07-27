from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from slc_app.models import BaseRepartition


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

    # Relations
    base_repartition: "BaseRepartition" = Relationship(back_populates="tantiemes")

    @field_validator("debut_occupation", "fin_occupation", mode="before")
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
