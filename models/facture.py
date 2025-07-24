from datetime import datetime
from typing import Optional

import pandas as pd
from sqlmodel import Field, Relationship, SQLModel

from .columns import SourceColFacture


class Facture(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    poste_id: int = Field(foreign_key="poste.id")
    nature: str
    numero_facture: str
    code_journal: str
    numero_compte_comptable: str
    montant_comptable: float
    libelle_ecriture: str
    references_partenaire_facture: str
    fichier_source: str
    ligne_pdf: int
    statut: str = "en_attente"
    commentaire_contestation: Optional[str] = None
    date_traitement: Optional[datetime] = None
    pdf_facture_nom: Optional[str] = None
    pdf_facture_contenu: Optional[bytes] = None
    texte_brut_pdf: Optional[str] = None
    fournisseur_id: Optional[int] = Field(default=None, foreign_key="fournisseur.id")

    # Relations
    poste: "Poste" = Relationship(back_populates="factures")
    details_electricite: Optional["FactureElectricite"] = Relationship(back_populates="facture")
    fournisseur: Optional["Fournisseur"] = Relationship(back_populates="factures")

    column_map = {
        "nature": SourceColFacture.NATURE,
        "numero_facture": SourceColFacture.NUMERO_FACTURE,
        "code_journal": SourceColFacture.CODE_JOURNAL,
        "numero_compte_comptable": SourceColFacture.NUMERO_COMPTE_COMPTABLE,
        "montant_comptable": SourceColFacture.MONTANT_COMPTABLE,
        "libelle_ecriture": SourceColFacture.LIBELLE_ECRITURE,
        "references_partenaire_facture": SourceColFacture.REFERENCES_PARTENAIRE_FACTURE,
        "fichier_source": SourceColFacture.FICHIER_SOURCE,
        "ligne_pdf": SourceColFacture.LIGNE_PDF,
    }

    @classmethod
    def from_df(cls, df: pd.DataFrame, **extra_fields) -> list["Facture"]:
        rename_map = {enum.value: field for field, enum in cls.column_map.items()}
        df = df.rename(columns=rename_map)
        for key, value in extra_fields.items():
            df[key] = value
        return [cls(**row) for row in df.to_dict(orient="records")]
