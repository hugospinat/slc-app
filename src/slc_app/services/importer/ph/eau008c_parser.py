import os
from typing import List, Tuple

import pandas as pd
import tabula.io as tabula
from sqlmodel import Session

from slc_app.models import (
    PosteReleve,
    SourceColPosteReleve,
    SourceColReleveIndividuel,
    ReleveIndividuel,
)
from slc_app.services.importer.ph.base_processor import BaseProcessor
from slc_app.utils.file_storage import save_file_from_path


class ParserEAU008C(BaseProcessor):
    """Processeur spécialisé pour l'extraction des données des PDF EAU008C (relevés individuels)"""

    def __init__(self):
        super().__init__()

    def _extract_data_from_pdf(self, pdf_path: str) -> pd.DataFrame:
        """Extraire les données d'un PDF EAU008C de manière robuste"""
        try:
            self.log_info(f"Traitement du fichier EAU008C: {pdf_path}")
            self.log_info(f"🔄 Extraction du PDF: {os.path.basename(pdf_path)}")

            # Extraire les tableaux du PDF avec lattice (même méthode que REG114)
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

            if combined_df.empty or combined_df.shape[1] < 11:
                self.log_error(
                    f"Format incorrect: {combined_df.shape[1]} colonnes (minimum 11 requis pour EAU008C)"
                )
                raise ValueError(
                    f"Format incorrect: {combined_df.shape[1]} colonnes (minimum 11 requis pour EAU008C)"
                )

            return combined_df

        except Exception as e:
            self.log_error(f"Erreur dans {pdf_path}: {str(e)}")
            import traceback

            traceback.print_exc()
            raise ValueError(
                f"Erreur lors de l'extraction des données de {pdf_path}: {str(e)}"
            ) from e

    def _process_extracted_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Traiter et nettoyer les données extraites du EAU008C avec détection des postes de relevé"""
        # Nommer les colonnes selon le modèle de données EAU008C
        colonnes_eau008c = [
            "nom_poste",  # Colonne 0: nom du poste (propagé)
            SourceColReleveIndividuel.NUMERO_UG,  # Colonne 1: N°UG
            SourceColReleveIndividuel.NATURE_UG,  # Colonne 2: Nature UG
            SourceColReleveIndividuel.NUMERO_CA,  # Colonne 3: N°CA
            SourceColReleveIndividuel.POINT_COMPTAGE,  # Colonne 4: Point de Comptage
            SourceColReleveIndividuel.NUMERO_SERIE_COMPTEUR,  # Colonne 5: N° Série compteur
            SourceColReleveIndividuel.DATE_RELEVE,  # Colonne 6: Date du Relevé
            SourceColReleveIndividuel.DATE_VALEUR,  # Colonne 7: Date de valeur
            SourceColReleveIndividuel.TYPE_RELEVE,  # Colonne 8: Type de Relevé
            SourceColReleveIndividuel.OBSERVATIONS,  # Colonne 9: Observations
            SourceColReleveIndividuel.INDEX,  # Colonne 10: Index
            SourceColReleveIndividuel.EVOLUTION_INDEX,  # Colonne 11: Evolution Index
        ]
        colonnes_postes = [SourceColPosteReleve.NOM]

        try:
            self.log_info(f"[DEBUG] DataFrame initial: {df.shape}")
            self.log_info(f"[DEBUG] Colonnes: {df.columns.tolist()}")

            # Supprimer les lignes complètement vides
            df = df.dropna(how="all")
            self.log_info(f"📊 Après suppression des lignes vides: {len(df)}")

            # Supprimer les lignes avec 12 colonnes ou plus non vides (doublons théoriques)
            df_filtre = self._filtrer_par_nombre_colonnes(df)
            self.log_info(f"[DEBUG] Après filtrage: {df_filtre.shape}")

            # Pattern pour détecter les postes de relevé (similaire aux bases de répartition)
            # Exemples: "EAU CHAUDE INDIVIDUELLE", "EAU FROIDE INDIVIDUELLE", "COMPTEUR DE CALORIE"
            pattern_poste = r"^([A-Z][A-Z\s]+)$"

            # Extraire les noms de postes
            self.log_info("[DEBUG] Échantillon de données colonne 0 avant extraction:")
            sample_data = df_filtre.iloc[:10, 0].astype(str).tolist()
            for i, val in enumerate(sample_data):
                self.log_info(f"[DEBUG] Ligne {i}: '{val}'")

            postes_extraits = (
                df_filtre.iloc[:, 0].astype(str).str.extract(pattern_poste, expand=False)
            )
            self.log_info(f"[DEBUG] Postes extraits: {postes_extraits.count()} non-null")
            self.log_info("[DEBUG] Échantillon postes_extraits:")
            self.log_info(f"{postes_extraits.dropna().head()}")

            # Propager le nom de poste vers le bas (forward fill) jusqu'au prochain poste
            noms_poste_propages = postes_extraits.ffill()
            self.log_info(f"[DEBUG] Noms propagés: {noms_poste_propages.count()} non-null")

            # Ajouter la colonne au DataFrame
            df_avec_poste = df.copy()
            df_avec_poste.insert(0, "nom_poste_actuel", noms_poste_propages)
            self.log_info(f"[DEBUG] DataFrame avec postes: {df_avec_poste.shape}")

            # Nous devons maintenant prendre seulement les colonnes nécessaires (12 premières)
            # car le DataFrame original peut avoir plus de colonnes que prévu
            nb_colonnes_attendues = len(colonnes_eau008c)
            if df_avec_poste.shape[1] > nb_colonnes_attendues:
                self.log_info(
                    f"[DEBUG] Réduction de {df_avec_poste.shape[1]} à {nb_colonnes_attendues} colonnes"
                )
                df_avec_poste = df_avec_poste.iloc[:, :nb_colonnes_attendues]

            df_avec_poste.columns = colonnes_eau008c
            self.log_info(f"[DEBUG] Colonnes finales: {df_avec_poste.columns.tolist()}")

            # Appliquer des validations plus strictes pour ne garder que les vrais relevés
            numero_ug_pattern = r"^\d+$"
            numero_ca_pattern = r"^\d+$"
            index_pattern = r"^\d+$"

            numero_ug_col = SourceColReleveIndividuel.NUMERO_UG
            numero_ca_col = SourceColReleveIndividuel.NUMERO_CA
            index_col = SourceColReleveIndividuel.INDEX

            self.log_info(
                f"[DEBUG] Validation stricte sur colonnes: {numero_ug_col}, {numero_ca_col}, {index_col}"
            )

            # Validation 1: Numéro UG doit être numérique
            mask_numero_ug = df_avec_poste[numero_ug_col].astype(str).str.match(numero_ug_pattern)
            self.log_info(f"[DEBUG] Lignes avec UG valide: {mask_numero_ug.sum()}")

            # Validation 2: Numéro CA doit être numérique
            mask_numero_ca = df_avec_poste[numero_ca_col].astype(str).str.match(numero_ca_pattern)
            self.log_info(f"[DEBUG] Lignes avec CA valide: {mask_numero_ca.sum()}")

            # Validation 3: Index doit être numérique
            mask_index = df_avec_poste[index_col].astype(str).str.match(index_pattern)
            self.log_info(f"[DEBUG] Lignes avec Index valide: {mask_index.sum()}")

            # Combiner toutes les validations (ET logique)
            mask_complet = mask_numero_ug & mask_numero_ca & mask_index
            df_avec_poste = df_avec_poste[mask_complet]
            self.log_info(f"[DEBUG] Après validation complète: {len(df_avec_poste)} lignes")

            # Récupérer les postes uniques extraits
            unique_postes_extraits = (
                postes_extraits.dropna().drop_duplicates().reset_index(drop=True)
            )
            self.log_info(
                f"[DEBUG] Postes uniques avant création DataFrame: {unique_postes_extraits.shape}"
            )

            # Vérifier que nous avons des postes valides
            if unique_postes_extraits.empty:
                self.log_warning("Aucun poste de relevé trouvé dans le document")
                # Créer un DataFrame vide avec les bonnes colonnes
                postes_releve = pd.DataFrame(columns=colonnes_postes)
            else:
                self.log_info(f"[DEBUG] Premiers postes trouvés: {unique_postes_extraits.head()}")
                postes_releve = pd.DataFrame({SourceColPosteReleve.NOM: unique_postes_extraits})
                # Vérifier s'il y a des valeurs nulles
                nulls_in_postes = postes_releve.isnull().sum()
                if nulls_in_postes.any():
                    self.log_warning(f"[DEBUG] Valeurs nulles dans les postes: {nulls_in_postes}")

            self.log_info(f"📋 Noms de postes propagés sur {len(df_avec_poste)} lignes")
            self.log_info(f"📊 {len(postes_releve)} postes de relevé identifiés")

            return df_avec_poste, postes_releve

        except Exception as e:
            self.log_error(f"Erreur lors du traitement des données: {str(e)}")
            import traceback

            traceback.print_exc()
            # Re-raise l'erreur originale au lieu de la masquer
            raise e

    def _filtrer_par_nombre_colonnes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Supprimer les lignes ayant 12 colonnes ou plus non vides (section écarts théoriques)"""
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

        # Garder seulement les lignes avec moins de 12 colonnes non vides
        mask_a_garder = nb_colonnes_par_ligne < 12

        nb_lignes_supprimees = (~mask_a_garder).sum()
        if nb_lignes_supprimees > 0:
            self.log_info(
                f"🔄 Suppression doublons : {nb_lignes_supprimees} lignes avec 12+ colonnes supprimées"
            )

        return df[mask_a_garder].copy()

    def _prepare_for_database(
        self, releves_df: pd.DataFrame, postes_df: pd.DataFrame, controle_id: int
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Préparer les DataFrames pour la sauvegarde en base (sans session DB)"""
        if postes_df.empty or releves_df.empty:
            self.log_warning("DataFrames vides, rien à préparer")
            raise ValueError("❌ DataFrames vides, rien à préparer")

        # Vérifier qu'il n'y a pas de valeurs nulles dans les colonnes critiques
        if postes_df[SourceColPosteReleve.NOM].isnull().any():
            self.log_error("Des noms de postes sont null, impossible de préparer")
            self.log_info(
                f"[DEBUG] Postes_df avec nulls: {postes_df[postes_df[SourceColPosteReleve.NOM].isnull()]}"
            )
            raise ValueError("❌ Des noms de postes sont null, impossible de préparer")

        try:
            # Préparer les postes avec l'ID du contrôle
            postes_prepared = postes_df.copy()
            postes_prepared[SourceColPosteReleve.CONTROLE_ID] = controle_id
            
            # Préparer les relevés avec conversion des types
            releves_prepared = releves_df.copy()
            
            # Convertir les colonnes numériques en string pour respecter le modèle
            string_columns = [
                SourceColReleveIndividuel.NUMERO_UG,
                SourceColReleveIndividuel.NUMERO_CA,
                SourceColReleveIndividuel.POINT_COMPTAGE,
                SourceColReleveIndividuel.NUMERO_SERIE_COMPTEUR,
                SourceColReleveIndividuel.TYPE_RELEVE,
                SourceColReleveIndividuel.OBSERVATIONS,
                SourceColReleveIndividuel.NATURE_UG,
            ]
            for col in string_columns:
                if col in releves_prepared.columns:
                    releves_prepared[col] = releves_prepared[col].fillna("").astype(str)
                    # Remplacer "nan" par chaîne vide pour les valeurs optionnelles
                    releves_prepared[col] = releves_prepared[col].replace("nan", "")

            self.log_info(f"📋 {len(postes_prepared)} postes de relevé préparés")
            self.log_info(f"📊 {len(releves_prepared)} relevés individuels préparés")

            return releves_prepared, postes_prepared

        except Exception as e:
            raise ValueError(f"❌ Erreur lors de la préparation des données: {str(e)}") from e
    
    def _save_to_database(
        self, releves_df: pd.DataFrame, postes_df: pd.DataFrame, session: Session
    ) -> Tuple[List[ReleveIndividuel], List[PosteReleve]]:
        """Sauvegarder les DataFrames préparés en base de données avec une session courte"""
        try:
            # Créer les objets PosteReleve
            poste_objects = PosteReleve.from_df(postes_df)
            session.add_all(poste_objects)
            session.commit()
            for p in poste_objects:
                session.refresh(p)

            # Créer un mapping nom -> id pour les postes
            poste_id_map = {p.nom: p.id for p in poste_objects}
            releves_df_with_ids = releves_df.copy()
            releves_df_with_ids[SourceColReleveIndividuel.POSTE_RELEVE_ID] = releves_df_with_ids["nom_poste"].map(
                poste_id_map
            )

            # Créer les objets ReleveIndividuel
            releve_objects = ReleveIndividuel.from_df(releves_df_with_ids)
            session.add_all(releve_objects)
            session.commit()
            for r in releve_objects:
                session.refresh(r)

            compteur_postes, compteur_releves = len(poste_objects), len(releve_objects)
            self.log_info(f"✅ {compteur_postes} postes de relevé sauvegardés en base")
            self.log_info(f"✅ {compteur_releves} relevés individuels sauvegardés en base")

            return releve_objects, poste_objects

        except Exception as e:
            session.rollback()
            raise ValueError(f"❌ Erreur lors de la sauvegarde en base de données: {str(e)}") from e

    def process_eau008c(
        self, pdf_path: str, controle_id: int, savePath: str, session: Session
    ) -> Tuple[List[ReleveIndividuel], List[PosteReleve]]:
        """Traiter un fichier EAU008C complet"""
        self.log_info(f"🔄 Traitement de {os.path.basename(pdf_path)}")
        data = self._extract_data_from_pdf(pdf_path)
        save_file_from_path(pdf_path, savePath, "eau008c.pdf")
        df_releves, df_postes = self._process_extracted_data(data)
        releves, postes_releve = self._save_to_database(df_releves, df_postes, controle_id, session)
        return releves, postes_releve
