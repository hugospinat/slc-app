from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from slc_app.models import FactureElectricite, FacturePDF, Fournisseur, Poste


class Facture(SQLModel, table=True):
    numero_local: Optional[str] = None
    id: Optional[int] = Field(default=None, primary_key=True)
    poste_id: int = Field(foreign_key="poste.id")
    numero_facture: Optional[str] = None
    code_journal: str
    numero_compte_comptable: str
    montant_comptable: float
    libelle_ecriture: str
    references_partenaire_facture: Optional[str] = None
    statut: str = "en_attente"
    commentaire_contestation: Optional[str] = None
    date_traitement: Optional[datetime] = None
    texte_brut_pdf: Optional[str] = None
    fournisseur_id: Optional[int] = Field(default=None, foreign_key="fournisseur.id")
    facture_pdf_id: Optional[int] = Field(default=None, foreign_key="facturepdf.id")

    # Relations
    poste: "Poste" = Relationship(back_populates="factures")
    details_electricite: Optional["FactureElectricite"] = Relationship(back_populates="facture")
    fournisseur: Optional["Fournisseur"] = Relationship(back_populates="factures")
    facture_pdf: Optional["FacturePDF"] = Relationship(back_populates="factures")
