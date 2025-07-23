import os
import re
from typing import List

import pandas as pd
import tabula.io as tabula

from .base_processor import BaseProcessor


class Reg010Processor(BaseProcessor):
    """Processeur spécialisé pour l'extraction des données des PDF REG010"""

    def __init__(self):
        super().__init__()

    def extract_data_from_pdf(self, pdf_path: str) -> pd.DataFrame:
        """Extraire les données d'un PDF REG010 de manière robuste"""
        try:
            self.log_info(f"Traitement du fichier: {pdf_path}")
            self.log_info(f"🔄 Extraction du PDF: {os.path.basename(pdf_path)}")

            # Extraire les tableaux du PDF avec lattice
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

            if combined_df.empty or combined_df.shape[1] < 7:
                self.log_error(f"Format incorrect: {combined_df.shape[1]} colonnes (minimum 7 requis)")
                return pd.DataFrame()

            # Nettoyer et structurer les données
            return self._process_extracted_data(combined_df, pdf_path)

        except Exception as e:
            self.log_error(f"Erreur dans {pdf_path}: {str(e)}")
            import traceback

            traceback.print_exc()
            return pd.DataFrame()

    def _process_extracted_data(self, combined_df: pd.DataFrame, pdf_path: str) -> pd.DataFrame:
        """Traiter les données extraites : nettoyage, filtrage et validation"""

        # Garder seulement les 7 premières colonnes
        combined_df = combined_df.iloc[:, :7]
        combined_df.columns = [
            "nature",
            "numero_facture",
            "code_journal",
            "numero_compte_comptable",
            "montant_comptable",
            "libelle_ecriture",
            "references_partenaire_facture",
        ]

        # Nettoyer les données: supprimer les lignes complètement vides
        combined_df = combined_df.dropna(how="all")
        self.log_info(f"📊 Après suppression des lignes vides: {len(combined_df)}")

        # ÉTAPE 1: Filtrer par montants valides
        filtered_df = self._filter_by_valid_amounts(combined_df, pdf_path)

        if filtered_df.empty:
            self.log_warning("Aucune ligne avec montant valide trouvée")
            return pd.DataFrame()

        # ÉTAPE 2: Déduplication
        filtered_df = self._remove_duplicates(filtered_df)

        # ÉTAPE 3: Extension des natures
        filtered_df = self._extend_natures(filtered_df)

        # ÉTAPE 4: Conversion des montants
        filtered_df["montant_comptable"] = filtered_df["montant_comptable"].str.replace(",", ".").astype(float)

        # ÉTAPE 5: Ajouter les métadonnées
        filtered_df["fichier_source"] = os.path.basename(pdf_path)
        filtered_df["ligne_pdf"] = range(1, len(filtered_df) + 1)

        # ÉTAPE 6: Validation finale
        filtered_df = filtered_df.dropna(subset=["nature"])

        # ÉTAPE 7: Déduplication finale
        filtered_df = self._final_deduplication(filtered_df)

        # Afficher les résultats finaux
        self._display_final_results(filtered_df)

        return filtered_df

    def _filter_by_valid_amounts(self, df: pd.DataFrame, pdf_path: str) -> pd.DataFrame:
        """Filtrer les lignes avec des montants valides"""
        self.log_info("💰 Filtrage par montants valides...")

        montant_pattern = r"^-?\d+\.\d{1,2}$"
        df["montant_comptable"] = df["montant_comptable"].astype(str).str.strip()

        # Log des lignes rejetées
        for idx, row in df.iterrows():
            montant = str(row["montant_comptable"]).strip()
            if not montant or montant == "nan" or not re.match(montant_pattern, montant):
                self.log_debug(f"Ligne rejetée ({os.path.basename(pdf_path)}) - Montant invalide: '{montant}'")

        # Masque pour les montants valides
        mask_montant_valide = (
            df["montant_comptable"].notna()
            & (df["montant_comptable"] != "nan")
            & (df["montant_comptable"] != "")
            & df["montant_comptable"].str.match(montant_pattern, na=False)
        )

        self.log_info(f"📊 Lignes avant filtrage montants: {len(df)}")
        self.log_info(f"📊 Lignes avec montants valides: {mask_montant_valide.sum()}")

        filtered_df = df[mask_montant_valide].copy()
        self.log_info(f"📊 Lignes après filtrage montants: {len(filtered_df)}")

        return filtered_df

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Supprimer les doublons basés sur numero_facture et montant_comptable"""
        self.log_info("🔧 Suppression des doublons...")
        nb_lignes_avant = len(df)

        df = df.drop_duplicates(subset=["numero_facture", "montant_comptable"], keep="first")

        nb_doublons_supprimes = nb_lignes_avant - len(df)
        if nb_doublons_supprimes > 0:
            self.log_info(f"⚠️ {nb_doublons_supprimes} doublons supprimés")
        else:
            self.log_info("✅ Aucun doublon détecté")

        return df

    def _extend_natures(self, df: pd.DataFrame) -> pd.DataFrame:
        """Étendre le champ nature avec forward fill"""
        self.log_info("🔧 Extension du champ nature...")

        # Remplacer les valeurs vides par NaN pour que ffill fonctionne
        df["nature"] = df["nature"].astype(str)
        df.loc[df["nature"].isin(["", "nan", "NaN", "None"]), "nature"] = pd.NA

        # Forward fill pour étendre les natures
        df["nature"] = df["nature"].ffill()

        return df

    def _final_deduplication(self, df: pd.DataFrame) -> pd.DataFrame:
        """Déduplication finale après extension des natures"""
        nb_lignes_avant = len(df)

        df = df.drop_duplicates(subset=["numero_facture", "montant_comptable", "nature"], keep="first")
        df = df.reset_index(drop=True)

        # Recalculer ligne_pdf après déduplication
        df["ligne_pdf"] = range(1, len(df) + 1)

        nb_doublons_finaux = nb_lignes_avant - len(df)
        if nb_doublons_finaux > 0:
            self.log_info(f"⚠️ {nb_doublons_finaux} doublons supprimés après extension des natures")

        return df

    def _display_final_results(self, df: pd.DataFrame):
        """Afficher les résultats finaux de l'extraction"""
        self.log_success(f"Extraction terminée: {len(df)} factures valides uniques")

        if not df.empty:
            natures_trouvees = df["nature"].dropna().unique()
            self.log_info(f"🏷️ Natures identifiées: {list(natures_trouvees)}")

            montant_total = df["montant_comptable"].sum()
            self.log_info(f"💰 Montant total: {montant_total:.2f}€")

            # Debug: afficher les premières lignes
            self.log_info("📋 Premières lignes validées:")
            for i, row in df.head(3).iterrows():
                self.log_info(
                    f"  - Nature: {row['nature']}, Facture: {row['numero_facture']}, Montant: {row['montant_comptable']}"
                )

    def process_reg010_files(self, pdf_files: List[str]) -> tuple[List[pd.DataFrame], List[str]]:
        """Traiter une liste de fichiers REG010"""
        dataframes = []
        processed_files = []

        for pdf_path in pdf_files:
            self.log_info(f"🔄 Traitement de {os.path.basename(pdf_path)}")
            df = self.extract_data_from_pdf(pdf_path)

            if not df.empty:
                df["fichier_source"] = os.path.basename(pdf_path)
                dataframes.append(df)
                processed_files.append(os.path.basename(pdf_path))

        return dataframes, processed_files
