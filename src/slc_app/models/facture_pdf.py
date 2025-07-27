from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

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
