import os
import tempfile
from datetime import datetime

import streamlit as st
from sqlmodel import Session, select

from slc_app.services.importer import PHImporter


# Utiliser le cache Streamlit pour éviter les reimports multiples
@st.cache_resource
def import_models():
    """Import des modèles avec cache pour éviter les redéfinitions SQLAlchemy"""
    from slc_app.models import Groupe, engine

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
            st.info(
                "Veuillez d'abord créer au moins un groupe dans la section 'Gestion des Groupes'"
            )
            if st.button("Aller à la gestion des groupes"):
                st.switch_page("pages/groupes_page.py")
            return

        # Créer deux colonnes pour les sélecteurs
        col1, col2 = st.columns(2)

        with col1:
            groupe_options = {f"{g.nom} ({g.identifiant})": g.id for g in groupes}
            selected_groupe_name = st.selectbox(
                "Sélectionner un groupe",
                options=list(groupe_options.keys()),
                key="groupe_selectbox",
            )
            groupe_id = groupe_options[selected_groupe_name]

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
        st.info(f"📋 Importation pour: **{selected_groupe_name}** - Année: **{annee}**")

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
                        # Traiter le fichier en passant l'ID du groupe
                        if groupe_id is None:
                            st.error("⚠️ Groupe non sélectionné!")
                        else:
                            st.success(f"📤 Fichier ZIP importé: {os.path.basename(tmp_path)}")
                            st.info("Traitement en cours...")
                            PHImporter(annee, groupe_id, tmp_path)
                            st.success("✅ Fichier traité avec succès!")
                    finally:
                        # Nettoyer le fichier temporaire
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)


if __name__ == "__main__":
    main()
