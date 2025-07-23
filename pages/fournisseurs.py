import re
from typing import List

import pandas as pd
import streamlit as st
from sqlmodel import Session, select

from models import (
    ControleCharges,
    Facture,
    Fournisseur,
    Groupe,
    RegleExtractionChamp,
    TypeFacture,
    clear_registry,
    engine,
)

# Nettoyer les métadonnées avant l'import des modèles
clear_registry()


def tester_regex(factures: List[Facture], champ: str, regex: str) -> pd.DataFrame:
    """Teste un regex sur une liste de factures"""
    if not regex:  # Si regex vide, retourner toutes les factures
        return pd.DataFrame(
            [
                {
                    "Numéro": f.numero_facture,
                    "Montant": f.montant_comptable,
                    "Libellé": f.libelle_ecriture,
                    "Référence": f.references_partenaire_facture,
                }
                for f in factures
            ]
        )

    try:
        pattern = re.compile(regex)
        factures_filtrees = [f for f in factures if pattern.search(getattr(f, champ))]
        return pd.DataFrame(
            [
                {
                    "Numéro": f.numero_facture,
                    "Montant": f.montant_comptable,
                    "Libellé": f.libelle_ecriture,
                    "Référence": f.references_partenaire_facture,
                }
                for f in factures_filtrees
            ]
        )
    except re.error as e:
        st.error(f"Erreur dans l'expression régulière : {str(e)}")
        return pd.DataFrame()


def main():
    st.set_page_config(page_title="Gestion des Fournisseurs", page_icon="🏢", layout="wide")
    st.title("Gestion des Fournisseurs")

    # Section Ajout/Modification fournisseur
    with st.expander("Ajouter un fournisseur", expanded=True):
        with Session(engine) as session:
            col1, col2 = st.columns(2)

            with col1:
                nouveau_nom = st.text_input("Nom du fournisseur")
                nouveau_type = st.selectbox("Type de facture", options=[t.value for t in TypeFacture])

            with col2:
                champ_detection = st.selectbox(
                    "Champ de détection",
                    options=["libelle_ecriture", "references_partenaire_facture", "numero_facture"],
                )
                regex_detection = st.text_input("Expression régulière de détection")

            if st.button("Enregistrer le fournisseur"):
                if not nouveau_nom:
                    st.error("Le nom du fournisseur est obligatoire")
                else:
                    try:
                        fournisseur = Fournisseur(
                            nom=nouveau_nom,
                            type_facture=TypeFacture(nouveau_type),
                            champ_detection=champ_detection,
                            regex_detection=regex_detection,
                        )
                        session.add(fournisseur)
                        session.commit()
                        st.success("✅ Fournisseur enregistré")
                    except Exception as e:
                        st.error(f"Erreur lors de l'enregistrement : {str(e)}")

    # Section Gestion des règles d'extraction
    st.subheader("Règles d'extraction automatique")

    with Session(engine) as session:
        fournisseurs = session.exec(select(Fournisseur)).all()

        if fournisseurs:
            fournisseur_noms = [f.nom for f in fournisseurs]
            fournisseur_selected = st.selectbox(
                "Fournisseur pour les règles", options=fournisseur_noms, key="regle_fournisseur"
            )
            fournisseur_obj = next(f for f in fournisseurs if f.nom == fournisseur_selected)

            with st.expander("Ajouter une règle d'extraction", expanded=False):
                col1, col2 = st.columns(2)

                with col1:
                    table_cible = st.selectbox("Table cible", options=[t.value for t in TypeFacture], key="regle_table")
                    champ_cible = st.text_input(
                        "Champ cible", placeholder="ex: index_debut, date_debut", key="regle_champ"
                    )

                with col2:
                    regex_extraction = st.text_input(
                        "Regex d'extraction", placeholder="ex: Index début:\\s*(\\d+)", key="regle_regex"
                    )
                    description = st.text_input(
                        "Description (optionnel)", placeholder="ex: Extrait l'index de début", key="regle_description"
                    )

                if st.button("Enregistrer la règle", key="save_regle"):
                    if not champ_cible or not regex_extraction:
                        st.error("Le champ cible et la regex sont obligatoires")
                    else:
                        try:
                            if fournisseur_obj.id is not None:
                                regle = RegleExtractionChamp(
                                    fournisseur_id=fournisseur_obj.id,
                                    table_cible=TypeFacture(table_cible),
                                    champ_cible=champ_cible,
                                    regex_extraction=regex_extraction,
                                    description=description,
                                    actif=True,
                                )
                                session.add(regle)
                                session.commit()
                                st.success("✅ Règle d'extraction enregistrée")
                            else:
                                st.error("ID du fournisseur non valide")
                        except Exception as e:
                            st.error(f"Erreur lors de l'enregistrement : {str(e)}")

            # Afficher les règles existantes
            regles = session.exec(
                select(RegleExtractionChamp).where(RegleExtractionChamp.fournisseur_id == fournisseur_obj.id)
            ).all()

            if regles:
                st.write("**Règles existantes :**")
                for regle in regles:
                    with st.expander(
                        f"{regle.table_cible.value}.{regle.champ_cible} - {'✅' if regle.actif else '❌'}"
                    ):
                        col1, col2, col3 = st.columns([2, 1, 1])

                        with col1:
                            st.code(regle.regex_extraction)
                            if regle.description:
                                st.caption(regle.description)

                        with col2:
                            nouveau_statut = st.checkbox("Actif", value=regle.actif, key=f"actif_{regle.id}")
                            if nouveau_statut != regle.actif:
                                regle.actif = nouveau_statut
                                session.add(regle)
                                session.commit()
                                st.rerun()

                        with col3:
                            if st.button("Supprimer", key=f"delete_{regle.id}"):
                                session.delete(regle)
                                session.commit()
                                st.rerun()

    # Section Test Regex
    st.subheader("Test de détection")

    with Session(engine) as session:
        # Sélection du contrôle
        col1, col2 = st.columns(2)
        with col1:
            annees = session.exec(select(ControleCharges.annee).distinct()).all()
            annee = st.selectbox("Année", options=sorted(annees, reverse=True))

        with col2:
            groupes = session.exec(select(Groupe).join(ControleCharges).where(ControleCharges.annee == annee)).all()
            groupe_dict = {f"{g.nom} ({g.identifiant})": g.id for g in groupes}
            groupe_id = st.selectbox("Groupe", options=list(groupe_dict.keys()))

        # Récupération des factures du contrôle
        controle = session.exec(
            select(ControleCharges).where(
                ControleCharges.groupe_id == groupe_dict[groupe_id], ControleCharges.annee == annee
            )
        ).first()

        if controle:
            factures = []
            for poste in controle.postes:
                factures.extend(poste.factures)

            # Interface de test regex
            fournisseurs = session.exec(select(Fournisseur)).all()
            fournisseur = st.selectbox("Fournisseur à tester", options=[f.nom for f in fournisseurs])

            if fournisseur:
                f = next(f for f in fournisseurs if f.nom == fournisseur)
                champ = st.selectbox(
                    "Champ à tester",
                    options=["libelle_ecriture", "references_partenaire_facture", "numero_facture"],
                    key="test_champ",
                    index=["libelle_ecriture", "references_partenaire_facture", "numero_facture"].index(
                        f.champ_detection
                    ),
                )
                regex = st.text_input("Regex à tester", value=f.regex_detection or "")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Tester le regex"):
                        df = tester_regex(factures, champ, regex)
                        if not df.empty:
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.info("Aucune facture ne correspond au regex")

                with col2:
                    if st.button("Enregistrer la configuration"):
                        try:
                            f.champ_detection = champ
                            f.regex_detection = regex
                            session.add(f)
                            session.commit()
                            st.success("✅ Configuration enregistrée")
                        except Exception as e:
                            st.error(f"Erreur lors de l'enregistrement : {str(e)}")


if __name__ == "__main__":
    main()
