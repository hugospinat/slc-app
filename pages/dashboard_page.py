import pandas as pd
import streamlit as st
from sqlmodel import Session, select

from models import ControleCharges, Facture, Groupe, clear_registry, engine

# Nettoyer les métadonnées avant l'import des modèles
clear_registry()


def main():
    """Page tableau de bord"""
    st.header("Tableau de Bord")

    with Session(engine) as session:
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
