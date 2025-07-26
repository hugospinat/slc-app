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


class SourceColPoste(str, Enum):
    CONTROLE_ID = "controle_id"
    NOM = "nom"
    CODE = "code"


class SourceColTantieme(str, Enum):
    BASE_ID = "base_id"
    NUMERO_UG = "numero_ug"
    NUMERO_CA = "numero_ca"
    DEBUT_OCCUPATION = "debut_occupation"
    FIN_OCCUPATION = "fin_occupation"
    TANTIEME = "tantieme"
    RELIQUAT = "reliquat"


class SourceColFacture(str, Enum):
    POSTE_ID = "poste_id"
    NUMERO_FACTURE = "numero_facture"
    CODE_JOURNAL = "code_journal"
    NUMERO_COMPTE_COMPTABLE = "numero_compte_comptable"
    MONTANT_COMPTABLE = "montant_comptable"
    LIBELLE_ECRITURE = "libelle_ecriture"
    REFERENCES_PARTENAIRE_FACTURE = "references_partenaire_facture"


class SourceColPosteReleve(str, Enum):
    CONTROLE_ID = "controle_id"
    NOM = "nom"


class SourceColReleveIndividuel(str, Enum):
    POSTE_RELEVE_ID = "poste_releve_id"
    NUMERO_UG = "numero_ug"
    NATURE_UG = "nature_ug"
    NUMERO_CA = "numero_ca"
    POINT_COMPTAGE = "point_comptage"
    NUMERO_SERIE_COMPTEUR = "numero_serie_compteur"
    DATE_RELEVE = "date_releve"
    DATE_VALEUR = "date_valeur"
    TYPE_RELEVE = "type_releve"
    OBSERVATIONS = "observations"
    INDEX = "index"
    EVOLUTION_INDEX = "evolution_index"


class GED001Columns(str, Enum):
    """Colonnes du DataFrame pour les données GED001"""

    IDENTIFIANT = "identifiant"
    TYPE = "type"
    TEXTE_BRUT = "texte_brut"
    PATH_TO_PDF_EXTRAIT = "path_to_pdf_extrait"
    CONTENU_PDF = "contenu_pdf"
