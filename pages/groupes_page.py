import pandas as pd
import streamlit as st
from sqlmodel import Session, select

from models import Groupe, engine


def main():
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


if __name__ == "__main__":
    main()
