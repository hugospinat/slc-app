from datetime import datetime

import pandas as pd
import streamlit as st
from sqlmodel import Session, select

from models import ControleCharges, Facture, FactureElectricite, Groupe, clear_registry, engine

# Nettoyer les métadonnées avant l'import des modèles
clear_registry()


def main():
    st.set_page_config(page_title="Factures Électricité", page_icon="⚡", layout="wide")
    st.title("Factures d'électricité")

    # Interface de sélection Groupe/Année
    with Session(engine) as session:
        # Sélection de l'année
        annees = session.exec(select(ControleCharges.annee).distinct()).all()
        annee = st.sidebar.selectbox("Année", options=sorted(annees, reverse=True))

        # Sélection du groupe
        groupes = session.exec(select(Groupe).join(ControleCharges).where(ControleCharges.annee == annee)).all()
        groupe_dict = {f"{g.nom} ({g.identifiant})": g.id for g in groupes}
        groupe_selected = st.sidebar.selectbox("Groupe", options=list(groupe_dict.keys()))
        groupe_id = groupe_dict[groupe_selected]

        # Récupérer le contrôle
        controle = session.exec(
            select(ControleCharges).where(ControleCharges.groupe_id == groupe_id, ControleCharges.annee == annee)
        ).first()

        if not controle:
            st.warning("Aucun contrôle trouvé pour cette période.")
            return

        # Récupérer toutes les factures d'électricité via les relations
        factures_elec = []
        for poste in controle.postes:
            for facture in poste.factures:
                if facture.details_electricite:
                    factures_elec.append(facture)

        if not factures_elec:
            st.info("Aucune facture d'électricité trouvée pour cette période.")
            return

        # Préparer les données pour le tableau
        factures_data = []
        for facture in factures_elec:
            details = facture.details_electricite
            factures_data.append(
                {
                    "ID": facture.id,
                    "Numéro": facture.numero_facture,
                    "Montant": facture.montant_comptable,
                    "Journal": facture.code_journal,
                    "Compte": facture.numero_compte_comptable,
                    "Libellé": facture.libelle_ecriture,
                    "Référence": facture.references_partenaire_facture,
                    "Fournisseur": facture.fournisseur.nom if facture.fournisseur else "Non détecté",
                    "Statut": facture.statut,
                    "Commentaire": facture.commentaire_contestation or "",
                    "Index Début": details.index_debut if details and details.index_debut is not None else 0.0,
                    "Index Fin": details.index_fin if details and details.index_fin is not None else 0.0,
                    "Date Début": (
                        details.date_debut.date() if details and details.date_debut else datetime.now().date()
                    ),
                    "Date Fin": details.date_fin.date() if details and details.date_fin else datetime.now().date(),
                }
            )

        if factures_data:
            df_factures = pd.DataFrame(factures_data)

            st.subheader(f"Factures d'électricité - {len(factures_data)} factures trouvées")

            # Tableau éditable avec toutes les colonnes
            selected_rows = st.data_editor(
                df_factures,
                column_config={
                    "ID": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                    "Numéro": st.column_config.TextColumn("Numéro", disabled=True, width="medium"),
                    "Montant": st.column_config.NumberColumn("Montant €", format="%.2f", disabled=True, width="small"),
                    "Journal": st.column_config.TextColumn("Journal", disabled=True, width="small"),
                    "Compte": st.column_config.TextColumn("Compte", disabled=True, width="medium"),
                    "Libellé": st.column_config.TextColumn("Libellé", disabled=True, width="large"),
                    "Référence": st.column_config.TextColumn("Référence", disabled=True, width="medium"),
                    "Fournisseur": st.column_config.TextColumn("Fournisseur", disabled=True, width="medium"),
                    "Statut": st.column_config.SelectboxColumn(
                        "Statut", options=["en_attente", "validee", "contestee"], required=True, width="small"
                    ),
                    "Commentaire": st.column_config.TextColumn("Commentaire", disabled=False, width="large"),
                    "Index Début": st.column_config.NumberColumn(
                        "Index Début", format="%.1f", disabled=False, width="medium"
                    ),
                    "Index Fin": st.column_config.NumberColumn(
                        "Index Fin", format="%.1f", disabled=False, width="medium"
                    ),
                    "Date Début": st.column_config.DateColumn("Date Début", disabled=False, width="medium"),
                    "Date Fin": st.column_config.DateColumn("Date Fin", disabled=False, width="medium"),
                },
                column_order=[
                    "Numéro",
                    "Montant",
                    "Journal",
                    "Libellé",
                    "Fournisseur",
                    "Statut",
                    "Commentaire",
                    "Index Début",
                    "Index Fin",
                    "Date Début",
                    "Date Fin",
                ],
                hide_index=True,
                use_container_width=True,
                height=600,
                key="factures_electricite_editor",
            )

            # Gérer les modifications
            if selected_rows is not None:
                df_selected = pd.DataFrame(selected_rows)
                for idx in df_selected.index:
                    row = df_selected.loc[idx]
                    orig_row = df_factures.loc[df_factures["ID"] == row["ID"]].iloc[0]

                    # Vérifier s'il y a des changements
                    changes_detected = False

                    # Changements dans la facture
                    if row["Statut"] != orig_row["Statut"]:
                        changes_detected = True
                    if row["Commentaire"] != orig_row["Commentaire"]:
                        changes_detected = True

                    # Changements dans les détails électricité
                    if row["Index Début"] != orig_row["Index Début"]:
                        changes_detected = True
                    if row["Index Fin"] != orig_row["Index Fin"]:
                        changes_detected = True
                    if row["Date Début"] != orig_row["Date Début"]:
                        changes_detected = True
                    if row["Date Fin"] != orig_row["Date Fin"]:
                        changes_detected = True

                    if changes_detected:
                        # Mettre à jour en base de données
                        with Session(engine) as update_session:
                            try:
                                # Mise à jour facture
                                facture_db = update_session.get(Facture, row["ID"])
                                if facture_db:
                                    facture_db.statut = row["Statut"]
                                    facture_db.commentaire_contestation = row["Commentaire"]

                                    # Mise à jour détails électricité
                                    details_db = update_session.exec(
                                        select(FactureElectricite).where(FactureElectricite.facture_id == row["ID"])
                                    ).first()

                                    if details_db:
                                        details_db.index_debut = float(row["Index Début"])
                                        details_db.index_fin = float(row["Index Fin"])
                                        details_db.date_debut = datetime.combine(row["Date Début"], datetime.min.time())
                                        details_db.date_fin = datetime.combine(row["Date Fin"], datetime.min.time())

                                    update_session.commit()
                                    st.toast(f"✅ Facture {row['Numéro']} mise à jour")

                            except Exception as e:
                                st.error(f"❌ Erreur lors de la mise à jour de la facture {row['Numéro']}: {e}")
                                update_session.rollback()

            # Statistiques
            st.markdown("---")
            st.subheader("Statistiques")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_montant = sum(f["Montant"] for f in factures_data)
                st.metric("Montant Total", f"{total_montant:.2f}€")

            with col2:
                nb_validees = len([f for f in factures_data if f["Statut"] == "validee"])
                st.metric("Validées", nb_validees)

            with col3:
                nb_contestees = len([f for f in factures_data if f["Statut"] == "contestee"])
                st.metric("Contestées", nb_contestees)

            with col4:
                nb_en_attente = len([f for f in factures_data if f["Statut"] == "en_attente"])
                st.metric("En attente", nb_en_attente)


if __name__ == "__main__":
    main()
