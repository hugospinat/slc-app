from enum import Enum


class SourceDf(str, Enum):
    TANTIEMES = "tantiemes"
    BASES_REPARTITION = "bases_repartition"
    FACTURES = "factures"
    GROUPES = "groupes"
    CONTROLES = "controles"
    POSTES = "postes"


class SourceColBaseRep(str, Enum):
    CONTROLE_ID = "controle_id"
    CODE = "code"
    NOM = "nom"
    FICHIER_SOURCE = "fichier_source"
    LIGNE_PDF = "ligne_pdf"


class SourceColPoste(str, Enum):
    CONTROLE_ID = "controle_id"
    NOM = "nom"
    CODE = "code"
    FICHIER_SOURCE = "fichier_source"
    LIGNE_PDF = "ligne_pdf"
    GROUPE_ID = "groupe_id"


class SourceColTantieme(str, Enum):
    BASE_ID = "base_id"
    NUMERO_UG = "numero_ug"
    NUMERO_CA = "numero_ca"
    DEBUT_OCCUPATION = "debut_occupation"
    FIN_OCCUPATION = "fin_occupation"
    TANTIEME = "tantieme"
    RELIQUAT = "reliquat"
    FICHIER_SOURCE = "fichier_source"
    LIGNE_PDF = "ligne_pdf"


class SourceColFacture(str, Enum):
    POSTE_ID = "poste_id"
    NUMERO_FACTURE = "numero_facture"
    CODE_JOURNAL = "code_journal"
    NUMERO_COMPTE_COMPTABLE = "numero_compte_comptable"
    MONTANT_COMPTABLE = "montant_comptable"
    LIBELLE_ECRITURE = "libelle_ecriture"
    REFERENCES_PARTENAIRE_FACTURE = "references_partenaire_facture"
    FICHIER_SOURCE = "fichier_source"
    LIGNE_PDF = "ligne_pdf"


class GED001Columns(str, Enum):
    """Colonnes du DataFrame pour les données GED001"""

    IDENTIFIANT = "identifiant"
    TYPE = "type"
    TEXTE_BRUT = "texte_brut"
    PATH_TO_PDF_EXTRAIT = "path_to_pdf_extrait"
    CONTENU_PDF = "contenu_pdf"
