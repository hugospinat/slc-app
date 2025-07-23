import re
from typing import Dict, List

import pandas as pd
import streamlit as st
from sqlmodel import Session, select

from models import Facture, Fournisseur, RegleExtractionChamp, TypeFacture, clear_registry, engine
from utils.extraction_champs import tester_regle_extraction

# Nettoyer les métadonnées avant l'import des modèles
clear_registry()


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


def afficher_texte_avec_highlights(texte: str, matches: List[Dict]) -> None:
    """Affiche le texte avec les matches surlignés"""
    if not matches:
        st.text_area("Texte brut", texte, height=400, disabled=True)
        return

    # Créer le HTML avec les highlights
    html_content = texte

    # Trier les matches par position pour éviter les conflits
    matches_sorted = sorted(matches, key=lambda x: x["start"], reverse=True)

    for match in matches_sorted:
        start, end = match["start"], match["end"]
        valeur = match["valeur"]
        description = match.get("description", "")

        # Remplacer par du HTML avec highlight
        highlighted = f'<mark style="background-color: #ffeb3b; padding: 2px 4px; border-radius: 3px;" title="{description}">{valeur}</mark>'
        html_content = html_content[:start] + highlighted + html_content[end:]

    # Afficher avec du HTML
    st.markdown("**Texte brut avec extractions surlignées :**")
    st.markdown(
        f'<div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; max-height: 400px; overflow-y: auto;">{html_content}</div>',
        unsafe_allow_html=True,
    )


def tester_regles_sur_texte(regles: List[RegleExtractionChamp], texte: str) -> List[Dict]:
    """Teste toutes les règles sur un texte et retourne les matches"""
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

    return matches


def main():
    st.set_page_config(page_title="Éditeur de Règles d'Extraction", page_icon="🔍", layout="wide")
    st.title("🔍 Éditeur de Règles d'Extraction")

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

        # Sélection d'une facture de test
        st.subheader("📄 Sélection d'une facture de test")

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
            with st.expander("📝 Texte brut de la facture", expanded=False):
                st.text_area("Contenu", texte_test, height=300, disabled=True, key="texte_brut_display")

        if not texte_test:
            st.stop()

        # Interface principale en deux colonnes
        col_regles, col_test = st.columns([1, 1])

        with col_regles:
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

            # Ajout d'une nouvelle règle
            st.markdown("---")
            st.markdown("**➕ Ajouter une nouvelle règle**")

            # On déduit automatiquement la table cible à partir du type du fournisseur sélectionné
            type_table_fournisseur = fournisseur.type_facture.value if fournisseur else "facture"
            champs_disponibles = obtenir_champs_fusionnes(type_table_fournisseur)

            with st.form("nouvelle_regle", clear_on_submit=True):
                col1, col2 = st.columns(2)

                with col1:
                    nouveau_champ = st.selectbox(
                        "Champ cible",
                        options=champs_disponibles,
                        index=0,
                        key=f"champ_cible_select_{type_table_fournisseur}_{len(champs_disponibles)}",
                    )

                with col2:
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

        with col_test:
            st.subheader("🧪 Test et Visualisation")

            # Tester toutes les règles actives
            if st.button("🔍 Tester toutes les règles actives", use_container_width=True):
                matches = tester_regles_sur_texte(list(regles), texte_test)

                if matches:
                    st.success(f"✅ {len(matches)} extractions trouvées")

                    # Affichage des résultats dans un tableau
                    df_resultats = pd.DataFrame(
                        [
                            {
                                "Champ": match["description"],
                                "Valeur": match["valeur"],
                                "Position": f"{match['start']}-{match['end']}",
                            }
                            for match in matches
                        ]
                    )
                    st.dataframe(df_resultats, use_container_width=True)

                    # Affichage du texte avec highlights
                    st.markdown("---")
                    afficher_texte_avec_highlights(texte_test, matches)

                else:
                    st.warning("❌ Aucune extraction trouvée")
                    st.text_area("Texte brut", texte_test, height=400, disabled=True)

            # Test d'une regex personnalisée
            st.markdown("---")
            st.markdown("**🔧 Test de regex personnalisée**")

            regex_test = st.text_input("Regex à tester", placeholder="ex: Index début.*?(\\d+)")

            if regex_test:
                try:
                    pattern = re.compile(regex_test, re.IGNORECASE | re.MULTILINE)
                    matches_custom = []

                    for match in pattern.finditer(texte_test):
                        valeur = match.group(1) if match.groups() else match.group(0)
                        matches_custom.append(
                            {
                                "start": match.start(),
                                "end": match.end(),
                                "valeur": valeur,
                                "description": "Test personnalisé",
                                "regle_id": None,
                            }
                        )

                    if matches_custom:
                        st.success(f"✅ {len(matches_custom)} correspondances trouvées")
                        for i, match in enumerate(matches_custom):
                            st.code(f"Match {i + 1}: {match['valeur']}")

                        # Affichage avec highlights
                        afficher_texte_avec_highlights(texte_test, matches_custom)
                    else:
                        st.warning("❌ Aucune correspondance")
                        st.text_area("Texte", texte_test, height=200, disabled=True)

                except re.error as e:
                    st.error(f"❌ Erreur dans la regex: {e}")

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
