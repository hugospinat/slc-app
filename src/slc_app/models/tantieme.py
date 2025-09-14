from datetime import datetime
from typing import TYPE_CHECKING, Optional
from decimal import Decimal
import pandas as pd

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
    tantieme: Decimal = Field(..., max_digits=8, decimal_places=2)
    reliquat: Decimal = Field(..., max_digits=8, decimal_places=2)

    # Relations
    base_repartition: "BaseRepartition" = Relationship(back_populates="tantiemes")
