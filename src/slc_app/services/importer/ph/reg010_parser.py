import os
import re
from typing import List, Tuple

import pandas as pd
import tabula.io as tabula
from slc_app.models.columns import SourceColFacture, SourceColPoste
from slc_app.models.db import engine
from slc_app.models.facture import Facture
from slc_app.models.poste import Poste
from sqlmodel import Session

from slc_app.services.importer.ph.base_processor import BaseProcessor


class ParserREG010(BaseProcessor):
    """Processeur spécialisé pour l'extraction des données des PDF REG010"""

    def __init__(self):
        super().__init__()

    def _extract_data_from_pdf(self, pdf_path: str) -> pd.DataFrame | None:
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
                return None

            # Combiner tous les DataFrames
            combined_df = pd.concat(dfs, ignore_index=True)
            self.log_info(
                f"📊 Données brutes extraites: {len(combined_df)} lignes, {combined_df.shape[1]} colonnes"
            )

            if combined_df.empty or combined_df.shape[1] < 7:
                self.log_error(
                    f"Format incorrect: {combined_df.shape[1]} colonnes (minimum 7 requis)"
                )
                return None

            return combined_df

        except Exception as e:
            self.log_error(f"Erreur dans {pdf_path}: {str(e)}")
            import traceback

            traceback.print_exc()
            return None

    def _process_extracted_data(
        self, combined_df: pd.DataFrame, pdf_path: str
    ) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        """Traiter les données extraites : nettoyage, filtrage et validation"""

        # Garder seulement les 7 premières colonnes
        combined_df = combined_df.iloc[:, :7]
        combined_df.columns = [
            SourceColFacture.POSTE_ID,
            SourceColFacture.NUMERO_FACTURE,
            SourceColFacture.CODE_JOURNAL,
            SourceColFacture.NUMERO_COMPTE_COMPTABLE,
            SourceColFacture.MONTANT_COMPTABLE,
            SourceColFacture.LIBELLE_ECRITURE,
            SourceColFacture.REFERENCES_PARTENAIRE_FACTURE,
        ]

        # Nettoyer les données: supprimer les lignes complètement vides
        combined_df = combined_df.dropna(how="all")
        self.log_info(f"📊 Après suppression des lignes vides: {len(combined_df)}")

        # ÉTAPE 1: Filtrer par montants valides
        factures_df = self._filter_by_valid_amounts(combined_df, pdf_path)

        if factures_df.empty:
            self.log_warning("Aucune ligne avec montant valide trouvée")
            return None, None

        # ÉTAPE 2: Déduplication
        factures_df = self._remove_duplicates(factures_df)

        # ÉTAPE 3: Extension des natures
        factures_df = self._extend_natures(factures_df)

        # ÉTAPE 4: Conversion des montants
        factures_df[SourceColFacture.MONTANT_COMPTABLE] = (
            factures_df[SourceColFacture.MONTANT_COMPTABLE].str.replace(",", ".").astype(float)
        )

        # ÉTAPE 5: Ajouter les métadonnées
        factures_df[SourceColFacture.FICHIER_SOURCE] = os.path.basename(pdf_path)
        factures_df[SourceColFacture.LIGNE_PDF] = range(1, len(factures_df) + 1)

        # ÉTAPE 6: Validation finale
        factures_df = factures_df.dropna(subset=[SourceColFacture.POSTE_ID])

        # ÉTAPE 7: Déduplication finale
        factures_df = self._final_deduplication(factures_df)

        # ÉTAPE 8: Extraire les natures uniques
        natures_uniques = (
            factures_df[[SourceColFacture.POSTE_ID]]
            .copy()
            .dropna()
            .drop_duplicates()
            .reset_index(drop=True)
        )
        natures_uniques.rename(columns={SourceColFacture.POSTE_ID: "nom"}, inplace=True)
        self.log_info(f"🏷️ {len(natures_uniques)} natures uniques identifiées.")

        # Afficher les résultats finaux
        self._display_final_results(factures_df)

        return factures_df, natures_uniques

    def _filter_by_valid_amounts(self, df: pd.DataFrame, pdf_path: str) -> pd.DataFrame:
        """Filtrer les lignes avec des montants valides"""
        self.log_info("💰 Filtrage par montants valides...")

        montant_pattern = r"^-?\d+\.\d{1,2}$"
        df[SourceColFacture.MONTANT_COMPTABLE] = (
            df[SourceColFacture.MONTANT_COMPTABLE].astype(str).str.strip()
        )

        # Log des lignes rejetées
        for idx, row in df.iterrows():
            montant = str(row[SourceColFacture.MONTANT_COMPTABLE]).strip()
            if not montant or montant == "nan" or not re.match(montant_pattern, montant):
                self.log_debug(
                    f"Ligne rejetée ({os.path.basename(pdf_path)}) - Montant invalide: '{montant}'"
                )

        # Masque pour les montants valides
        mask_montant_valide = (
            df[SourceColFacture.MONTANT_COMPTABLE].notna()
            & (df[SourceColFacture.MONTANT_COMPTABLE] != "nan")
            & (df[SourceColFacture.MONTANT_COMPTABLE] != "")
            & df[SourceColFacture.MONTANT_COMPTABLE].str.match(montant_pattern, na=False)
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

        df = df.drop_duplicates(
            subset=["numero_facture", "montant_comptable", "nature"], keep="first"
        )
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
                    f"  - Nature: {row[SourceColPoste.NOM]}, Facture: {row[SourceColFacture.NUMERO_FACTURE]}, Montant: {row[SourceColFacture.MONTANT_COMPTABLE]}"
                )

    def _save_to_database(
        self, df_factures: pd.DataFrame, df_postes: pd.DataFrame
    ) -> Tuple[List[Facture], List[Poste]]:
        """Sauvegarder les bases de répartition et tantièmes en base de données"""
        if df_factures.empty or df_postes.empty:
            raise ValueError(
                "❌ Les DataFrames factures ou postes sont vides, impossible de continuer l'import."
            )
        try:

            postes = Poste.from_df(df_postes)

            with Session(engine) as session:
                session.add_all(postes)
                session.commit()
                session.refresh(postes)

                poste_id_map = {p.code: p.id for p in postes}
                df_factures[SourceColFacture.POSTE_ID] = df_factures["code_poste"].map(poste_id_map)

                factures = Facture.from_df(df_factures)

                session.add_all(factures)
                session.commit()

                compteur_postes, compteur_bases = len(postes), len(factures)
                self.log_info(f"✅ {compteur_postes} postes sauvegardés en base")
                self.log_info(f"✅ {compteur_bases} factures sauvegardées en base")

            return factures, postes

        except Exception as e:
            raise ValueError(f"Erreur lors de la sauvegarde en base de données: {str(e)}") from e

    def process_reg010(self, pdf_path: str, controle_id: int) -> Tuple[List[Facture], List[Poste]]:
        """Traiter une liste de fichiers REG010"""

        self.log_info(f"🔄 Traitement de {os.path.basename(pdf_path)}")
        data = self._extract_data_from_pdf(pdf_path)
        if data is None:
            return [], []
        df_factures, df_postes = self._process_extracted_data(data, pdf_path)
        if df_factures is None or df_postes is None:
            self.log_warning(f"Aucune facture ou poste extrait de {os.path.basename(pdf_path)}")
            return [], []
        df_factures[SourceColFacture.FICHIER_SOURCE] = os.path.basename(pdf_path)
        df_postes[SourceColPoste.FICHIER_SOURCE] = os.path.basename(pdf_path)

        factures, postes = self._save_to_database(df_factures, df_postes)

        return factures, postes
