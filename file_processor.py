import os
import re
import shutil
import tempfile
import zipfile
from typing import List, Tuple

import pandas as pd
import tabula.io as tabula


class FileProcessor:
    """Classe pour traiter les fichiers ZIP et extraire les données des PDF"""

    def __init__(self, upload_dir: str = "uploads"):
        """Initialiser le processeur de fichiers"""
        self.upload_dir = upload_dir  # Gardé pour compatibilité mais non utilisé
        # Nous utilisons maintenant tempfile.mkdtemp() qui gère automatiquement les répertoires

    def extract_zip(self, zip_path: str) -> str:
        """Extraire un fichier ZIP et retourner le répertoire d'extraction"""
        # Créer un répertoire temporaire unique
        extract_dir = tempfile.mkdtemp(prefix="charge_extract_")

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
        except Exception as e:
            print(f"Erreur lors de l'extraction du ZIP: {e}")
            # Nettoyer en cas d'erreur
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir, ignore_errors=True)
            raise

        return extract_dir

    def find_reg010_pdfs(self, directory: str) -> List[str]:
        """Trouver tous les fichiers PDF contenant 'REG010' dans le nom"""
        pdf_files = []

        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(".pdf") and "REG010" in file:
                    pdf_files.append(os.path.join(root, file))

        return pdf_files

    def is_valid_montant(self, value: str) -> bool:
        """Vérifier si une valeur est un montant valide (nombre avec point pour décimales)"""
        if pd.isna(value) or value == "":
            return False

        # Convertir en string si ce n'est pas déjà le cas
        value_str = str(value).strip()

        # Pattern pour un nombre décimal (peut être négatif)
        pattern = r"^-?\d+(\.\d+)?$"
        return bool(re.match(pattern, value_str))

    def extract_data_from_pdf(self, pdf_path: str) -> pd.DataFrame:
        """Extraire les données d'un PDF en utilisant tabula avec l'option lattice"""
        try:
            # Utiliser tabula pour extraire les données avec l'option lattice (équivalent d'axis)
            # Ajouter des options pour gérer les problèmes d'encodage
            dfs = tabula.read_pdf(
                pdf_path,
                pages="all",
                lattice=True,
                pandas_options={"header": None},
                encoding="latin-1",  # Encodage alternatif pour les caractères spéciaux
                java_options=["-Dfile.encoding=UTF-8"],  # Options Java pour l'encodage
            )

            if not dfs:
                return pd.DataFrame()

            # Combiner tous les DataFrames si plusieurs pages
            combined_df = pd.concat(dfs, ignore_index=True)

            # Vérifier qu'on a au moins 7 colonnes
            if combined_df.shape[1] < 7:
                print(f"Attention: PDF {pdf_path} n'a que {combined_df.shape[1]} colonnes (7 attendues)")
                return pd.DataFrame()

            # Prendre seulement les 7 premières colonnes si plus
            if combined_df.shape[1] > 7:
                combined_df = combined_df.iloc[:, :7]

            # Nommer les colonnes selon le schéma fourni
            combined_df.columns = [
                "nature",
                "numero_facture",
                "code_journal",
                "numero_compte_comptable",
                "montant_comptable",
                "libelle_ecriture",
                "references_partenaire_facture",
            ]

            # Nettoyer les données textuelles des caractères problématiques
            for col in combined_df.columns:
                if col != "montant_comptable":
                    combined_df[col] = (
                        combined_df[col]
                        .astype(str)
                        .apply(lambda x: x.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore"))
                    )

            # Filtrer les lignes où le 5ème champ (montant_comptable) est un nombre valide
            filtered_df = combined_df[combined_df["montant_comptable"].apply(self.is_valid_montant)].copy()

            # Convertir le montant en float
            if not filtered_df.empty:
                filtered_df["montant_comptable"] = filtered_df["montant_comptable"].astype(float)

                # Ajouter des métadonnées
                filtered_df["fichier_source"] = os.path.basename(pdf_path)
                filtered_df["ligne_pdf"] = range(1, len(filtered_df) + 1)

            return filtered_df

        except UnicodeDecodeError as e:
            print(f"Erreur d'encodage lors de l'extraction du PDF {pdf_path}: {e}")
            # Essayer avec un autre encodage
            try:
                dfs = tabula.read_pdf(
                    pdf_path,
                    pages="all",
                    lattice=True,
                    pandas_options={"header": None},
                    encoding="cp1252",  # Encodage Windows
                )
                if dfs:
                    combined_df = pd.concat(dfs, ignore_index=True)
                    if combined_df.shape[1] >= 7:
                        # Traitement similaire mais simplifié
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
                        return combined_df
            except Exception as e2:
                print(f"Échec avec encodage alternatif: {e2}")
            return pd.DataFrame()
        except Exception as e:
            print(f"Erreur lors de l'extraction du PDF {pdf_path}: {e}")
            return pd.DataFrame()

    def process_zip_file(self, zip_path: str) -> Tuple[List[pd.DataFrame], List[str]]:
        """Traiter un fichier ZIP complet"""
        extract_dir = None
        try:
            # Extraire le ZIP dans un répertoire temporaire
            extract_dir = self.extract_zip(zip_path)

            # Trouver les PDF REG010
            pdf_files = self.find_reg010_pdfs(extract_dir)

            # Extraire les données de chaque PDF
            dataframes = []
            processed_files = []

            for pdf_file in pdf_files:
                df = self.extract_data_from_pdf(pdf_file)
                if not df.empty:
                    dataframes.append(df)
                    processed_files.append(os.path.basename(pdf_file))

            return dataframes, processed_files

        finally:
            # Nettoyer le répertoire temporaire automatiquement
            if extract_dir and os.path.exists(extract_dir):
                shutil.rmtree(extract_dir, ignore_errors=True)

    def cleanup(self):
        """Nettoyer les fichiers temporaires (optionnel car tempfile gère automatiquement)"""
        # Les répertoires temporaires sont automatiquement nettoyés par le système
        # Cette méthode est gardée pour compatibilité mais n'est plus nécessaire
        pass
