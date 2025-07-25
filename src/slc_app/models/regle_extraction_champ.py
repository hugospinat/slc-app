from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from slc_app.models import Fournisseur

from .type_facture import TypeFacture


class RegleExtractionChamp(SQLModel, table=True):
    """Règles d'extraction automatique de champs à partir du texte PDF"""

    id: Optional[int] = Field(default=None, primary_key=True)
    fournisseur_id: int = Field(foreign_key="fournisseur.id")
    table_cible: TypeFacture
    champ_cible: str
    regex_extraction: str
    description: Optional[str] = None
    actif: bool = Field(default=True)

    # Relations
    fournisseur: "Fournisseur" = Relationship(back_populates="regles_extraction")
