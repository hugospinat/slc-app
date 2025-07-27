"""
Constantes pour les parsers PH - noms des champs correspondant exactement aux modèles SQLModel
"""


class REG010:
    """Constantes pour le parser REG010 - Factures"""

    POSTE_ID = "poste_id"
    NUMERO_FACTURE = "numero_facture"
    CODE_JOURNAL = "code_journal"
    NUMERO_COMPTE_COMPTABLE = "numero_compte_comptable"
    MONTANT_COMPTABLE = "montant_comptable"
    LIBELLE_ECRITURE = "libelle_ecriture"
    REFERENCES_PARTENAIRE_FACTURE = "references_partenaire_facture"


class REG010_POSTE:
    """Constantes pour les postes extraits du REG010"""

    CONTROLE_ID = "controle_id"
    NOM = "nom"
    CODE = "code"


class REG114:
    """Constantes pour le parser REG114 - Tantièmes"""

    BASE_REPARTITION_ID = "base_repartition_id"
    NUMERO_UG = "numero_ug"
    NATURE_UG = "nature_ug"
    NUMERO_CA = "numero_ca"
    TANTIEME = "tantieme"
    RELIQUAT = "reliquat"


class REG114_BASE:
    """Constantes pour les bases de répartition extraites du REG114"""

    CONTROLE_ID = "controle_id"
    CODE = "code"
    NOM = "nom"


class EAU008C:
    """Constantes pour le parser EAU008C - Relevés individuels"""

    POSTE_RELEVE_ID = "poste_releve_id"
    NUMERO_UG = "numero_ug"
    NATURE_UG = "nature_ug"
    NUMERO_CA = "numero_ca"
    POINT_COMPTAGE = "point_comptage"
    NUMERO_SERIE_COMPTEUR = "numero_serie_compteur"
    DATE_RELEVE = "date_releve"
    DATE_VALEUR = "date_valeur"
    INDEX_RELEVE = "index_releve"


class EAU008C_POSTE:
    """Constantes pour les postes de relevé extraits du EAU008C"""

    CONTROLE_ID = "controle_id"
    NOM = "nom"


class GED001:
    """Constantes pour le parser GED001 - Factures PDF"""

    IDENTIFIANT = "identifiant"
    TYPE = "type"
    CHEMIN_FICHIER = "chemin_fichier"
    TEXTE_BRUT = "texte_brut"
