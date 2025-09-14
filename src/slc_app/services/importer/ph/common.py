from slc_app.utils.dataframe_mapper import create_objects_from_df
from slc_app.utils.logger import logger
import os
from typing import Dict, List, Tuple, Type, TypeVar

T = TypeVar("T")

import pandas as pd
import tabula.io as tabula
from sqlmodel import Session

from slc_app.models import PosteReleve, ReleveIndividuel


class TableauParser:
    """Classe General de configuration pour les parsers"""

    def __init__(self, df: pd.DataFrame):
        self.df = df

    @classmethod
    def from_pdf(cls, pdf_path: str, min_columns: int):
        df = cls._extract_data(pdf_path, min_columns)
        return cls(df)

    @staticmethod
    def _extract_data(pdf_path: str, min_columns: int) -> pd.DataFrame:
        try:
            logger.info(f"Traitement du fichier : {pdf_path}")
            logger.info(f"🔄 Extraction du PDF: {os.path.basename(pdf_path)}")

            dfs = tabula.read_pdf(
                pdf_path,
                pages="all",
                lattice=True,
                pandas_options={"header": None},
            )

            if not dfs:
                logger.warning(f"Aucun tableau trouvé dans {pdf_path}")
                raise ValueError(f"Aucun tableau trouvé dans {pdf_path}")

            # Combiner tous les DataFrames
            combined_df = pd.concat(dfs, ignore_index=True)
            logger.info(
                f"📊 Données brutes extraites: {len(combined_df)} lignes, {combined_df.shape[1]} colonnes"
            )

            # LOG: Afficher le contenu brut extrait du PDF pour debug
            logger.info("[DEBUG] Structure complète du DataFrame extrait:")
            logger.info(f"[DEBUG] Colonnes: {list(combined_df.columns)}")
            logger.info("[DEBUG] Premiers 15 lignes du DataFrame brut:")
            for i in range(min(15, len(combined_df))):
                ligne_str = " | ".join(
                    [str(val) if pd.notna(val) else "NaN" for val in combined_df.iloc[i]]
                )
                logger.info(f"[DEBUG] Ligne {i}: {ligne_str}")

            if len(combined_df) > 15:
                logger.info(f"[DEBUG] ... ({len(combined_df) - 15} autres lignes)")

            logger.info("[DEBUG] Fin de l'affichage du DataFrame brut")

            if combined_df.empty or combined_df.shape[1] < min_columns:
                logger.error(
                    f"Format incorrect: {combined_df.shape[1]} colonnes (minimum {min_columns} requis pour {pdf_path})"
                )
                raise ValueError(
                    f"Format incorrect: {combined_df.shape[1]} colonnes (minimum {min_columns} requis {pdf_path})"
                )

            return combined_df

        except Exception as e:
            logger.error(f"Erreur dans {pdf_path}: {str(e)}")
            import traceback

            traceback.print_exc()
            raise ValueError(
                f"Erreur lors de l'extraction des données de {pdf_path}: {str(e)}"
            ) from e

    def copy_tableau(
        self, colonnes: List[str] | str | int | List[int] | None = None
    ) -> "TableauParser":
        """Créer un nouveau parser avec des colonnes spécifiques"""
        if colonnes is None:
            return self.__class__(self.df.copy())
        elif isinstance(colonnes, int):
            colonnes = [self.df.columns[colonnes]]
        elif isinstance(colonnes, List) and all(isinstance(x, int) for x in colonnes):
            colonnes = [self.df.columns[i] for i in colonnes]
        if isinstance(colonnes, str):
            colonnes = [colonnes]

        if len(colonnes) > self.df.shape[1]:
            logger.warning(
                f"Trop de noms de colonnes ({len(colonnes)}) pour le DataFrame ({self.df.shape[1]} colonnes)"
            )
            colonnes = colonnes[: self.df.shape[1]]

        return self.__class__(self.df[colonnes].copy())

    def apply_mask(self, mask: List[bool]):
        """Appliquer un masque booléen pour filtrer les lignes du DataFrame"""
        if not isinstance(mask, list) or not all(isinstance(m, bool) for m in mask):
            logger.error("Le masque doit être une liste de booléens")
            raise ValueError("Le masque doit être une liste de booléens")

        if len(mask) != len(self.df):
            logger.error(
                f"Le masque doit avoir la même longueur que le DataFrame ({len(self.df)} lignes)"
            )
            raise ValueError(
                f"Le masque doit avoir la même longueur que le DataFrame ({len(self.df)} lignes)"
            )

        # Calculer les statistiques de filtrage
        nb_lignes_supprimees = (~pd.Series(mask)).sum()
        nb_lignes_gardees = pd.Series(mask).sum()

        if nb_lignes_supprimees > 0:
            logger.info(
                f"🔄 Filtrage: {nb_lignes_supprimees} lignes supprimées, {nb_lignes_gardees} lignes conservées"
            )

        self.df = self.df[mask].copy().reset_index(drop=True)
        return self

    def max_nb_cols(self, max_nb_col: int):
        """Supprimer les lignes ayant max_non_empty_colonnes colonnes ou plus non vides (section écarts théoriques)"""
        if self.df.empty:
            return self

        # Masque pour les valeurs non-NaN
        mask_non_nan = self.df.notna()

        # Convertir tout en string et créer un masque pour les valeurs non vides
        df_str = self.df.astype(str)
        mask_non_empty = (df_str != "") & (df_str != "nan") & (df_str != "None")

        mask_non_vide = mask_non_nan & mask_non_empty
        nb_colonnes_par_ligne = mask_non_vide.sum(axis=1)
        mask_a_garder = (nb_colonnes_par_ligne < max_nb_col).tolist()

        self.apply_mask(mask_a_garder)
        return self

    def copy_col(self, colonne_source: str, nouvelle_colonne: str):
        """Copier une colonne existante dans une nouvelle colonne"""
        if colonne_source not in self.df.columns:
            logger.error(f"La colonne source '{colonne_source}' n'existe pas dans le DataFrame")
            raise ValueError(f"La colonne source '{colonne_source}' n'existe pas dans le DataFrame")

        self.df[nouvelle_colonne] = self.df[colonne_source]
        return self

    def apply_regex(
        self,
        colonne_source: str,
        regex: str,
        nouvelle_colonne: List[str] = None,
        drop_source: bool = False,
    ):
        """
        Extraire des données d'une colonne source en utilisant une expression régulière
        et les stocker dans une nouvelle colonne.

        Args:
            colonne_source: nom de la colonne source
            regex: expression régulière avec groupes de capture ()
            nouvelle_colonne: liste des noms pour les nouvelles colonnes

        Returns:
            self
        """
        if colonne_source not in self.df.columns:
            logger.error(f"La colonne source '{colonne_source}' n'existe pas dans le DataFrame")
            raise ValueError(f"La colonne source '{colonne_source}' n'existe pas dans le DataFrame")

        # Extraire avec regex
        extracted = self.df[colonne_source].str.extract(regex, expand=True)

        if nouvelle_colonne is None:
            nouvelle_colonne = [colonne_source]

        # Ajuster le nombre de noms de colonnes au nombre de groupes extraits
        nb_groupes = extracted.shape[1]
        if len(nouvelle_colonne) != nb_groupes:
            raise ValueError(
                f"Le nombre de noms de colonnes ({len(nouvelle_colonne)}) ne correspond pas au nombre de groupes extraits ({nb_groupes})"
            )

        # Nommer les colonnes extraites
        if nouvelle_colonne is not None:
            extracted.columns = nouvelle_colonne

        # Supprimer la colonne source et ajouter les nouvelles colonnes
        if drop_source:
            self.df = extracted.copy()
        elif colonne_source in nouvelle_colonne:
            self.df = self.df.drop(columns=[colonne_source])
            self.df = pd.concat([self.df, extracted], axis=1)
        else:
            self.df = pd.concat([self.df, extracted], axis=1)

        nb_extraites = extracted.count().sum()
        logger.info(
            f"✅ {nb_extraites} valeurs extraites dans {len(nouvelle_colonne)} colonne(s): {nouvelle_colonne}"
        )

        return self

    def filtre_regex(self, colonne: str, pattern_regex: str):
        """
        Filtrer un DataFrame en gardant seulement les lignes où une colonne matche un pattern regex.

        Args:
            colonne: nom de la colonne à valider
            pattern_regex: expression régulière de validation
        """
        logger.info(f"[DEBUG] Filtrage par pattern '{pattern_regex}' sur colonne '{colonne}'")

        mask_valide = self.df[colonne].astype(str).str.match(pattern_regex, na=False)
        logger.info(f"[DEBUG] Lignes validées: {mask_valide.sum()}/{len(self.df)}")

        self.apply_mask(mask_valide.tolist())
        return self

    def supprimer_doublons(self, colonnes_subset: List[str], keep: str = "first"):
        """
        Supprimer les doublons d'un DataFrame basés sur un subset de colonnes.

        Args:
            colonnes_subset: liste des colonnes à utiliser pour détecter les doublons
            keep: stratégie de conservation ('first', 'last', False)
        """
        logger.info("🔧 Suppression des doublons...")
        nb_lignes_avant = len(self.df)

        self.df = self.df.drop_duplicates(subset=colonnes_subset, keep=keep).reset_index(drop=True)

        nb_doublons_supprimes = nb_lignes_avant - len(self.df)
        if nb_doublons_supprimes > 0:
            logger.info(f"⚠️ {nb_doublons_supprimes}/{nb_lignes_avant} doublons supprimés")
        else:
            logger.info("✅ Aucun doublon détecté")
        return self

    def forward_fill(self, colonne: str, valeurs_vides: List[str] = None) -> "TableauParser":
        """
        Forward fill en remplaçant les valeurs vides par NaN d'abord.

        Args:
            colonne: nom de la colonne à étendre
            valeurs_vides: liste des valeurs considérées comme vides (par défaut ["", "nan", "NaN", "None"])
        """
        if valeurs_vides is None:
            valeurs_vides = ["", "nan", "NaN", "None"]

        logger.info(f"🔧 Extension du champ '{colonne}' avec forward fill...")

        # Vérifier que la colonne existe
        if colonne not in self.df.columns:
            logger.error(f"La colonne '{colonne}' n'existe pas dans le DataFrame")
            logger.error(f"Colonnes disponibles: {list(self.df.columns)}")
            raise ValueError(f"La colonne '{colonne}' n'existe pas dans le DataFrame")

        # Remplacer les valeurs vides par NaN pour que ffill fonctionne
        self.df[colonne] = self.df[colonne].astype(str)
        self.df.loc[self.df[colonne].isin(valeurs_vides), colonne] = pd.NA

        # Forward fill pour étendre
        self.df[colonne] = self.df[colonne].ffill()
        return self

    def afficher_resultats_extraction(
        self,
        colonne_identifiants: str,
        colonne_montants: str = None,
        nom_type_donnee: str = "éléments",
    ):
        """
        Afficher les résultats finaux d'une extraction avec statistiques.

        Args:
            colonne_identifiants: colonne contenant les identifiants uniques à analyser
            colonne_montants: colonne contenant les montants (optionnel)
            nom_type_donnee: nom du type de données (ex: "factures", "tantièmes", "relevés")
        """

        logger.info(f"Extraction terminée: {len(self.df)} {nom_type_donnee} valides uniques")

        if not self.df.empty:
            identifiants_uniques = self.df[colonne_identifiants].dropna()
            logger.info(f"🏷️ Identifiants trouvés: {list(identifiants_uniques)}")

            if colonne_montants and colonne_montants in self.df.columns:
                try:
                    montant_total = self.df[colonne_montants].sum()
                    logger.info(f"💰 Montant total: {montant_total:.2f}€")
                except (TypeError, ValueError):
                    logger.info("💰 Montants: non numériques ou non calculables")

            # Debug: afficher les premières lignes
            logger.info(f"📋 Premières lignes validées ({nom_type_donnee}):")
            for i, (idx, row) in enumerate(self.df.head(3).iterrows()):
                if i >= 3:  # Limite de sécurité
                    break
                ligne_info = f"  - ID: {row.get(colonne_identifiants, 'N/A')}"
                if colonne_montants and colonne_montants in self.df.columns:
                    ligne_info += f", Montant: {row.get(colonne_montants, 'N/A')}"
                logger.info(ligne_info)
        return self

    def definir_colonnes(self, noms_colonnes: List[str]):
        """Définir les noms de colonnes pour df"""
        if len(noms_colonnes) > self.df.shape[1]:
            logger.warning(
                f"Trop de noms de colonnes ({len(noms_colonnes)}) pour le DataFrame ({self.df.shape[1]} colonnes)"
            )
            noms_colonnes = noms_colonnes[: self.df.shape[1]]

        # Prendre seulement les colonnes nécessaires si le DataFrame en a plus
        if self.df.shape[1] > len(noms_colonnes):
            self.df = self.df.iloc[:, : len(noms_colonnes)]

        self.df.columns = noms_colonnes
        logger.info(f"📋 Colonnes définies: {list(self.df.columns)}")
        return self

    def remove_empty_lines(self):
        """Supprimer les lignes complètement vides"""
        nb_lignes_avant = len(self.df)
        self.df = self.df.dropna(how="all").reset_index(drop=True)
        nb_lignes_supprimees = nb_lignes_avant - len(self.df)
        if nb_lignes_supprimees > 0:
            logger.info(
                f"📊 {nb_lignes_supprimees} lignes vides supprimées, {len(self.df)} lignes restantes"
            )
        return self

    def col_to_float(self, colonne: str):
        """Convertir une colonne en float"""
        logger.info(f"🔢 Conversion de la colonne '{colonne}' en float")
        self.df[colonne] = self.df[colonne].astype(float)
        return self

    def copy_df(self) -> pd.DataFrame:
        """Retourner une copie du DataFrame interne"""
        return self.df.copy()

    def to_date(self, date_columns: List[str]):
        """
        Convertit les colonnes spécifiées en dates (format français jj/mm/aaaa)
        Gère proprement les valeurs NaT en les convertissant en None

        Args:
            date_columns: Liste des noms de colonnes à convertir en dates

        Returns:
            self pour le chaînage
        """
        for col in date_columns:
            if col in self.df.columns:
                # Convertir en datetime avec format français jj/mm/aaaa
                self.df[col] = pd.to_datetime(self.df[col], format="%d/%m/%Y", errors="coerce")
                # Remplacer explicitement les NaT par None pour éviter les erreurs de conversion
                self.df[col] = self.df[col].where(pd.notna(self.df[col]), None)
                # Forcer le type object pour que None soit bien un None Python
                self.df[col] = self.df[col].astype(object)
                logger.info(f"📅 Colonne '{col}' convertie en dates (NaT → None)")
                # Vérification post-conversion : logger les valeurs qui ne sont ni None ni datetime
                for i, val in enumerate(self.df[col].head(20)):
                    if val is not None and not isinstance(val, pd.Timestamp):
                        logger.warning(
                            f"[CHECK] Colonne '{col}' ligne {i}: valeur inattendue {val} de type {type(val)}"
                        )
        return self

    def dropna(self, subset: List[str] = None):
        """Supprimer les lignes avec des valeurs NaN dans les colonnes spécifiées"""
        if subset is None:
            self.df = self.df.dropna().reset_index(drop=True)
        else:
            self.df = self.df.dropna(subset=subset).reset_index(drop=True)
        return self

    def to_objects(self, model: Type[T]) -> List[T]:
        """
        Convertit le DataFrame en une liste d'objets du modèle spécifié.

        Args:
            model: Le modèle SQLModel à utiliser pour la conversion

        Returns:
            Liste d'objets du modèle
        """
        return create_objects_from_df(model, self.df)

    def to_objects_with_field(self, model: Type[T], field_name: str) -> Dict[str, List[T]]:
        """
        Convertit le DataFrame en objets groupés par la valeur d'un champ.

        Args:
            model: Le modèle SQLModel à utiliser pour la conversion
            field_name: Le nom du champ à utiliser pour le groupement

        Returns:
            Dictionnaire mappant les valeurs du champ vers les listes d'objets
        """
        # Créer les objets sans le champ de groupement
        df_objects = self.df.drop(columns=[field_name])
        logger.info(
            f"[DEBUG] DataFrame pour création d'objets - {len(df_objects)} lignes, colonnes: {list(df_objects.columns)}"
        )

        objects = create_objects_from_df(model, df_objects)

        # Créer le mapping en utilisant les valeurs du champ
        field_values = self.df[field_name].tolist()
        result = {}

        for i, obj in enumerate(objects):
            field_value = field_values[i]
            if field_value not in result:
                result[field_value] = []
            result[field_value].append(obj)

        return result

    @staticmethod
    def map_relations_static(
        objects_grouped: Dict[str, List],
        relation_map: Dict[str, any],
        relation_field: str,
        clean_key: bool = True,
    ) -> List:
        """
        Mappe les relations entre objets groupés et objets de référence.

        Args:
            objects_grouped: Dictionnaire {clé: [objets]} retourné par to_objects_with_field
            relation_map: Dictionnaire {clé: objet_de_référence} pour le mapping
            relation_field: Nom de l'attribut à assigner sur les objets
            clean_key: Si True, nettoie les clés avec .strip()

        Returns:
            Liste aplatie des objets avec relations assignées
        """
        result = []
        for key, objects_list in objects_grouped.items():
            clean_key_val = key.strip() if clean_key else key
            if clean_key_val in relation_map:
                for obj in objects_list:
                    setattr(obj, relation_field, relation_map[clean_key_val])
                    result.append(obj)
            else:
                logger.warning(
                    f"Clé '{clean_key_val}' non trouvée dans le mapping pour {relation_field}"
                )
        return result

    def nan_to_none(self, columns: List[str] = None):
        """
        Remplace les NaN par None dans les colonnes spécifiées d'un DataFrame.

        Args:
            df: Le DataFrame à modifier
            columns: Liste des noms de colonnes à traiter

        Returns:
            DataFrame avec NaN remplacés par None dans les colonnes spécifiées
        """
        if columns is None:
            columns = self.df.columns.tolist()
        for col in columns:
            if col in self.df.columns:
                self.df[col] = self.df[col].where(pd.notna(self.df[col]), None)
        return self
