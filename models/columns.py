from enum import Enum


class SourceColBaseRepartition(str, Enum):
    CODE = "code"
    NOM = "nom"
    CDC_CONCERNE = "cdc_concerne"
    FICHIER_SOURCE = "fichier_source"
    LIGNE_PDF = "ligne_pdf"


class SourceColTantieme(str, Enum):
    BASE_CODE = "base_code"
    NUMERO_UG = "numero_ug"
    NUMERO_CA = "numero_ca"
    DEBUT_OCCUPATION = "debut_occupation"
    FIN_OCCUPATION = "fin_occupation"
    TANTIEME = "tantieme"
    RELIQUAT = "reliquat"
    FICHIER_SOURCE = "fichier_source"
    LIGNE_PDF = "ligne_pdf"


class SourceColFacture(str, Enum):
    NATURE = "nature"
    NUMERO_FACTURE = "numero_facture"
    CODE_JOURNAL = "code_journal"
    NUMERO_COMPTE_COMPTABLE = "numero_compte_comptable"
    MONTANT_COMPTABLE = "montant_comptable"
    LIBELLE_ECRITURE = "libelle_ecriture"
    REFERENCES_PARTENAIRE_FACTURE = "references_partenaire_facture"
    FICHIER_SOURCE = "fichier_source"
    LIGNE_PDF = "ligne_pdf"
