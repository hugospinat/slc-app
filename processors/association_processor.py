from typing import Dict, List

import pandas as pd

from .base_processor import BaseProcessor


class AssociationProcessor(BaseProcessor):
    """Processeur pour associer les factures GED001 aux données REG010"""

    def __init__(self):
        super().__init__()

    def associer_factures_ged001_reg010(
        self, dataframes: List[pd.DataFrame], factures_ged001: Dict[str, Dict]
    ) -> Dict[str, Dict]:
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

        self.log_info(f"Numéros de factures REG010 trouvés: {len(numeros_factures_reg010)}")
        self.log_info(f"Factures GED001 extraites: {len(factures_ged001)}")

        # Associer chaque facture GED001 avec les données REG010
        for id_ged001, info_ged001 in factures_ged001.items():
            facture_associee = self._find_association(id_ged001, numeros_factures_reg010, libelles_factures_reg010)

            if facture_associee:
                associations[facture_associee] = {
                    "type": info_ged001["type"],
                    "pdf_contenu": info_ged001["pdf_contenu"],
                }
            else:
                self.log_warning(f"Aucune association trouvée pour GED001 {id_ged001}")

        self.log_success(f"Total des associations créées: {len(associations)}")
        return associations

    def _find_association(
        self, id_ged001: str, numeros_factures_reg010: set, libelles_factures_reg010: Dict[str, str]
    ) -> str | None:
        """
        Trouver l'association entre un ID GED001 et les factures REG010
        Retourne le numéro de facture REG010 associé ou None
        """
        # Recherche directe par numéro de facture
        if id_ged001 in numeros_factures_reg010:
            self.log_success(f"Association directe: REG010 {id_ged001} ↔ GED001 {id_ged001}")
            return id_ged001

        # Recherche dans les libellés
        for numero_reg010, libelle_reg010 in libelles_factures_reg010.items():
            if id_ged001 in libelle_reg010:
                self.log_success(f"Association par libellé: REG010 {numero_reg010} ↔ GED001 {id_ged001}")
                return numero_reg010

        return None
