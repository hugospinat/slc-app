import os
from typing import List, Tuple

import pandas as pd
import tabula.io as tabula
from sqlmodel import Session

from slc_app.models import BaseRepartition, SourceColBaseRep, SourceColTantieme, Tantieme
from slc_app.services.importer.ph.base_processor import BaseProcessor
from slc_app.utils.file_storage import save_file_from_path


class ParserREG114(BaseProcessor):
    """Processeur spécialisé pour l'extraction des données des PDF REG114 (tantièmes)"""

    def __init__(self):
        super().__init__()

    def _extract_data_from_pdf(self, pdf_path: str) -> pd.DataFrame:
        """Extraire les données d'un PDF REG114 de manière robuste"""
        try:
            self.log_info(f"Traitement du fichier REG114: {pdf_path}")
            self.log_info(f"🔄 Extraction du PDF: {os.path.basename(pdf_path)}")

            # Extraire les tableaux du PDF avec lattice (même méthode que REG010)
            dfs = tabula.read_pdf(
                pdf_path,
                pages="all",
                lattice=True,
                pandas_options={"header": None},
            )

            if not dfs:
                self.log_warning(f"Aucun tableau trouvé dans {pdf_path}")
                raise ValueError(f"Aucun tableau trouvé dans {pdf_path}")

            # Combiner tous les DataFrames
            combined_df = pd.concat(dfs, ignore_index=True)
            self.log_info(
                f"📊 Données brutes extraites: {len(combined_df)} lignes, {combined_df.shape[1]} colonnes"
            )

            # LOG: Afficher le contenu brut extrait du PDF pour debug
            self.log_info("[DEBUG] Structure complète du DataFrame extrait:")
            self.log_info(f"[DEBUG] Colonnes: {list(combined_df.columns)}")
            self.log_info("[DEBUG] Premiers 15 lignes du DataFrame brut:")
            for i in range(min(15, len(combined_df))):
                ligne_str = " | ".join(
                    [str(val) if pd.notna(val) else "NaN" for val in combined_df.iloc[i]]
                )
                self.log_info(f"[DEBUG] Ligne {i}: {ligne_str}")

            if len(combined_df) > 15:
                self.log_info(f"[DEBUG] ... ({len(combined_df) - 15} autres lignes)")

            self.log_info("[DEBUG] Fin de l'affichage du DataFrame brut")

            if combined_df.empty or combined_df.shape[1] < 6:
                self.log_error(
                    f"Format incorrect: {combined_df.shape[1]} colonnes (minimum 6 requis pour REG114)"
                )
                raise ValueError(
                    f"Format incorrect: {combined_df.shape[1]} colonnes (minimum 6 requis pour REG114)"
                )

            # Nettoyer et structurer les données
            return combined_df

        except Exception as e:
            self.log_error(f"Erreur dans {pdf_path}: {str(e)}")
            import traceback

            traceback.print_exc()
            raise ValueError(
                f"Erreur lors de l'extraction des données de {pdf_path}: {str(e)}"
            ) from e

    def _process_extracted_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Traiter et nettoyer les données extraites du REG114 avec détection des bases de répartition"""
        # Nommer les colonnes selon le modèle de données REG114
        colonnes_reg114 = [
            "code_base",  # Colonne 0: code de base actuel (propagé)
            "numero_ug",  # Colonne 1: numéros UG
            "numero_ca",  # Colonne 2: numéro compte auxiliaire
            "debut_occupation",  # Colonne 3: date début occupation
            "fin_occupation",  # Colonne 4: date fin occupation
            "tantieme",  # Colonne 5: montant tantième
            "reliquat",  # Colonne 6: montant reliquat
        ]
        colonnes_bases = [SourceColBaseRep.CODE, SourceColBaseRep.NOM]
        try:
            self.log_info(f"[DEBUG] DataFrame initial: {df.shape}")
            self.log_info(f"[DEBUG] Colonnes: {df.columns.tolist()}")

            # Supprimer les lignes complètement vides
            df = df.dropna(how="all")
            self.log_info(f"📊 Après suppression des lignes vides: {len(df)}")

            # Supprimer les lignes avec 7 colonnes ou plus non vides (doublons théoriques)
            df_filtre = self._filtrer_par_nombre_colonnes(df)
            self.log_info(f"[DEBUG] Après filtrage: {df_filtre.shape}")

            # Pattern pour détecter les codes de base de répartition
            # IMPORTANT: ^ au début pour éviter de matcher des sous-chaînes
            pattern_base = r"^([A-Z][A-Z0-9]+) - (.*)"

            # Extraire les codes de base (garde seulement le code, pas le nom)
            self.log_info("[DEBUG] Échantillon de données colonne 0 avant extraction:")
            sample_data = df_filtre.iloc[:10, 0].astype(str).tolist()
            for i, val in enumerate(sample_data):
                self.log_info(f"[DEBUG] Ligne {i}: '{val}'")

            base_extraites = df_filtre.iloc[:, 0].astype(str).str.extract(pattern_base, expand=True)
            self.log_info(f"[DEBUG] Bases extraites: {base_extraites.shape}")
            self.log_info("[DEBUG] Échantillon base_extraites:")
            self.log_info(f"{base_extraites.head()}")

            # Propager le code vers le bas (forward fill) jusqu'à la prochaine base
            # On utilise la première colonne (code) seulement
            codes_base_propages = base_extraites.iloc[:, 0].ffill()
            self.log_info(f"[DEBUG] Codes propagés: {codes_base_propages.count()} non-null")

            # Ajouter la colonne au DataFrame
            df_avec_code = df.copy()
            df_avec_code.insert(0, "code_base_actuel", codes_base_propages)
            self.log_info(f"[DEBUG] DataFrame avec codes: {df_avec_code.shape}")

            # Nous devons maintenant prendre seulement les colonnes nécessaires (7 premières)
            # car le DataFrame original peut avoir plus de colonnes que prévu
            nb_colonnes_attendues = len(colonnes_reg114)
            if df_avec_code.shape[1] > nb_colonnes_attendues:
                self.log_info(
                    f"[DEBUG] Réduction de {df_avec_code.shape[1]} à {nb_colonnes_attendues} colonnes"
                )
                df_avec_code = df_avec_code.iloc[:, :nb_colonnes_attendues]

            df_avec_code.columns = colonnes_reg114
            self.log_info(f"[DEBUG] Colonnes finales: {df_avec_code.columns.tolist()}")

            # Appliquer le regex pour valider les tantièmes
            # Utiliser le nom de colonne plutôt que l'index pour éviter les erreurs
            tantieme_pattern = r"^-?\d+\.\d{1,2}$"
            tantieme_col = SourceColTantieme.TANTIEME.value
            self.log_info(f"[DEBUG] Validation tantièmes sur colonne: {tantieme_col}")

            mask_tantieme = df_avec_code[tantieme_col].astype(str).str.match(tantieme_pattern)
            df_avec_code = df_avec_code[mask_tantieme]
            self.log_info(f"[DEBUG] Après validation tantièmes: {len(df_avec_code)}")

            # Récuperer les bases uniques extraites
            unique_bases_extraites = (
                base_extraites.dropna().drop_duplicates().reset_index(drop=True)
            )
            self.log_info(
                f"[DEBUG] Bases uniques avant création DataFrame: {unique_bases_extraites.shape}"
            )

            # Vérifier que nous avons des bases valides
            if unique_bases_extraites.empty:
                self.log_warning("Aucune base de répartition trouvée dans le document")
                # Créer un DataFrame vide avec les bonnes colonnes
                bases_repartition = pd.DataFrame(columns=colonnes_bases)
            else:
                self.log_info(f"[DEBUG] Premières bases trouvées: {unique_bases_extraites.head()}")
                bases_repartition = pd.DataFrame(unique_bases_extraites)
                bases_repartition.columns = colonnes_bases
                # Vérifier s'il y a des valeurs nulles
                nulls_in_bases = bases_repartition.isnull().sum()
                if nulls_in_bases.any():
                    self.log_warning(f"[DEBUG] Valeurs nulles dans les bases: {nulls_in_bases}")

            self.log_info(f"📋 Codes de base propagés sur {len(df_avec_code)} lignes")
            self.log_info(f"📊 {len(bases_repartition)} bases de répartition identifiées")

            return df_avec_code, bases_repartition

        except Exception as e:
            self.log_error(f"Erreur lors du traitement des données: {str(e)}")
            import traceback

            traceback.print_exc()
            # Re-raise l'erreur originale au lieu de la masquer
            raise e

    def _filtrer_par_nombre_colonnes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Supprimer les lignes ayant 7 colonnes ou plus non vides (section écarts théoriques)"""
        if df.empty:
            return df

        # Compter les colonnes non vides pour chaque ligne avec pandas
        # Exclure les colonnes ajoutées (fichier_source, ligne_pdf)
        colonnes_donnees = [col for col in df.columns if col not in ["fichier_source", "ligne_pdf"]]

        # Approche entièrement vectorisée sans boucles
        df_subset = df[colonnes_donnees]

        # Masque pour les valeurs non-NaN
        mask_non_nan = df_subset.notna()

        # Convertir tout en string et créer un masque pour les valeurs non vides
        df_str = df_subset.astype(str)
        mask_non_empty = (df_str != "") & (df_str != "nan") & (df_str != "None")

        # Combiner les deux masques
        mask_non_vide = mask_non_nan & mask_non_empty

        # Compter les colonnes non vides par ligne
        nb_colonnes_par_ligne = mask_non_vide.sum(axis=1)

        # Garder seulement les lignes avec moins de 7 colonnes non vides
        mask_a_garder = nb_colonnes_par_ligne < 7

        nb_lignes_supprimees = (~mask_a_garder).sum()
        if nb_lignes_supprimees > 0:
            self.log_info(
                f"🔄 Suppression doublons : {nb_lignes_supprimees} lignes avec 7+ colonnes supprimées"
            )

        return df[mask_a_garder].copy()

    def _save_to_database(
        self, tantieme_df: pd.DataFrame, base_df: pd.DataFrame, controle_id: int, session: Session
    ) -> Tuple[List[Tantieme], List[BaseRepartition]]:
        """Sauvegarder les bases de répartition et tantièmes en base de données"""
        if base_df.empty or tantieme_df.empty:
            self.log_warning("DataFrames vides, rien à sauvegarder")
            raise ValueError("❌ DataFrames vides, rien à sauvegarder")

        # Vérifier qu'il n'y a pas de valeurs nulles dans les colonnes critiques
        if base_df[SourceColBaseRep.CODE].isnull().any():
            self.log_error("Des codes de base sont null, impossible de sauvegarder")
            self.log_info(
                f"[DEBUG] Base_df avec nulls: {base_df[base_df[SourceColBaseRep.CODE].isnull()]}"
            )
            raise ValueError("❌ Des codes de base sont null, impossible de sauvegarder")

        try:
            base_objects = BaseRepartition.from_df(base_df, controle_id)

            # ARCHITECTURE CENTRALISÉE: Utiliser la session passée en paramètre
            session.add_all(base_objects)
            session.commit()
            for b in base_objects:
                session.refresh(b)

            base_id_map = {b.code: b.id for b in base_objects}
            tantieme_df[SourceColTantieme.BASE_ID] = tantieme_df["code_base"].map(base_id_map)

            tantieme_objects = Tantieme.from_df(tantieme_df)

            session.add_all(tantieme_objects)
            session.commit()
            for t in tantieme_objects:
                session.refresh(t)

            compteur_tantiemes, compteur_bases = len(base_objects), len(tantieme_objects)
            self.log_info(f"✅ {compteur_tantiemes} bases sauvegardées en base")
            self.log_info(f"✅ {compteur_bases} tantièmes sauvegardés en base")

            return tantieme_objects, base_objects

        except Exception as e:
            raise ValueError(f"❌ Erreur lors de la sauvegarde en base de données: {str(e)}") from e

    def process_reg114(
        self, pdf_path: str, controle_id: int, savePath: str, session: Session
    ) -> Tuple[List[Tantieme], List[BaseRepartition]]:

        self.log_info(f"🔄 Traitement de {os.path.basename(pdf_path)}")
        data = self._extract_data_from_pdf(pdf_path)
        save_file_from_path(pdf_path, savePath, "reg114.pdf")
        df_tantiemes, df_bases = self._process_extracted_data(data)
        df_bases[SourceColBaseRep.CONTROLE_ID] = controle_id
        tantiemes, bases_repartition = self._save_to_database(
            df_tantiemes, df_bases, controle_id, session
        )
        return tantiemes, bases_repartition
