import os
from typing import List, Tuple

import pandas as pd
import tabula.io as tabula

from models.base_repartition import BaseRepartition
from models.columns import SourceColBaseRep, SourceColTantieme
from models.tantieme import Tantieme

from .base_processor import BaseProcessor


class Reg114Processor(BaseProcessor):
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
            self.log_info(f"📊 Données brutes extraites: {len(combined_df)} lignes, {combined_df.shape[1]} colonnes")

            if combined_df.empty or combined_df.shape[1] < 6:
                self.log_error(f"Format incorrect: {combined_df.shape[1]} colonnes (minimum 6 requis pour REG114)")
                raise ValueError(f"Format incorrect: {combined_df.shape[1]} colonnes (minimum 6 requis pour REG114)")

            # Nettoyer et structurer les données
            return combined_df

        except Exception as e:
            self.log_error(f"Erreur dans {pdf_path}: {str(e)}")
            import traceback

            traceback.print_exc()
            raise ValueError(f"Erreur lors de l'extraction des données de {pdf_path}: {str(e)}") from e

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
        colonnes_bases = ["code_base", "nom_base"]
        try:
            # Supprimer les lignes complètement vides
            df = df.dropna(how="all")
            self.log_info(f"📊 Après suppression des lignes vides: {len(df)}")

            # Supprimer les lignes avec 7 colonnes ou plus non vides (doublons théoriques)
            df_filtre = self._filtrer_par_nombre_colonnes(df)

            # Pattern pour détecter les codes de base de répartition
            pattern_base = r"([A-Z][A-Z0-9]+) - (.*)"

            # Extraire les codes de base (garde seulement le code, pas le nom)
            base_extraites = df_filtre.iloc[:, 0].astype(str).str.extract(pattern_base, expand=True)

            # Propager le code vers le bas (forward fill) jusqu'à la prochaine base
            codes_base_propages = base_extraites.iloc[0].ffill()

            # Ajouter la colonne au DataFrame
            df_avec_code = df.copy()
            df_avec_code.insert(0, "code_base_actuel", codes_base_propages)

            df_avec_code.columns = colonnes_reg114

            # Appliquer le regex pour valider les tantièmes
            tantieme_pattern = r"^-?\d+\.\d{1,2}$"
            df_avec_code = df_avec_code[df_avec_code.iloc[:, 5].astype(str).str.match(tantieme_pattern)]

            # Récuperer les bases uniques extraites
            unique_bases_extraites = base_extraites.dropna().drop_duplicates().reset_index(drop=True)
            bases_repartition = pd.DataFrame(unique_bases_extraites, columns=colonnes_bases)

            self.log_info(f"📋 Codes de base propagés sur {len(df_avec_code)} lignes")
            self.log_info(f"📊 {len(bases_repartition)} bases de répartition identifiées")

            return df_avec_code, bases_repartition

        except Exception as e:
            self.log_error(f"Erreur lors du traitement des données: {str(e)}")
            raise ValueError("❌ Erreur dans le traitement des données REG114") from e

    def _filtrer_par_nombre_colonnes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Supprimer les lignes ayant 7 colonnes ou plus non vides (section écarts théoriques)"""
        if df.empty:
            return df

        # Compter les colonnes non vides pour chaque ligne avec pandas
        # Exclure les colonnes ajoutées (fichier_source, ligne_pdf)
        colonnes_donnees = [col for col in df.columns if col not in ["fichier_source", "ligne_pdf"]]

        # Créer un masque pour les valeurs non vides (pas NaN et pas chaîne vide)
        mask_non_vide = df[colonnes_donnees].notna() & (df[colonnes_donnees].astype(str).str.strip() != "")

        # Compter les colonnes non vides par ligne
        nb_colonnes_par_ligne = mask_non_vide.sum(axis=1)

        # Garder seulement les lignes avec moins de 7 colonnes non vides
        mask_a_garder = nb_colonnes_par_ligne < 7

        nb_lignes_supprimees = (~mask_a_garder).sum()
        if nb_lignes_supprimees > 0:
            self.log_info(f"🔄 Suppression doublons : {nb_lignes_supprimees} lignes avec 7+ colonnes supprimées")

        return df[mask_a_garder].copy()

    def _save_to_database(
        self, base_df: pd.DataFrame, tantieme_df: pd.DataFrame, controle_id: int
    ) -> Tuple[List[Tantieme], List[BaseRepartition]]:
        """Sauvegarder les bases de répartition et tantièmes en base de données"""
        if base_df.empty or tantieme_df.empty:
            self.log_warning("DataFrames vides, rien à sauvegarder")
            raise ValueError("❌ DataFrames vides, rien à sauvegarder")
        try:
            from sqlmodel import Session

            from models import BaseRepartition, Tantieme, engine

            base_objects = BaseRepartition.from_df(base_df, controle_id)

            with Session(engine) as session:
                session.add_all(base_objects)
                session.commit()
                session.refresh(base_objects)

                base_id_map = {b.code: b.id for b in base_objects}
                tantieme_df[SourceColTantieme.BASE_ID] = tantieme_df["code_base"].map(base_id_map)

                tantieme_objects = Tantieme.from_df(tantieme_df)

                session.add_all(tantieme_objects)
                session.commit()
                session.refresh(tantieme_objects)

                compteur_tantiemes, compteur_bases = len(base_objects), len(tantieme_objects)
                self.log_info(f"✅ {compteur_tantiemes} bases sauvegardées en base")
                self.log_info(f"✅ {compteur_bases} tantièmes sauvegardés en base")

            return tantieme_objects, base_objects

        except Exception as e:
            raise ValueError(f"❌ Erreur lors de la sauvegarde en base de données: {str(e)}") from e

    def process_reg114(self, pdf_path: str, controle_id: int) -> Tuple[List[Tantieme], List[BaseRepartition]]:

        self.log_info(f"🔄 Traitement de {os.path.basename(pdf_path)}")
        data = self._extract_data_from_pdf(pdf_path)
        df_tantiemes, df_bases = self._process_extracted_data(data)
        df_tantiemes[SourceColTantieme.FICHIER_SOURCE] = os.path.basename(pdf_path)
        df_bases[SourceColBaseRep.CONTROLE_ID] = controle_id
        tantiemes, bases_repartition = self._save_to_database(df_tantiemes, df_bases, controle_id)
        return tantiemes, bases_repartition
