import base64

import pandas as pd
import streamlit as st
from sqlmodel import Session, SQLModel, select

from models import ControleCharges, Facture, Groupe, Poste, engine
from utils.factures import update_facture_commentaire, update_facture_statut
from utils.postes import update_rapport_poste

# Nettoyer les métadonnées avant l'import des modèles
SQLModel.metadata.clear()


def afficher_pdf(pdf_bytes):
    """Affiche un PDF à partir de bytes"""
    if pdf_bytes:
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="800px" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.warning("Pas de PDF disponible pour cette facture")


def main():
    st.set_page_config(page_title="Contrôle des Charges", page_icon="📊", layout="wide")

    # Sélection du groupe et de l'année dans la barre latérale
    with Session(engine) as session:
        # Récupérer les années disponibles
        annees_disponibles = session.exec(select(ControleCharges.annee).distinct()).all()
        annees_disponibles = sorted(set(annees_disponibles), reverse=True)

        if not annees_disponibles:
            st.sidebar.warning("Aucune année disponible.")
            st.session_state.selected_annee = None
            st.session_state.selected_groupe_id = None
            st.session_state.controle_id = None
            return

        # Sélection de l'année
        annee = st.sidebar.selectbox("Année", options=annees_disponibles, key="sidebar_annee")
        st.session_state.selected_annee = annee

        # Récupérer les groupes pour l'année sélectionnée avec jointure correcte
        groupes_annee = session.exec(select(Groupe).join(ControleCharges).where(ControleCharges.annee == annee)).all()

        if not groupes_annee:
            st.sidebar.warning("Aucun groupe disponible pour cette année.")
            st.session_state.selected_groupe_id = None
            st.session_state.controle_id = None
            return

        # Sélection du groupe
        groupe_options = {f"{g.nom} ({g.identifiant})": g.id for g in groupes_annee}
        selected_groupe = st.sidebar.selectbox("Groupe", options=list(groupe_options.keys()), key="sidebar_groupe")
        groupe_id = groupe_options[selected_groupe]
        st.session_state.selected_groupe_id = groupe_id

        # Récupérer le contrôle
        controle = session.exec(
            select(ControleCharges).where(ControleCharges.groupe_id == groupe_id, ControleCharges.annee == annee)
        ).first()

        if not controle:
            st.sidebar.warning(f"⚠️ Contrôle non existant pour {selected_groupe} - {annee}")
            st.session_state.controle_id = None
            return

        st.session_state.controle_id = controle.id

    controle_id = st.session_state.get("controle_id")

    if not controle_id:
        st.warning("Aucun contrôle sélectionné. Veuillez choisir un groupe et une année dans la barre latérale.")
        return

    with Session(engine) as session:
        controle = session.get(ControleCharges, controle_id)
        groupe = session.get(Groupe, controle.groupe_id) if controle else None

        if not controle or not groupe:
            st.error("Le contrôle sélectionné n'existe pas. Veuillez en sélectionner un autre.")
            return

        postes = session.exec(select(Poste).where(Poste.controle_id == controle_id)).all()

        if not postes:
            st.info("Aucun poste trouvé pour ce contrôle.")
            return

        col1, col2 = st.columns(2)

        with col1:
            poste_options = {f"{poste.code} - {poste.nom}": poste.id for poste in postes}
            poste_options["Tout"] = None  # Ajouter l'option "Tout"

            # Garder l'ancien poste_id pour détecter le changement
            ancien_poste_id = st.session_state.get("current_poste_id")

            selected_poste_name = st.selectbox("Sélectionner un poste", options=["Tout"] + list(poste_options.keys()))
            poste_id = poste_options[selected_poste_name]

            # Si le poste a changé, réinitialiser la sélection du PDF
            if ancien_poste_id != poste_id:
                st.session_state.selected_facture_id = None
                st.session_state.current_poste_id = poste_id

        with col2:
            statut_filter = st.selectbox("Filtrer par statut", ["Tous", "en_attente", "validee", "contestee"])

        if poste_id is None:  # Option "Tout" sélectionnée
            # Récupérer toutes les factures pour ce contrôle
            factures = []
            for poste in postes:
                factures.extend(session.exec(select(Facture).where(Facture.poste_id == poste.id)).all())
            poste_actuel = None
        else:
            poste_actuel = session.get(Poste, poste_id)
            factures = session.exec(select(Facture).where(Facture.poste_id == poste_id)).all()

        if not factures:
            st.info("Aucune facture trouvée.")
            st.stop()

        # Filtrage par statut
        if statut_filter != "Tous":
            factures_filtered = [f for f in factures if f.statut == statut_filter]
        else:
            factures_filtered = factures

        factures_data = []
        for f in factures_filtered:
            factures_data.append(
                {
                    "ID": f.id,
                    "Numéro": f.numero_facture,
                    "Montant": f.montant_comptable,
                    "Journal": f.code_journal,
                    "Compte": f.numero_compte_comptable,
                    "Libellé": f.libelle_ecriture,
                    "Référence": f.references_partenaire_facture,
                    "Statut": f.statut,
                    "Commentaire": f.commentaire_contestation or "",
                }
            )

        # Initialiser la sélection si nécessaire
        if "selected_facture_id" not in st.session_state:
            st.session_state.selected_facture_id = None

        # Diviser l'écran en deux colonnes principales
        col_table, col_pdf = st.columns([1, 1])  # Ratio 1:1

        with col_table:
            if factures_data:
                df_factures = pd.DataFrame(factures_data)
                selected_rows = st.data_editor(
                    df_factures,
                    column_config={
                        "ID": st.column_config.NumberColumn("ID", disabled=True),
                        "Numéro": st.column_config.TextColumn("Numéro", disabled=True),
                        "Montant": st.column_config.NumberColumn(
                            "Montant €", format="%.2f", disabled=True, width="small"
                        ),
                        "Journal": st.column_config.TextColumn("Journal", disabled=True),
                        "Compte": st.column_config.TextColumn("Compte", disabled=True),
                        "Libellé": st.column_config.TextColumn("Libellé", disabled=True),
                        "Référence": st.column_config.TextColumn("Référence", disabled=True),
                        "Statut": st.column_config.SelectboxColumn(
                            "Statut", options=["en_attente", "validee", "contestee"], required=True, width="small"
                        ),
                        "Commentaire": st.column_config.TextColumn("Commentaire", disabled=False, width="large"),
                    },
                    column_order=["Numéro", "Montant", "Journal", "Libellé", "Statut", "Commentaire"],
                    hide_index=True,
                    use_container_width=True,
                    height=800,
                    key="factures_editor",
                )

                # Gérer les modifications
                if selected_rows is not None:
                    df_selected = pd.DataFrame(selected_rows)
                    for idx in df_selected.index:
                        row = df_selected.loc[idx]
                        orig_row = df_factures.loc[df_factures["ID"] == row["ID"]].iloc[0]

                        if row["Statut"] != orig_row["Statut"]:
                            update_facture_statut(row["ID"], row["Statut"])
                            st.toast(f"✅ Statut mis à jour pour la facture {row['Numéro']}")

                        if row["Commentaire"] != orig_row["Commentaire"]:
                            update_facture_commentaire(row["ID"], row["Commentaire"])
                            st.toast(f"✅ Commentaire mis à jour pour la facture {row['Numéro']}")

        # Afficher le PDF dans la colonne de droite
        with col_pdf:
            # Section PDF
            with Session(engine) as session:
                factures_avec_pdf = []
                for f in factures_data:
                    facture = session.get(Facture, f["ID"])
                    if facture and facture.pdf_facture_contenu:
                        factures_avec_pdf.append(f)

                if factures_avec_pdf:  # Si des PDFs existent
                    factures_menu = {f"Facture {f['Numéro']} - {f['Montant']:.2f}€": f["ID"] for f in factures_avec_pdf}

                    # Affichage du PDF
                    if st.session_state.selected_facture_id:
                        facture = session.get(Facture, st.session_state.selected_facture_id)
                        if facture and facture.pdf_facture_contenu:
                            afficher_pdf(facture.pdf_facture_contenu)

                    # Navigation
                    st.markdown("### Navigation")
                    col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])

                    with col_nav1:
                        if st.button("⬅️ Précédent"):
                            if st.session_state.selected_facture_id:
                                current_index = list(factures_menu.values()).index(st.session_state.selected_facture_id)
                                if current_index > 0:
                                    st.session_state.selected_facture_id = list(factures_menu.values())[
                                        current_index - 1
                                    ]

                    with col_nav2:
                        try:
                            default_index = (
                                list(factures_menu.values()).index(st.session_state.selected_facture_id)
                                if st.session_state.selected_facture_id in factures_menu.values()
                                else 0
                            )
                        except ValueError:
                            default_index = 0

                        selected_facture = st.selectbox(
                            label="Sélectionner une facture",
                            options=list(factures_menu.keys()),
                            key="facture_selectbox",
                            index=default_index,
                            label_visibility="collapsed",
                        )
                        st.session_state.selected_facture_id = factures_menu[selected_facture]

                    with col_nav3:
                        if st.button("Suivant ➡️"):
                            if st.session_state.selected_facture_id:
                                current_index = list(factures_menu.values()).index(st.session_state.selected_facture_id)
                                if current_index < len(factures_menu) - 1:
                                    st.session_state.selected_facture_id = list(factures_menu.values())[
                                        current_index + 1
                                    ]
                else:
                    st.warning("Aucune facture avec PDF disponible pour ce poste")

        # Continuer avec l'affichage des statistiques et du rapport
        st.markdown("---")

        if poste_id is None:  # Option "Tout" sélectionnée
            st.subheader("Remarque Globale")
            remarque_globale = controle.remarque_globale or ""
            nouvelle_remarque = st.text_area("Éditer la remarque globale", value=remarque_globale, height=400)

            if st.button("Enregistrer la remarque globale"):
                with Session(engine) as session:
                    controle_maj = session.get(ControleCharges, controle_id)
                    if controle_maj is not None:
                        controle_maj.remarque_globale = nouvelle_remarque
                        session.commit()
                        st.success("✅ Remarque globale mise à jour")
                    else:
                        st.error("Erreur : Contrôle introuvable lors de la mise à jour de la remarque globale.")

            # Remplacer l'aperçu par les statistiques du groupe
            st.subheader("Statistiques du groupe")
            montant_total = sum(f.montant_comptable for f in factures)
            nb_validees = len([f for f in factures if f.statut == "validee"])
            nb_contestees = len([f for f in factures if f.statut == "contestee"])
            nb_en_attente = len([f for f in factures if f.statut == "en_attente"])

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total", f"{montant_total:.2f}€")
            col2.metric("Validées", nb_validees)
            col3.metric("Contestées", nb_contestees)
            col4.metric("En attente", nb_en_attente)

            st.markdown(remarque_globale)
        elif poste_actuel is not None:
            st.subheader(f"Rapport de contrôle - {poste_actuel.nom}")

            rapport_actuel = poste_actuel.rapport or ""
            nouveau_rapport = st.text_area("Éditer le rapport", value=rapport_actuel, height=400)

            if st.button("Enregistrer le rapport"):
                if poste_id is not None:
                    update_rapport_poste(poste_id, nouveau_rapport)

            st.subheader("Aperçu du rapport")
            st.markdown(nouveau_rapport)

            montant_total = sum(f.montant_comptable for f in factures)
            nb_validees = len([f for f in factures if f.statut == "validee"])
            nb_contestees = len([f for f in factures if f.statut == "contestee"])
            nb_en_attente = len([f for f in factures if f.statut == "en_attente"])

            st.subheader("Statistiques du poste")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total", f"{montant_total:.2f}€")
            col2.metric("Validées", nb_validees)
            col3.metric("Contestées", nb_contestees)
            col4.metric("En attente", nb_en_attente)
        else:
            st.warning("Aucun poste sélectionné ou le poste n'existe pas.")


if __name__ == "__main__":
    main()
