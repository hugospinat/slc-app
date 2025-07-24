from typing import Optional

from sqlmodel import Field, SQLModel


class FacturePDF(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    facture_id: Optional[int] = Field(foreign_key="facture.id")
    pdf_facture_nom: str
    pdf_facture_contenu: str
    texte_brut_pdf: str
