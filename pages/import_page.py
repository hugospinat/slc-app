import os
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st
from sqlmodel import Session, select

from processors import CDCProcessor
from utils.database import save_to_database


# Utiliser le cache Streamlit pour éviter les reimports multiples
@st.cache_resource
def import_models():
    """Import des modèles avec cache pour éviter les redéfinitions SQLAlchemy"""
    from models import Groupe, engine

    return Groupe, engine


# Import avec cache
Groupe, engine = import_models()


def main():
    st.set_page_config(page_title="Import des fichiers", page_icon="📤", layout="wide")
    st.header("Import de fichiers ZIP")

    # Récupérer tous les groupes et années une seule fois
    with Session(engine) as session:
        groupes = session.exec(select(Groupe)).all()
        if not groupes:
            st.error("⚠️ Aucun groupe n'est configuré!")
            st.info("Veuillez d'abord créer au moins un groupe dans la section 'Gestion des Groupes'")
            if st.button("Aller à la gestion des groupes"):
                st.switch_page("pages/groupes_page.py")
            return

        # Créer deux colonnes pour les sélecteurs
        col1, col2 = st.columns(2)

        with col1:
            groupe_options = {f"{g.nom} ({g.identifiant})": g.id for g in groupes}
            selected_groupe = st.selectbox(
                "Sélectionner un groupe", options=list(groupe_options.keys()), key="groupe_selectbox"
            )
            groupe_id = groupe_options[selected_groupe]

        with col2:
            current_year = datetime.now().year
            annee = st.number_input(
                "Année",
                min_value=2000,
                max_value=current_year + 1,
                value=current_year,
                step=1,
                format="%d",
                key="annee_input",
            )

        # Afficher les informations d'import
        st.info(f"📋 Importation pour: **{selected_groupe}** - Année: **{annee}**")

        # Upload du fichier ZIP
        uploaded_file = st.file_uploader("Choisir un fichier ZIP", type=["zip"], key="zip_uploader")

        if uploaded_file is not None:
            if st.button("Traiter le fichier"):
                with st.spinner("Traitement en cours..."):
                    # Sauvegarder le fichier temporairement
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
                        tmp_file.write(uploaded_file.read())
                        tmp_path = tmp_file.name

                    try:
                        # Traiter le fichier
                        processor = CDCProcessor()
                        dataframes, processed_files, factures_ged001 = processor.process_zip_file(tmp_path)

                        if not dataframes:
                            st.error("Aucun fichier PDF REG010 trouvé ou aucune donnée extraite.")
                            return

                        # Combiner tous les DataFrames
                        combined_df = pd.concat(dataframes, ignore_index=True)

                        st.success(f"✅ {len(processed_files)} fichiers PDF REG010 traités avec succès!")
                        st.info(f"📄 Fichiers traités: {', '.join(processed_files)}")
                        st.info(f"📊 {len(combined_df)} lignes de données extraites")

                        if factures_ged001:
                            st.info(f"📎 {len(factures_ged001)} factures GED001 extraites avec PDFs")

                        # Sauvegarder directement en base de données
                        save_to_database(combined_df, groupe_id, annee, factures_ged001)
                        st.success("✅ Données et PDFs sauvegardés en base avec succès!")

                    finally:
                        # Nettoyer le fichier temporaire
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)


if __name__ == "__main__":
    main()
