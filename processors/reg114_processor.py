import os
from typing import Dict, List

import pandas as pd
import tabula.io as tabula
from sqlmodel import select

from .base_processor import BaseProcessor


class Reg114Processor(BaseProcessor):
    """Processeur spécialisé pour l'extraction des données des PDF REG114 (tantièmes)"""

    def __init__(self):
        super().__init__()

    def extract_data_from_pdf(self, pdf_path: str) -> Dict[str, pd.DataFrame]:
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
                return {}

            # Combiner tous les DataFrames
            combined_df = pd.concat(dfs, ignore_index=True)
            self.log_info(f"📊 Données brutes extraites: {len(combined_df)} lignes, {combined_df.shape[1]} colonnes")

            if combined_df.empty or combined_df.shape[1] < 6:
                self.log_error(f"Format incorrect: {combined_df.shape[1]} colonnes (minimum 6 requis pour REG114)")
                return {}

            # Nettoyer et structurer les données
            return self._process_extracted_data(combined_df)

        except Exception as e:
            self.log_error(f"Erreur dans {pdf_path}: {str(e)}")
            import traceback

            traceback.print_exc()
            return {}

    def _process_extracted_data(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
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

            return {"df_avec_code": df_avec_code, "bases_repartition": bases_repartition}

        except Exception as e:
            self.log_error(f"Erreur lors du traitement des données: {str(e)}")
            return {}

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

    def save_to_database(self, dfs: Dict[str, pd.DataFrame], controle_id: int) -> tuple[int, int]:
        """Sauvegarder les bases de répartition et tantièmes en base de données"""
        if not dfs:
            self.log_warning("DataFrames vides, rien à sauvegarder")
            return (0, 0)

        df_tantiemes = dfs.get("tantiemes", pd.DataFrame())
        df_bases = dfs.get("bases", pd.DataFrame())

        try:
            from sqlmodel import Session

            from models import BaseRepartition, Tantieme, engine

            compteur_bases = 0
            compteur_tantiemes = 0

            with Session(engine) as session:

                # 1. Sauvegarder les bases de répartition
                if not df_bases.empty:
                    self.log_info(f"💾 Sauvegarde de {len(df_bases)} bases de répartition")

                    for _, ligne_base in df_bases.iterrows():
                        nouvelle_base = BaseRepartition(
                            controle_id=controle_id,
                            code=str(ligne_base["code_base"]),
                            nom=str(ligne_base["nom_base"]),
                        )
                        session.add(nouvelle_base)
                        compteur_bases += 1

                # Valider les bases pour récupérer les IDs
                session.commit()

                # 2. Sauvegarder les tantièmes
                if not df_tantiemes.empty:
                    self.log_info(f"💾 Sauvegarde de {len(df_tantiemes)} tantièmes")

                    # Récupérer les bases créées pour l'association (SQLModel style)
                    bases_creees = session.exec(
                        select(BaseRepartition).where(BaseRepartition.controle_id == controle_id)
                    ).all()

                    # Créer un dictionnaire code -> id pour l'association
                    mapping_bases = {base.code: base.id for base in bases_creees}

                    for _, ligne_tantieme in df_tantiemes.iterrows():
                        code_base = str(ligne_tantieme.get("code_base_actuel", ""))
                        base_id = mapping_bases.get(code_base)

                        if base_id:
                            # Extraire le numéro UG depuis description_ligne
                            nouveau_tantieme = Tantieme(
                                base_repartition_id=base_id,
                                numero_ug=ligne_tantieme.get("numero_ug", 0),
                                numero_ca=str(ligne_tantieme.get("numero_ca", "")),
                                debut_occupation=ligne_tantieme.get("debut_occupation"),
                                fin_occupation=ligne_tantieme.get("fin_occupation"),
                                tantieme=float(ligne_tantieme.get("tantieme", 0)),
                                reliquat=float(ligne_tantieme.get("reliquat", 0)),
                            )
                            session.add(nouveau_tantieme)
                            compteur_tantiemes += 1

                session.commit()

                self.log_success(f"✅ Sauvegarde terminée: {compteur_bases} bases, {compteur_tantiemes} tantièmes")

            return (compteur_tantiemes, compteur_bases)

        except Exception as e:
            self.log_error(f"Erreur lors de la sauvegarde: {str(e)}")
            return (0, 0)

    def process_reg114_files(self, pdf_files: List[str]) -> tuple[dict[str, pd.DataFrame], List[str]]:
        """Traiter une liste de fichiers REG114"""
        dataframes_tantiemes = []
        dataframes_bases = []
        processed_files = []

        for pdf_path in pdf_files:
            self.log_info(f"🔄 Traitement de {os.path.basename(pdf_path)}")
            dict_dfs = self.extract_data_from_pdf(pdf_path)

            if not dict_dfs["tantiemes"].empty and not dict_dfs["bases"].empty:
                dataframes_tantiemes.append(dict_dfs["tantiemes"])
                dataframes_bases.append(dict_dfs["bases"])
                processed_files.append(os.path.basename(pdf_path))

        df_tantiemes_final = (
            pd.concat(dataframes_tantiemes, ignore_index=True) if dataframes_tantiemes else pd.DataFrame()
        )
        df_bases_final = pd.concat(dataframes_bases, ignore_index=True) if dataframes_bases else pd.DataFrame()
        df_dictionary = {
            "tantiemes": df_tantiemes_final,
            "bases": df_bases_final,
        }
        return df_dictionary, processed_files
