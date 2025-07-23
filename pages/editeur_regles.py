import re
from typing import Dict, List

import pandas as pd
import streamlit as st
from sqlmodel import Session, select


# Utiliser le cache Streamlit pour éviter les reimports multiples
@st.cache_resource
def import_models():
    """Import des modèles avec cache pour éviter les redéfinitions SQLAlchemy"""
    from models import Facture, Fournisseur, RegleExtractionChamp, TypeFacture, engine

    return Facture, Fournisseur, RegleExtractionChamp, TypeFacture, engine


@st.cache_resource
def import_utils():
    """Import des utilitaires avec cache"""
    from utils.extraction_champs import tester_regle_extraction

    return tester_regle_extraction


# Import avec cache
Facture, Fournisseur, RegleExtractionChamp, TypeFacture, engine = import_models()
tester_regle_extraction = import_utils()


def obtenir_champs_modele(type_facture: str) -> List[str]:
    """Extrait les noms des champs depuis les modèles SQLModel"""
    # Import dynamique des modèles selon le type
    if type_facture == "electricite":
        from models import FactureElectricite

        modele = FactureElectricite
    elif type_facture == "facture":
        from models import Facture

        modele = Facture
    else:
        return []

    champs = list(modele.model_fields.keys())
    champs_exclus = {"id", "created_at", "updated_at", "fournisseur_id", "controle_charges_id"}
    champs_filtres = [champ for champ in champs if champ not in champs_exclus]
    return sorted(champs_filtres)


def obtenir_champs_fusionnes(type_facture: str) -> List[str]:
    """Retourne la liste fusionnée des champs Facture + type spécialisé si applicable"""
    champs = set(obtenir_champs_modele("facture"))
    if type_facture != "facture":
        champs.update(obtenir_champs_modele(type_facture))
    return sorted(champs)


def display_matches_from_regles(regles: List[RegleExtractionChamp], texte: str) -> None:  # type: ignore[reportInvalidTypeForm]
    """Teste toutes les règles sur un texte et affiche les résultats"""
    matches = []

    for regle in regles:
        if not regle.actif:
            continue

        try:
            pattern = re.compile(regle.regex_extraction, re.IGNORECASE | re.MULTILINE)
            for match in pattern.finditer(texte):
                valeur = match.group(1) if match.groups() else match.group(0)
                matches.append(
                    {
                        "start": match.start(),
                        "end": match.end(),
                        "valeur": valeur,
                        "description": f"{regle.table_cible.value}.{regle.champ_cible}",
                        "regle_id": regle.id,
                    }
                )
        except re.error:
            continue

    # Afficher les résultats
    disply_matches(texte, matches)


def disply_matches(texte: str, matches: List[Dict]) -> None:
    """Affiche le texte avec les matches surlignés en utilisant les fonctionnalités natives de Streamlit"""
    if not matches:
        st.warning("Aucune correspondance trouvée dans le texte.")
        return

    # Créer le DataFrame des résultats avec contexte
    resultats_avec_contexte = []
    for match in matches:
        # Extraire le contexte autour du match (60 caractères avant/après)
        start, end = match["start"], match["end"]
        contexte_debut = max(0, start - 60)
        contexte_fin = min(len(texte), end + 60)

        avant = texte[contexte_debut:start].strip()
        apres = texte[end:contexte_fin].strip()

        resultats_avec_contexte.append(
            {
                "Champ": match["description"],
                "Match": match["valeur"],
                "Contexte Avant": avant[-60:] if len(avant) > 60 else avant,
                "Contexte Après": apres[:60] if len(apres) > 60 else apres,
                "Position": f"{match['start']}-{match['end']}",
            }
        )

    df_matches = pd.DataFrame(resultats_avec_contexte)

    # Afficher le DataFrame
    st.dataframe(df_matches, use_container_width=True)
    st.success(f"✅ {len(matches)} correspondances trouvées")


def creer_regle_temporaire(regex: str, description: str = "Test personnalisé") -> RegleExtractionChamp:  # type: ignore
    return RegleExtractionChamp(
        fournisseur_id=0,
        table_cible=TypeFacture.FACTURE,
        champ_cible="test_personnalise",
        regex_extraction=regex,
        description=description,
        actif=True,
    )


def main():
    st.set_page_config(page_title="Éditeur de Règles d'Extraction", page_icon="🔍", layout="wide")

    with Session(engine) as session:
        # Sélection du fournisseur
        fournisseurs = session.exec(select(Fournisseur)).all()

        if not fournisseurs:
            st.warning("Aucun fournisseur trouvé. Veuillez d'abord créer des fournisseurs.")
            return

        fournisseur_options = {f"{f.nom} ({f.type_facture.value})": f.id for f in fournisseurs}
        fournisseur_selected = st.sidebar.selectbox(
            "Sélectionner un fournisseur", options=list(fournisseur_options.keys())
        )
        fournisseur_id = fournisseur_options[fournisseur_selected]
        fournisseur = session.get(Fournisseur, fournisseur_id)

        st.sidebar.markdown("---")
        if fournisseur is not None:
            st.sidebar.markdown(f"**Fournisseur :** {fournisseur.nom}")
            st.sidebar.markdown(f"**Type :** {fournisseur.type_facture.value}")
        else:
            st.sidebar.warning("Aucun fournisseur sélectionné.")

        # Récupération des règles existantes
        regles = session.exec(
            select(RegleExtractionChamp)
            .where(RegleExtractionChamp.fournisseur_id == fournisseur_id)
            .order_by(RegleExtractionChamp.table_cible, RegleExtractionChamp.champ_cible)
        ).all()

        # Récupérer les factures de ce fournisseur avec texte brut
        factures_test = session.exec(select(Facture).where(Facture.fournisseur_id == fournisseur_id).limit(20)).all()

        if factures_test:
            facture_options = {f"{f.numero_facture} - {f.montant_comptable}€": f for f in factures_test}
            facture_selected = st.selectbox("Facture de test", options=list(facture_options.keys()))
            facture_test = facture_options[facture_selected]
            texte_test = facture_test.texte_brut_pdf or ""
        else:
            st.warning("Aucune facture avec texte brut trouvée pour ce fournisseur.")
            texte_test = st.text_area("Texte de test manuel", height=200, placeholder="Collez ici un texte de test...")

        # Affichage du texte brut
        if texte_test:
            with st.container(height=450, border=True):
                st.text(texte_test)

        if not texte_test:
            st.stop()

        # Variable pour stocker les règles à tester
        regles_a_tester = None

        # Première ligne : Gestion des règles et Ajout de nouvelle règle
        col_gestion, col_ajout = st.columns([1, 1])

        with col_gestion:
            st.subheader("⚙️ Gestion des Règles")

            # Affichage des règles existantes
            if regles:
                for regle in regles:
                    with st.expander(
                        f"{'✅' if regle.actif else '❌'} {regle.table_cible.value}.{regle.champ_cible}", expanded=False
                    ):
                        # Affichage des informations
                        st.code(regle.regex_extraction, language="regex")
                        if regle.description:
                            st.caption(regle.description)

                        # Contrôles d'édition
                        col1, col2, col3 = st.columns([2, 1, 1])

                        with col1:
                            nouveau_regex = st.text_input(
                                "Regex", value=regle.regex_extraction, key=f"regex_{regle.id}"
                            )

                        with col2:
                            nouveau_actif = st.checkbox("Actif", value=regle.actif, key=f"actif_{regle.id}")

                        with col3:
                            if st.button("💾", help="Sauvegarder", key=f"save_{regle.id}"):
                                regle.regex_extraction = nouveau_regex
                                regle.actif = nouveau_actif
                                session.add(regle)
                                session.commit()
                                st.success("Sauvegardé!")
                                st.rerun()

                            if st.button("🗑️", help="Supprimer", key=f"delete_{regle.id}"):
                                session.delete(regle)
                                session.commit()
                                st.success("Supprimé!")
                                st.rerun()

                        # Test de cette règle spécifique
                        if st.button("🧪 Tester cette règle", key=f"test_{regle.id}"):
                            if fournisseur_id is not None:
                                test_result = tester_regle_extraction(fournisseur_id, texte_test, nouveau_regex)
                                if test_result:
                                    st.success(f"✅ Extraction: `{test_result}`")
                                else:
                                    st.error("❌ Aucune correspondance trouvée")
                            else:
                                st.error("❌ Impossible de tester la règle : fournisseur_id est manquant.")

        with col_ajout:
            st.subheader("➕ Ajouter une nouvelle règle")

            # On déduit automatiquement la table cible à partir du type du fournisseur sélectionné
            type_table_fournisseur = fournisseur.type_facture.value if fournisseur else "facture"
            champs_disponibles = obtenir_champs_fusionnes(type_table_fournisseur)

            with st.form("nouvelle_regle", clear_on_submit=True):
                nouveau_champ = st.selectbox(
                    "Champ cible",
                    options=champs_disponibles,
                    index=0,
                    key=f"champ_cible_select_{type_table_fournisseur}_{len(champs_disponibles)}",
                )

                nouveau_regex_form = st.text_input("Regex d'extraction", placeholder="ex: numero.*?(\\d+)")
                nouvelle_description = st.text_input("Description (optionnel)")

                if st.form_submit_button("Ajouter la règle"):
                    if nouveau_champ and nouveau_regex_form:
                        if fournisseur_id is None:
                            st.error("❌ Impossible d'ajouter la règle : fournisseur_id est manquant.")
                        else:
                            try:
                                re.compile(nouveau_regex_form)
                                # Déduire la table cible selon le champ choisi
                                if nouveau_champ in obtenir_champs_modele("facture"):
                                    table_cible = TypeFacture.FACTURE
                                else:
                                    if fournisseur is not None:
                                        table_cible = fournisseur.type_facture
                                    else:
                                        st.error(
                                            "❌ Impossible de déterminer la table cible : fournisseur est manquant."
                                        )
                                        st.stop()
                                nouvelle_regle = RegleExtractionChamp(
                                    fournisseur_id=fournisseur_id,
                                    table_cible=table_cible,
                                    champ_cible=nouveau_champ,
                                    regex_extraction=nouveau_regex_form,
                                    description=nouvelle_description,
                                    actif=True,
                                )
                                session.add(nouvelle_regle)
                                session.commit()
                                st.success("✅ Règle ajoutée!")
                                st.rerun()
                            except re.error as e:
                                st.error(f"❌ Erreur dans la regex: {e}")
                            except Exception as e:
                                st.error(f"❌ Erreur: {e}")
                    else:
                        st.error("Le champ et la regex sont obligatoires")

        # Deuxième ligne : Tests
        st.markdown("---")

        col_test_regles, col_test_custom = st.columns([1, 1])

        with col_test_regles:
            st.subheader("🔍 Test toutes les règles actives")

            # Tester toutes les règles actives
            if st.button("🧪 Tester toutes les règles actives", use_container_width=True):
                regles_a_tester = list(regles)

        with col_test_custom:
            st.subheader("🔧 Test de regex personnalisée")
            # Utiliser un formulaire pour éviter les mises à jour automatiques
            with st.form("test_regex_form"):
                regex_test = st.text_input(
                    "Regex à tester",
                    placeholder="ex: Index début.*?(\\d+)",
                    help="Saisissez votre regex et cliquez sur 'Tester' pour l'évaluer",
                )
                bouton_tester = st.form_submit_button("🧪 Tester cette regex", use_container_width=True)

                if bouton_tester and regex_test:
                    # Créer une règle temporaire pour le test
                    regle_temporaire = creer_regle_temporaire(regex_test)

                    regles_a_tester = [regle_temporaire]

                elif bouton_tester and not regex_test:
                    st.error("Veuillez saisir une regex avant de tester")

        # Section des résultats (toute la largeur)
        st.markdown("---")
        st.subheader("📊 Résultats du dernier test")

        if regles_a_tester is not None:
            display_matches_from_regles(regles_a_tester, texte_test)
        else:
            st.info("Cliquez sur un des boutons de test ci-dessus pour voir les résultats.")

        # Section d'aide
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 💡 Aide Regex")

            with st.expander("Exemples utiles", expanded=False):
                st.markdown(
                    """
**Nombres:**
- `\\d+` : Un ou plusieurs chiffres
- `\\d{1,3}` : 1 à 3 chiffres
- `\\d+\\.\\d+` : Nombre décimal

**Dates:**
- `\\d{2}/\\d{2}/\\d{4}` : Format DD/MM/YYYY
- `(\\d{2}/\\d{2}/\\d{4})` : Capture la date

**Texte:**
- `.*?` : N'importe quel caractère (non-gourmand)
- `\\s+` : Un ou plusieurs espaces
- `[A-Z]+` : Lettres majuscules uniquement

**Groupes de capture:**
- `(.+?)` : Capture tout entre parenthèses
- `Index:\\s*(\\d+)` : Capture le nombre après "Index:"
                    """
                )


if __name__ == "__main__":
    main()
