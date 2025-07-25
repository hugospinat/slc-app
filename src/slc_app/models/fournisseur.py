from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from slc_app.models.facture import Facture
    from slc_app.models.regle_extraction_champ import RegleExtractionChamp

from slc_app.models.type_facture import TypeFacture


class Fournisseur(SQLModel, table=True):
    """Fournisseur de services (électricité, gaz, etc.)"""

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(index=True)
    type_facture: TypeFacture
    champ_detection: str = Field(default="libelle_ecriture")
    regex_detection: Optional[str] = None

    # Relations
    factures: List["Facture"] = Relationship(back_populates="fournisseur")
    regles_extraction: List["RegleExtractionChamp"] = Relationship(back_populates="fournisseur")
