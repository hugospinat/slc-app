import re
from typing import Any, List

import pandas as pd
import streamlit as st
from sqlmodel import Session, select


# Utiliser le cache Streamlit pour éviter les reimports multiples
@st.cache_resource
def import_models():
    """Import des modèles avec cache pour éviter les redéfinitions SQLAlchemy"""
    from slc_app.models import (
        ControleCharges,
        Facture,
        Fournisseur,
        Groupe,
        RegleExtractionChamp,
        TypeFacture,
        engine,
    )

    return ControleCharges, Facture, Fournisseur, Groupe, RegleExtractionChamp, TypeFacture, engine


# Import avec cache
ControleCharges, Facture, Fournisseur, Groupe, RegleExtractionChamp, TypeFacture, engine = (
    import_models()
)


def creer_dataframe_factures(factures: List[Any]) -> pd.DataFrame:
    """Crée un DataFrame à partir d'une liste de factures"""
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


def tester_regex(factures: List[Any], champ: str, regex: str) -> pd.DataFrame:
    """Teste un regex sur une liste de factures"""
    if not regex:  # Si regex vide, retourner toutes les factures
        return creer_dataframe_factures(factures)

    try:
        pattern = re.compile(regex)
        factures_filtrees = [f for f in factures if pattern.search(getattr(f, champ, "") or "")]
        return creer_dataframe_factures(factures_filtrees)
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
                nouveau_type = st.selectbox(
                    "Type de facture", options=[t.value for t in TypeFacture]
                )

            with col2:
                champs_detection = [
                    "libelle_ecriture",
                    "references_partenaire_facture",
                    "numero_facture",
                ]
                champ_detection = st.selectbox("Champ de détection", options=champs_detection)
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
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de l'enregistrement : {str(e)}")

    # Section Test Regex
    st.subheader("Test de détection")

    with Session(engine) as session:
        # Sélection du contrôle
        col1, col2 = st.columns(2)
        with col1:
            annees = session.exec(select(ControleCharges.annee).distinct()).all()
            if not annees:
                st.warning("Aucune année de contrôle disponible")
                return
            annee = st.selectbox("Année", options=sorted(annees, reverse=True))

        with col2:
            groupes = session.exec(
                select(Groupe).join(ControleCharges).where(ControleCharges.annee == annee)
            ).all()
            if not groupes:
                st.warning("Aucun groupe disponible pour cette année")
                return
            groupe_dict = {f"{g.nom} ({g.identifiant})": g.id for g in groupes}
            groupe_id = st.selectbox("Groupe", options=list(groupe_dict.keys()))

        # Récupération des factures du contrôle
        controle = session.exec(
            select(ControleCharges).where(
                ControleCharges.groupe_id == groupe_dict[groupe_id], ControleCharges.annee == annee
            )
        ).first()

        if not controle:
            st.warning("Aucun contrôle trouvé")
            return

        factures = []
        for poste in controle.postes:
            factures.extend(poste.factures)

        if not factures:
            st.info("Aucune facture trouvée pour ce contrôle")
            return

        # Interface de test regex
        fournisseurs = session.exec(select(Fournisseur)).all()
        if not fournisseurs:
            st.warning("Aucun fournisseur configuré")
            return

        fournisseur_nom = st.selectbox(
            "Fournisseur à tester", options=[f.nom for f in fournisseurs]
        )
        fournisseur_obj = next(f for f in fournisseurs if f.nom == fournisseur_nom)

        champs_detection = ["libelle_ecriture", "references_partenaire_facture", "numero_facture"]
        champ_index = 0
        if fournisseur_obj.champ_detection in champs_detection:
            champ_index = champs_detection.index(fournisseur_obj.champ_detection)

        champ = st.selectbox("Champ à tester", options=champs_detection, index=champ_index)
        regex = st.text_input("Regex à tester", value=fournisseur_obj.regex_detection or "")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Tester le regex"):
                df = tester_regex(factures, champ, regex)
                if not df.empty:
                    st.dataframe(df, use_container_width=True)
                    st.info(f"{len(df)} facture(s) trouvée(s)")
                else:
                    st.info("Aucune facture ne correspond au regex")

        with col2:
            if st.button("Enregistrer la configuration"):
                try:
                    fournisseur_obj.champ_detection = champ
                    fournisseur_obj.regex_detection = regex
                    session.add(fournisseur_obj)
                    session.commit()
                    st.success("✅ Configuration enregistrée")
                except Exception as e:
                    st.error(f"Erreur lors de l'enregistrement : {str(e)}")


if __name__ == "__main__":
    main()
