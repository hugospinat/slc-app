import os
import re
from typing import List

import pandas as pd
import tabula.io as tabula

from .base_processor import BaseProcessor


class Reg114Processor(BaseProcessor):
    """Processeur spécialisé pour l'extraction des données des PDF REG114 (tantièmes)"""

    def __init__(self):
        super().__init__()

    def extract_data_from_pdf(self, pdf_path: str) -> pd.DataFrame:
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
                return pd.DataFrame()

            # Combiner tous les DataFrames
            combined_df = pd.concat(dfs, ignore_index=True)
            self.log_info(f"📊 Données brutes extraites: {len(combined_df)} lignes, {combined_df.shape[1]} colonnes")

            if combined_df.empty or combined_df.shape[1] < 6:
                self.log_error(f"Format incorrect: {combined_df.shape[1]} colonnes (minimum 6 requis pour REG114)")
                return pd.DataFrame()

            # Nettoyer et structurer les données
            return self._process_extracted_data(combined_df, pdf_path)

        except Exception as e:
            self.log_error(f"Erreur dans {pdf_path}: {str(e)}")
            import traceback

            traceback.print_exc()
            return pd.DataFrame()

    def _process_extracted_data(self, df: pd.DataFrame, pdf_path: str) -> pd.DataFrame:
        """Traiter et nettoyer les données extraites du REG114 avec détection des bases de répartition"""
        try:
            # Ajouter les métadonnées de base
            df["fichier_source"] = os.path.basename(pdf_path)
            df["ligne_pdf"] = range(1, len(df) + 1)

            # Supprimer les lignes complètement vides
            df = df.dropna(how="all")
            self.log_info(f"📊 Après suppression des lignes vides: {len(df)}")

            # NOUVEAU : Supprimer les lignes avec 7 colonnes ou plus non vides (doublons théoriques)
            df_filtre = self._filtrer_par_nombre_colonnes(df)

            # Détecter et traiter les bases de répartition
            df_with_bases = self._detect_and_group_by_bases(df_filtre)

            return df_with_bases

        except Exception as e:
            self.log_error(f"Erreur lors du traitement des données: {str(e)}")
            return pd.DataFrame()

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

    def _detect_and_group_by_bases(self, df: pd.DataFrame) -> pd.DataFrame:
        """Détecter les lignes de base de répartition et grouper les tantièmes"""

        try:
            base_repartition_rows = []
            tantieme_rows = []
            current_base = None
            codes_bases_vus = set()  # NOUVEAU : Tracker les codes de base déjà vus

            # Regex pour détecter les bases de répartition: code commençant par une majuscule suivi de lettres/chiffres + " - "
            base_pattern = re.compile(r"([A-Z][A-Z0-9]+) - (.+)")

            for idx, row in df.iterrows():
                # Vérifier si c'est une ligne de base de répartition
                first_col = str(row.iloc[0]) if not pd.isna(row.iloc[0]) else ""

                match = base_pattern.match(first_col.strip())
                if match:
                    # C'est une base de répartition
                    code_base = match.group(1)
                    nom_base = match.group(2).strip()

                    # NOUVEAU : Vérifier si le code de base existe déjà
                    if code_base in codes_bases_vus:
                        self.log_info(f"🔄 Code de base dupliqué ignoré: {code_base} (ligne {row['ligne_pdf']})")
                        # On ignore cette ligne et toutes les suivantes car on est dans la section doublons
                        break

                    # Ajouter le code à la liste des codes vus
                    codes_bases_vus.add(code_base)

                    current_base = {
                        "code": code_base,
                        "nom": nom_base,
                        "cdc_concerne": None,  # À déterminer si nécessaire
                        "fichier_source": row["fichier_source"],
                        "ligne_pdf": row["ligne_pdf"],
                        "type": "base_repartition",
                    }

                    base_repartition_rows.append(current_base)
                    self.log_info(f"📋 Base de répartition détectée: {code_base} - {nom_base}")

                else:
                    # C'est une ligne de tantième
                    if current_base is not None:
                        # Vérifier si la ligne a suffisamment de colonnes pour être un tantième valide
                        if self._is_valid_tantieme_row(row):
                            tantieme_data = self._extract_tantieme_data(row, current_base)
                            if tantieme_data:  # Vérifier que le dictionnaire n'est pas vide
                                tantieme_rows.append(tantieme_data)

            self.log_info(f"✅ {len(base_repartition_rows)} bases de répartition détectées")
            self.log_info(f"✅ {len(tantieme_rows)} tantièmes extraits")

            # Créer le DataFrame final avec les deux types de données
            all_rows = base_repartition_rows + tantieme_rows
            return pd.DataFrame(all_rows)

        except Exception as e:
            self.log_error(f"Erreur lors de la détection des bases: {str(e)}")
            return df

    def _is_valid_tantieme_row(self, row) -> bool:
        """Vérifier si une ligne est un tantième valide"""

        try:
            # Au minimum : numéro UG (première colonne) non vide
            numero_ug = str(row.iloc[0]) if not pd.isna(row.iloc[0]) else ""
            if numero_ug.strip() == "" or " - " in numero_ug:
                return False

            return True
        except Exception:
            return False

    def _extract_tantieme_data(self, row, current_base):
        """Extraire les données d'un tantième avec validation du montant"""
        try:
            # Colonnes attendues : UG, CA, début, fin, tantième, reliquat
            tantieme_data = {
                "type": "tantieme",
                "base_code": current_base["code"],
                "base_nom": current_base["nom"],
                "numero_ug": str(row.iloc[0]) if not pd.isna(row.iloc[0]) else "",
                "numero_ca": str(row.iloc[1]) if len(row) > 1 and not pd.isna(row.iloc[1]) else "",
                "debut_occupation": row.iloc[2] if len(row) > 2 else None,
                "fin_occupation": row.iloc[3] if len(row) > 3 else None,
                "tantieme": row.iloc[4] if len(row) > 4 else None,
                "reliquat": row.iloc[5] if len(row) > 5 else None,
                "fichier_source": row["fichier_source"],
                "ligne_pdf": row["ligne_pdf"],
            }

            # Vérifier que le numéro UG n'est pas vide
            if tantieme_data["numero_ug"].strip() == "":
                return {}

            # Appliquer le même filtre de montant que REG010 sur la colonne tantième
            if not self._is_valid_tantieme_amount(tantieme_data["tantieme"]):
                self.log_debug(f"Ligne tantième rejetée - Montant invalide: '{tantieme_data['tantieme']}'")
                return {}

            return tantieme_data

        except Exception as e:
            self.log_warning(f"Erreur lors de l'extraction tantième ligne {row.get('ligne_pdf', '?')}: {str(e)}")
            return {}

    def _is_valid_tantieme_amount(self, montant) -> bool:
        """Valider le montant d'un tantième avec le même pattern que REG010"""
        import re

        if montant is None or pd.isna(montant):
            return False

        montant_str = str(montant).strip()
        if montant_str == "" or montant_str == "nan":
            return False

        # Même pattern que REG010 : montant décimal avec 1 ou 2 chiffres après la virgule
        montant_pattern = r"^-?\d+(\.\d{1,2})?$"
        return bool(re.match(montant_pattern, montant_str))

    def _convert_numeric_fields(self, df: pd.DataFrame):
        """Convertir les champs numériques et dates"""
        try:
            # Conversion des champs numériques
            for col in ["tantieme", "reliquat"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Conversion des dates (si format reconnu)
            for col in ["debut_occupation", "fin_occupation"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

        except Exception as e:
            self.log_warning(f"Erreur lors de la conversion des types: {str(e)}")

    def save_to_database(self, df: pd.DataFrame, controle_id: int) -> int:
        """Sauvegarder les bases de répartition et tantièmes en base de données"""
        if df.empty:
            self.log_warning("DataFrame vide, rien à sauvegarder")
            return 0

        try:
            from sqlmodel import Session

            from models import BaseRepartition, Tantieme, engine

            saved_count = 0
            base_id_map = {}  # Mapping code_base -> base_id

            with Session(engine) as session:
                # D'abord sauvegarder les bases de répartition
                for _, row in df.iterrows():
                    if row.get("type") == "base_repartition":
                        base_repartition = BaseRepartition(
                            controle_id=controle_id,
                            code=row["code"],
                            nom=row["nom"],
                            cdc_concerne=row.get("cdc_concerne"),
                            fichier_source=row["fichier_source"],
                            ligne_pdf=int(row["ligne_pdf"]),
                        )
                        session.add(base_repartition)
                        session.flush()  # Pour obtenir l'ID
                        base_id_map[row["code"]] = base_repartition.id
                        saved_count += 1

                # Ensuite sauvegarder les tantièmes
                for _, row in df.iterrows():
                    if row.get("type") == "tantieme":
                        base_id = base_id_map.get(row["base_code"])
                        if base_id:
                            tantieme = Tantieme(
                                base_repartition_id=base_id,
                                numero_ug=str(row["numero_ug"]),
                                numero_ca=str(row["numero_ca"]),
                                debut_occupation=row.get("debut_occupation"),
                                fin_occupation=row.get("fin_occupation"),
                                tantieme=row.get("tantieme"),
                                reliquat=row.get("reliquat"),
                                fichier_source=row["fichier_source"],
                                ligne_pdf=int(row["ligne_pdf"]),
                            )
                            session.add(tantieme)
                            saved_count += 1

                session.commit()
                self.log_info(f"✅ {saved_count} éléments sauvegardés en base (bases + tantièmes)")

            return saved_count

        except Exception as e:
            self.log_error(f"Erreur lors de la sauvegarde: {str(e)}")
            return 0

    def save_combined_to_csv(self, dataframes: List[pd.DataFrame], output_filename: str = "reg114.csv") -> str:
        """Sauvegarder le DataFrame fusionné en CSV"""
        try:
            if not dataframes:
                self.log_warning("Aucun DataFrame à fusionner")
                return ""

            # Fusionner tous les DataFrames
            combined_df = pd.concat(dataframes, ignore_index=True)

            # Sauvegarder en CSV
            combined_df.to_csv(output_filename, index=False, encoding="utf-8")

            self.log_info(f"📁 DataFrame REG114 fusionné sauvegardé: {output_filename}")
            self.log_info(f"📊 Total lignes sauvegardées: {len(combined_df)}")

            return output_filename

        except Exception as e:
            self.log_error(f"Erreur lors de la sauvegarde CSV: {str(e)}")
            return ""

    def process_reg114_files(self, pdf_files: List[str]) -> tuple[List[pd.DataFrame], List[str]]:
        """Traiter une liste de fichiers REG114"""
        dataframes = []
        processed_files = []

        for pdf_path in pdf_files:
            self.log_info(f"🔄 Traitement de {os.path.basename(pdf_path)}")
            df = self.extract_data_from_pdf(pdf_path)

            if not df.empty:
                dataframes.append(df)
                processed_files.append(os.path.basename(pdf_path))

        return dataframes, processed_files
