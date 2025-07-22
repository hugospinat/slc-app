import os
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st
from sqlmodel import Session, select

from file_processor import FileProcessor
from models import ControleCharges, Facture, Groupe, create_db_and_tables, engine


def init_database():
    """Initialiser la base de données"""
    try:
        print("🔧 Initialisation de la base de données...")
        create_db_and_tables()
        print("✅ Base de données initialisée avec succès")

        # Vérifier la connexion
        with Session(engine) as session:
            groupes_count = len(session.exec(select(Groupe)).all())
            print(f"📊 Groupes existants: {groupes_count}")

    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base: {e}")
        import traceback

        traceback.print_exc()


def main():
    st.set_page_config(page_title="Contrôle des Charges", page_icon="📊", layout="wide")

    st.title("📊 Application de Contrôle des Charges")

    # Initialiser la base de données
    init_database()

    # Initialiser la navigation dans session_state si pas déjà fait
    if "page" not in st.session_state:
        st.session_state.page = "Import de fichiers"

    # Sidebar pour la navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choisir une page",
        ["Import de fichiers", "Gestion des groupes", "Validation des factures", "Tableau de bord"],
        index=["Import de fichiers", "Gestion des groupes", "Validation des factures", "Tableau de bord"].index(
            st.session_state.page
        ),
    )

    # Mettre à jour la page sélectionnée
    st.session_state.page = page

    if page == "Import de fichiers":
        page_import()
    elif page == "Gestion des groupes":
        page_groupes()
    elif page == "Validation des factures":
        page_validation()
    elif page == "Tableau de bord":
        page_dashboard()


def page_import():
    """Page d'import des fichiers ZIP"""
    st.header("Import de fichiers ZIP")

    # Sélection du groupe et de l'année
    col1, col2 = st.columns(2)

    with col1:
        # Récupérer les groupes existants
        with Session(engine) as session:
            groupes = session.exec(select(Groupe)).all()

        if not groupes:
            st.warning("Aucun groupe trouvé. Veuillez d'abord créer un groupe dans la section 'Gestion des groupes'.")
            return

        groupe_options = {f"{g.nom} ({g.identifiant})": g.id for g in groupes}
        selected_groupe = st.selectbox("Sélectionner un groupe", options=list(groupe_options.keys()))
        groupe_id = groupe_options[selected_groupe]

    with col2:
        annee = st.number_input("Année des charges", min_value=2020, max_value=2030, value=datetime.now().year)

    # Upload du fichier ZIP
    uploaded_file = st.file_uploader("Choisir un fichier ZIP", type=["zip"])

    if uploaded_file is not None:
        if st.button("Traiter le fichier"):
            with st.spinner("Traitement en cours..."):
                # Sauvegarder le fichier temporairement
                with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
                    tmp_file.write(uploaded_file.read())
                    tmp_path = tmp_file.name

                try:
                    # Traiter le fichier
                    processor = FileProcessor()
                    dataframes, processed_files = processor.process_zip_file(tmp_path)

                    if not dataframes:
                        st.error("Aucun fichier PDF REG010 trouvé ou aucune donnée extraite.")
                        return

                    # Combiner tous les DataFrames
                    combined_df = pd.concat(dataframes, ignore_index=True)

                    st.success(f"✅ {len(processed_files)} fichiers PDF traités avec succès!")
                    st.info(f"📄 Fichiers traités: {', '.join(processed_files)}")
                    st.info(f"📊 {len(combined_df)} lignes de données extraites")

                    # Sauvegarder directement en base de données
                    if groupe_id is not None:
                        try:
                            save_to_database(combined_df, groupe_id, annee)
                            st.success("✅ Données sauvegardées en base avec succès!")
                            st.success("🔄 Redirection vers la validation...")

                            # Nettoyer
                            processor.cleanup()

                            # Marquer qu'on vient d'importer des données
                            st.session_state.just_imported = True

                            # Rediriger vers la page de validation
                            st.session_state.page = "Validation des factures"
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Erreur lors de la sauvegarde: {e}")
                            st.error("Vérifiez la console pour plus de détails")
                    else:
                        st.error("Erreur: Groupe non sélectionné")

                finally:
                    # Nettoyer le fichier temporaire
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)


def save_to_database(df: pd.DataFrame, groupe_id: int, annee: int):
    """Sauvegarder les données en base"""
    try:
        with Session(engine) as session:
            # Créer ou récupérer le contrôle des charges
            print(f"🔍 Recherche contrôle pour groupe_id={groupe_id}, annee={annee}")
            controle = session.exec(
                select(ControleCharges).where(ControleCharges.groupe_id == groupe_id, ControleCharges.annee == annee)
            ).first()

            if not controle:
                print("➕ Création nouveau contrôle des charges")
                controle = ControleCharges(groupe_id=groupe_id, annee=annee)
                session.add(controle)
                session.commit()
                session.refresh(controle)
                print(f"✅ Contrôle créé avec ID: {controle.id}")
            else:
                print(f"✅ Contrôle existant trouvé avec ID: {controle.id}")

            # Ajouter les factures
            factures_ajoutees = 0
            print(f"📊 Traitement de {len(df)} lignes de factures")

            for index, row in df.iterrows():
                if controle.id is not None:
                    try:
                        facture = Facture(
                            controle_id=controle.id,
                            nature=str(row["nature"]),
                            numero_facture=str(row["numero_facture"]),
                            code_journal=str(row["code_journal"]),
                            numero_compte_comptable=str(row["numero_compte_comptable"]),
                            montant_comptable=float(row["montant_comptable"]),
                            libelle_ecriture=str(row["libelle_ecriture"]),
                            references_partenaire_facture=str(row["references_partenaire_facture"]),
                            fichier_source=str(row["fichier_source"]),
                            ligne_pdf=int(row["ligne_pdf"]),
                        )
                        session.add(facture)
                        factures_ajoutees += 1
                    except Exception as e:
                        print(f"❌ Erreur ligne {index}: {e}")
                        continue

            print(f"💾 Sauvegarde de {factures_ajoutees} factures...")
            session.commit()
            print(f"✅ {factures_ajoutees} factures sauvegardées avec succès!")

    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        import traceback

        traceback.print_exc()
        raise


def update_facture_statut(facture_id: int, nouveau_statut: str):
    """Mettre à jour le statut d'une facture automatiquement"""
    try:
        with Session(engine) as session:
            facture = session.get(Facture, facture_id)
            if facture:
                facture.statut = nouveau_statut
                facture.date_traitement = datetime.now()
                session.add(facture)
                session.commit()
                st.success(f"✅ Statut mis à jour: {nouveau_statut}")
    except Exception as e:
        st.error(f"❌ Erreur lors de la mise à jour du statut: {e}")


def update_facture_commentaire(facture_id: int, nouveau_commentaire: str):
    """Mettre à jour le commentaire d'une facture automatiquement"""
    try:
        with Session(engine) as session:
            facture = session.get(Facture, facture_id)
            if facture:
                facture.commentaire_contestation = nouveau_commentaire if nouveau_commentaire else None
                facture.date_traitement = datetime.now()
                session.add(facture)
                session.commit()
                st.success("✅ Commentaire mis à jour")
    except Exception as e:
        st.error(f"❌ Erreur lors de la mise à jour du commentaire: {e}")


def page_groupes():
    """Page de gestion des groupes"""
    st.header("Gestion des Groupes")

    # Formulaire pour créer un nouveau groupe
    st.subheader("Créer un nouveau groupe")
    col1, col2 = st.columns(2)

    with col1:
        nom_groupe = st.text_input("Nom du groupe")
    with col2:
        identifiant_groupe = st.text_input("Identifiant du groupe")

    if st.button("Créer le groupe"):
        if nom_groupe and identifiant_groupe:
            with Session(engine) as session:
                # Vérifier si l'identifiant existe déjà
                existing = session.exec(select(Groupe).where(Groupe.identifiant == identifiant_groupe)).first()

                if existing:
                    st.error("Cet identifiant existe déjà!")
                else:
                    groupe = Groupe(nom=nom_groupe, identifiant=identifiant_groupe)
                    session.add(groupe)
                    session.commit()
                    st.success("✅ Groupe créé avec succès!")
        else:
            st.error("Veuillez remplir tous les champs.")

    # Afficher les groupes existants
    st.subheader("Groupes existants")
    with Session(engine) as session:
        groupes = session.exec(select(Groupe)).all()

        if groupes:
            df_groupes = pd.DataFrame([{"ID": g.id, "Nom": g.nom, "Identifiant": g.identifiant} for g in groupes])
            st.dataframe(df_groupes, use_container_width=True)
        else:
            st.info("Aucun groupe créé pour le moment.")


def page_validation():
    """Page de validation des factures"""
    st.header("Validation des Factures")

    # Afficher un message si on vient d'importer des données
    if "just_imported" in st.session_state and st.session_state.just_imported:
        st.success("🎉 Nouvelles données importées ! Vous pouvez maintenant valider les factures ci-dessous.")
        st.session_state.just_imported = False  # Reset le flag

    # Sélectionner un contrôle
    with Session(engine) as session:
        controles = session.exec(select(ControleCharges, Groupe).join(Groupe)).all()

        if not controles:
            st.warning("Aucun contrôle de charges trouvé. Importez d'abord des données.")
            return

        controle_options = {f"{groupe.nom} - {controle.annee}": controle.id for controle, groupe in controles}

        selected_controle = st.selectbox("Sélectionner un contrôle", options=list(controle_options.keys()))
        controle_id = controle_options[selected_controle]

        # Récupérer les factures
        factures = session.exec(select(Facture).where(Facture.controle_id == controle_id)).all()

        if not factures:
            st.info("Aucune facture trouvée pour ce contrôle.")
            return

        # Afficher les factures sous forme de tableau éditable
        st.subheader("Factures à valider")

        # Filtres
        col1, col2 = st.columns(2)
        with col1:
            statut_filter = st.selectbox("Filtrer par statut", ["Tous", "en_attente", "validee", "contestee"])

        # Filtrer les factures
        factures_filtered = factures
        if statut_filter != "Tous":
            factures_filtered = [f for f in factures if f.statut == statut_filter]

        # Afficher chaque facture
        for i, facture in enumerate(factures_filtered):
            with st.expander(f"Facture {facture.numero_facture} - {facture.montant_comptable}€"):
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.write(f"**Nature:** {facture.nature}")
                    st.write(f"**Code Journal:** {facture.code_journal}")
                    st.write(f"**Compte:** {facture.numero_compte_comptable}")
                    st.write(f"**Libellé:** {facture.libelle_ecriture}")
                    st.write(f"**Référence:** {facture.references_partenaire_facture}")

                with col2:
                    st.selectbox(
                        "Statut",
                        ["en_attente", "validee", "contestee"],
                        index=["en_attente", "validee", "contestee"].index(facture.statut),
                        key=f"statut_{facture.id}",
                        on_change=lambda f_id=facture.id: update_facture_statut(
                            f_id, st.session_state[f"statut_{f_id}"]
                        ),
                    )

                with col3:
                    st.text_area(
                        "Commentaire/Contestation",
                        value=facture.commentaire_contestation or "",
                        key=f"comment_{facture.id}",
                        height=100,
                        on_change=lambda f_id=facture.id: update_facture_commentaire(
                            f_id, st.session_state[f"comment_{f_id}"]
                        ),
                    )

                # Afficher le statut actuel et la dernière modification
                if facture.date_traitement:
                    st.caption(f"Dernière modification: {facture.date_traitement.strftime('%d/%m/%Y %H:%M')}")
                else:
                    st.caption("Non traité")


def page_dashboard():
    """Page tableau de bord"""
    st.header("Tableau de Bord")

    with Session(engine) as session:
        # Statistiques générales
        total_groupes = len(session.exec(select(Groupe)).all())
        total_controles = len(session.exec(select(ControleCharges)).all())
        total_factures = len(session.exec(select(Facture)).all())

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Groupes", total_groupes)
        with col2:
            st.metric("Contrôles", total_controles)
        with col3:
            st.metric("Factures", total_factures)

        # Répartition par statut
        factures = session.exec(select(Facture)).all()
        if factures:
            statuts = {}
            montants = {}

            for facture in factures:
                statut = facture.statut
                statuts[statut] = statuts.get(statut, 0) + 1
                montants[statut] = montants.get(statut, 0) + facture.montant_comptable

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Répartition par statut (nombre)")
                df_statuts = pd.DataFrame(list(statuts.items()), columns=["Statut", "Nombre"])
                st.bar_chart(df_statuts.set_index("Statut"))

            with col2:
                st.subheader("Répartition par statut (montants)")
                df_montants = pd.DataFrame(list(montants.items()), columns=["Statut", "Montant"])
                st.bar_chart(df_montants.set_index("Statut"))


if __name__ == "__main__":
    main()
