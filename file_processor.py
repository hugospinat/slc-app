import logging
import os
import re
import shutil
import tempfile
import zipfile
from typing import List

import fitz
import pandas as pd
import tabula.io as tabula


class FileProcessor:
    """Classe pour traiter les fichiers ZIP et extraire les données des PDF"""

    def __init__(self, upload_dir: str = "uploads"):
        """Initialiser le processeur de fichiers"""
        self.upload_dir = upload_dir  # Gardé pour compatibilité mais non utilisé
        # Nous utilisons maintenant tempfile.mkdtemp() qui gère automatiquement les répertoires

        # Configuration du logger
        self.logger = logging.getLogger("file_processor")
        self.logger.setLevel(logging.DEBUG)

        # Handler pour le fichier log.txt
        fh = logging.FileHandler("log.txt", mode="a", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

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

    def find_ged001_pdfs(self, directory: str) -> List[str]:
        """Trouver tous les fichiers PDF contenant 'GED001' dans le nom"""
        pdf_files = []

        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(".pdf") and "GED001" in file:
                    pdf_files.append(os.path.join(root, file))

        return pdf_files

    def extract_data_from_pdf(self, pdf_path: str) -> pd.DataFrame:
        """Extraire les données d'un PDF REG010 de manière robuste"""
        try:
            self.logger.info(f"\n=== Traitement du fichier: {pdf_path} ===")
            print(f"🔄 Extraction du PDF: {os.path.basename(pdf_path)}")

            # Extraire les tableaux du PDF avec lattice
            dfs = tabula.read_pdf(
                pdf_path,
                pages="all",
                lattice=True,
                pandas_options={"header": None},
            )

            if not dfs:
                print(f"❌ Aucun tableau trouvé dans {pdf_path}")
                return pd.DataFrame()

            # Combiner tous les DataFrames
            combined_df = pd.concat(dfs, ignore_index=True)
            print(f"📊 Données brutes extraites: {len(combined_df)} lignes, {combined_df.shape[1]} colonnes")

            if combined_df.empty or combined_df.shape[1] < 7:
                print(f"❌ Format incorrect: {combined_df.shape[1]} colonnes (minimum 7 requis)")
                return pd.DataFrame()

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
            print(f"📊 Après suppression des lignes vides: {len(combined_df)}")

            # **ÉTAPE 1: Filtrer AVANT l'extension des natures**
            print("💰 Filtrage par montants valides...")

            # Identifier les lignes avec des montants valides
            montant_pattern = r"^-?\d+\.\d{1,2}$"
            combined_df["montant_comptable"] = combined_df["montant_comptable"].astype(str).str.strip()

            # Log des lignes rejetées
            for idx, row in combined_df.iterrows():
                montant = str(row["montant_comptable"]).strip()
                if not montant or montant == "nan" or not re.match(montant_pattern, montant):
                    self.logger.debug(f"Ligne rejetée ({os.path.basename(pdf_path)}) - Raison: montant invalide")
                    self.logger.debug(f"Données: {row.to_dict()}")
                    self.logger.debug(f"Montant trouvé: '{montant}'")
                    self.logger.debug("-" * 50)

            # Masque pour les montants valides (pas de NaN, pas de chaînes vides)
            mask_montant_valide = (
                combined_df["montant_comptable"].notna()
                & (combined_df["montant_comptable"] != "nan")
                & (combined_df["montant_comptable"] != "")
                & combined_df["montant_comptable"].str.match(montant_pattern, na=False)
            )

            print(f"📊 Lignes avant filtrage montants: {len(combined_df)}")
            print(f"📊 Lignes avec montants valides: {mask_montant_valide.sum()}")

            # Appliquer le filtre
            filtered_df = combined_df[mask_montant_valide].copy()
            print(f"📊 Lignes après filtrage montants: {len(filtered_df)}")

            if filtered_df.empty:
                print("⚠️ Aucune ligne avec montant valide trouvée")
                return pd.DataFrame()

            # **ÉTAPE 2: Déduplication après filtrage des montants**
            print("🔧 Suppression des doublons...")
            nb_lignes_avant_dedup = len(filtered_df)

            # Déduplication basée sur numero_facture et montant_comptable
            filtered_df = filtered_df.drop_duplicates(subset=["numero_facture", "montant_comptable"], keep="first")

            nb_lignes_apres_dedup = len(filtered_df)
            nb_doublons_supprimes = nb_lignes_avant_dedup - nb_lignes_apres_dedup

            if nb_doublons_supprimes > 0:
                print(f"⚠️ {nb_doublons_supprimes} doublons supprimés")
            else:
                print("✅ Aucun doublon détecté")

            # **ÉTAPE 3: Extension des natures sur les données déduplicées**
            print("🔧 Extension du champ nature...")

            # Remplacer les valeurs vides par NaN pour que ffill fonctionne
            filtered_df["nature"] = filtered_df["nature"].astype(str)
            filtered_df.loc[filtered_df["nature"].isin(["", "nan", "NaN", "None"]), "nature"] = pd.NA

            # Forward fill pour étendre les natures
            filtered_df["nature"] = filtered_df["nature"].ffill()

            # **ÉTAPE 4: Conversion des montants**
            filtered_df["montant_comptable"] = filtered_df["montant_comptable"].str.replace(",", ".").astype(float)

            # **ÉTAPE 5: Ajouter les métadonnées**
            filtered_df["fichier_source"] = os.path.basename(pdf_path)
            filtered_df["ligne_pdf"] = range(1, len(filtered_df) + 1)

            # **ÉTAPE 6: Validation finale - éliminer les lignes avec nature manquante**
            filtered_df = filtered_df.dropna(subset=["nature"])

            # **ÉTAPE 7: Déduplication finale (au cas où l'extension des natures aurait créé des doublons)**
            nb_lignes_avant_dedup_finale = len(filtered_df)
            filtered_df = filtered_df.drop_duplicates(
                subset=["numero_facture", "montant_comptable", "nature"], keep="first"
            )
            filtered_df = filtered_df.reset_index(drop=True)  # Réinitialiser les index

            # Recalculer ligne_pdf après déduplication
            filtered_df["ligne_pdf"] = range(1, len(filtered_df) + 1)

            nb_lignes_apres_dedup_finale = len(filtered_df)
            nb_doublons_finaux = nb_lignes_avant_dedup_finale - nb_lignes_apres_dedup_finale

            if nb_doublons_finaux > 0:
                print(f"⚠️ {nb_doublons_finaux} doublons supprimés après extension des natures")

            # Afficher les résultats finaux
            print(f"✅ Extraction terminée: {len(filtered_df)} factures valides uniques")
            if not filtered_df.empty:
                natures_trouvees = filtered_df["nature"].dropna().unique()
                print(f"🏷️ Natures identifiées: {list(natures_trouvees)}")

                montant_total = filtered_df["montant_comptable"].sum()
                print(f"💰 Montant total: {montant_total:.2f}€")

                # Debug: afficher les premières lignes
                print("📋 Premières lignes validées:")
                for i, row in filtered_df.head(3).iterrows():
                    print(
                        f"  - Nature: {row['nature']}, Facture: {row['numero_facture']}, Montant: {row['montant_comptable']}"
                    )

            return filtered_df

        except Exception as e:
            self.logger.error(f"Erreur dans {pdf_path}: {str(e)}")
            print(f"❌ Erreur lors de l'extraction du PDF {pdf_path}: {e}")
            import traceback

            traceback.print_exc()
            return pd.DataFrame()

    def process_zip_file(self, zip_path: str) -> tuple[List[pd.DataFrame], List[str], dict]:
        """Traiter un fichier ZIP et extraire les données des PDF REG010 et GED001"""
        dataframes = []
        processed_files = []
        toutes_factures_ged001 = {}  # Dictionnaire pour stocker toutes les factures GED001
        extract_dir = None

        try:
            # Extraire le ZIP
            extract_dir = self.extract_zip(zip_path)

            # Trouver les fichiers REG010 et GED001
            reg010_files = self.find_reg010_pdfs(extract_dir)
            ged001_files = self.find_ged001_pdfs(extract_dir)

            print(f"📄 Fichiers REG010 trouvés: {len(reg010_files)}")
            print(f"📎 Fichiers GED001 trouvés: {len(ged001_files)}")

            # Analyser les fichiers GED001 et extraire directement les PDFs de factures
            if ged001_files:
                print("📋 Analyse et extraction des fichiers GED001 :")
                for ged_file in ged001_files:
                    nom_fichier = os.path.basename(ged_file)
                    print(f"🔍 Traitement de {nom_fichier}")

                    factures_extraites = self.analyser_et_extraire_factures_ged001(ged_file)

                    if factures_extraites:
                        print(f"  📊 {len(factures_extraites)} factures extraites:")
                        for id_facture, info in factures_extraites.items():
                            toutes_factures_ged001[id_facture] = info
                            print(f"    - {id_facture} ({info['type']}): {info['nb_pages']} pages")
                    else:
                        print(f"  ⚠️ Aucune facture extraite de {nom_fichier}")

            # Traiter les fichiers REG010
            for pdf_path in reg010_files:
                print(f"🔄 Traitement de {os.path.basename(pdf_path)}")
                df = self.extract_data_from_pdf(pdf_path)

                if not df.empty:
                    df["fichier_source"] = os.path.basename(pdf_path)
                    dataframes.append(df)
                    processed_files.append(os.path.basename(pdf_path))

        finally:
            # Nettoyer le répertoire temporaire
            if extract_dir and os.path.exists(extract_dir):
                shutil.rmtree(extract_dir, ignore_errors=True)

        return dataframes, processed_files, toutes_factures_ged001

    def extraire_pages_facture(self, chemin_pdf: str, pages: List[int]) -> bytes:
        """
        Extraire certaines pages d'un PDF et retourner le contenu binaire
        """
        import fitz

        try:
            # Ouvrir le PDF source
            doc_source = fitz.open(chemin_pdf)

            # Créer un nouveau PDF avec seulement les pages voulues
            doc_nouveau = fitz.open()

            for num_page in pages:
                if num_page < len(doc_source):
                    doc_nouveau.insert_pdf(doc_source, from_page=num_page, to_page=num_page)

            # Récupérer le contenu binaire
            contenu_binaire = doc_nouveau.tobytes()

            doc_source.close()
            doc_nouveau.close()

            return contenu_binaire

        except Exception as e:
            print(f"❌ Erreur lors de l'extraction des pages: {e}")
            return b""

    def analyser_et_extraire_factures_ged001(self, chemin_pdf: str) -> dict:
        """
        Analyser un PDF GED001 en un seul passage et extraire directement tous les PDFs de factures
        Retourne: {identifiant_facture: {'type': 'BONTRV01'|'FACFOU01', 'pdf_contenu': bytes}}
        """
        factures_extraites = {}

        try:
            # Ouvrir le PDF source
            doc_source = fitz.open(chemin_pdf)
            print(f"📄 Analyse du PDF: {os.path.basename(chemin_pdf)} ({len(doc_source)} pages)")

            facture_courante = None
            type_facture = None
            pages_courantes = []

            def finaliser_facture():
                """Fonction interne pour finaliser une facture et extraire son PDF"""
                if facture_courante and pages_courantes:
                    # Créer un nouveau PDF pour cette facture
                    doc_facture = fitz.open()

                    # Ajouter toutes les pages de cette facture
                    for num_page in pages_courantes:
                        if num_page < len(doc_source):
                            doc_facture.insert_pdf(doc_source, from_page=num_page, to_page=num_page)

                    # Récupérer le contenu binaire
                    contenu_pdf = doc_facture.tobytes()
                    doc_facture.close()

                    # Stocker la facture
                    factures_extraites[facture_courante] = {
                        "type": type_facture,
                        "pdf_contenu": contenu_pdf,
                        "nb_pages": len(pages_courantes),
                    }

                    print(
                        f"  ✅ Facture {facture_courante} ({type_facture}): {len(pages_courantes)} pages, PDF généré ({len(contenu_pdf)} octets)"
                    )

            # Parcourir toutes les pages UNE SEULE fois
            for num_page in range(len(doc_source)):
                page = doc_source[num_page]
                textpage = page.get_textpage()
                texte_page = textpage.extractText()

                # Chercher les patterns BONTRV01 ou FACFOU01
                pattern_bontrv = r"(\d+\s*\)\s*BONTRV01\s+([A-Z0-9]+)/.*BONTRV01)"
                pattern_facfou = r"(\d+\s*\)\s*FACFOU01\s+([A-Z0-9]+)/.*FACFOU01)"

                match_bontrv = re.search(pattern_bontrv, texte_page)
                match_facfou = re.search(pattern_facfou, texte_page)

                # Détecter un nouvel identifiant
                nouvel_identifiant = None
                nouveau_type = None

                if match_bontrv:
                    nouvel_identifiant = match_bontrv.group(2)
                    nouveau_type = "BONTRV01"

                elif match_facfou:
                    nouvel_identifiant = match_facfou.group(2)
                    nouveau_type = "FACFOU01"

                # Si on change de facture, finaliser la précédente
                if nouvel_identifiant and nouvel_identifiant != facture_courante:
                    # Finaliser la facture précédente
                    finaliser_facture()

                    # Commencer une nouvelle facture
                    facture_courante = nouvel_identifiant
                    type_facture = nouveau_type
                    pages_courantes = [num_page]

                else:
                    # Ajouter la page à la facture courante
                    if facture_courante:
                        pages_courantes.append(num_page)

            # Finaliser la dernière facture
            finaliser_facture()

            doc_source.close()
            print(f"📊 Total des factures extraites: {len(factures_extraites)}")

        except Exception as e:
            print(f"❌ Erreur lors de l'analyse du PDF {chemin_pdf}: {e}")

        return factures_extraites

    def associer_factures_ged001_reg010(self, dataframes: List[pd.DataFrame], factures_ged001: dict) -> dict:
        """
        Associer les factures GED001 (avec PDF déjà généré) aux lignes de données REG010
        Retourne: {numero_facture_reg010: {'type': str, 'pdf_contenu': bytes}}
        """
        associations = {}

        # Extraire tous les numéros de facture et libellés des DataFrames REG010
        numeros_factures_reg010 = set()
        libelles_factures_reg010 = {}

        for df in dataframes:
            if "numero_facture" in df.columns and "libelle_ecriture" in df.columns:
                for _, row in df.iterrows():
                    numero_facture = str(row["numero_facture"])
                    libelle_ecriture = str(row["libelle_ecriture"])
                    numeros_factures_reg010.add(numero_facture)
                    libelles_factures_reg010[numero_facture] = libelle_ecriture

        print(f"🔍 Numéros de factures REG010 trouvés: {len(numeros_factures_reg010)}")
        print(f"🔍 Factures GED001 extraites: {len(factures_ged001)}")

        # Associer chaque facture GED001 avec les données REG010
        for id_ged001, info_ged001 in factures_ged001.items():
            facture_associee = None

            # Recherche directe par numéro de facture
            if id_ged001 in numeros_factures_reg010:
                facture_associee = id_ged001
                print(f"  ✅ Association directe: REG010 {facture_associee} ↔ GED001 {id_ged001}")
            else:
                # Recherche dans les libellés
                for numero_reg010, libelle_reg010 in libelles_factures_reg010.items():
                    if id_ged001 in libelle_reg010:
                        facture_associee = numero_reg010
                        print(f"  ✅ Association par libellé: REG010 {facture_associee} ↔ GED001 {id_ged001}")
                        break

            if facture_associee:
                associations[facture_associee] = {
                    "type": info_ged001["type"],
                    "pdf_contenu": info_ged001["pdf_contenu"],
                }
            else:
                print(f"  ⚠️ Aucune association trouvée pour GED001 {id_ged001}")

        print(f"📎 Total des associations créées: {len(associations)}")
        return associations
