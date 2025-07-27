from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from slc_app.models import ControleCharges, Groupe, ReleveIndividuel, PosteReleve, engine
from sqlmodel import Session, select


def show_releves_individuels_page():
    """Page de visualisation des relevés individuels par contrôle de charges"""

    st.title("💧 Visualisation des Relevés Individuels")
    st.markdown("Consultez les relevés individuels par contrôle de charges et postes")

    # Sidebar pour sélection du contrôle
    with st.sidebar:
        st.header("🔧 Sélection du Contrôle")

        # Récupérer les contrôles disponibles avec relevés individuels
        controles_disponibles = get_controles_avec_releves()

        if not controles_disponibles:
            st.warning("Aucun contrôle avec relevés individuels trouvé")
            st.stop()

        # Créer les options pour la selectbox
        options_controles = []
        for controle in controles_disponibles:
            label = (
                f"{controle['annee']} - {controle['groupe_nom']} ({controle['nb_postes']} postes)"
            )
            options_controles.append({"label": label, "value": controle["id"], "data": controle})

        # Selectbox pour choisir le contrôle
        selected_controle = st.selectbox(
            "Choisir un contrôle de charges:",
            options=options_controles,
            format_func=lambda x: x["label"] if x else "Aucun",
        )

        if selected_controle:
            controle_data = selected_controle["data"]
            st.success("✅ Contrôle sélectionné")
            st.info(
                f"""
            **Année:** {controle_data['annee']}
            **Groupe:** {controle_data['groupe_nom']}
            **Postes de relevé:** {controle_data['nb_postes']}
            **Total relevés:** {controle_data['nb_releves']}
            """
            )

            # Section de filtrage par poste
            st.header("🔍 Filtrage")

            # Récupérer les postes pour ce contrôle
            postes_disponibles = get_postes_pour_controle(controle_data["id"])

            # Option "Tous les postes"
            options_postes = [{"label": "🔄 Tous les postes", "value": None}]
            for poste in postes_disponibles:
                options_postes.append(
                    {
                        "label": f"📍 {poste['nom']} ({poste['nb_releves']} relevés)",
                        "value": poste["id"],
                    }
                )

            selected_poste = st.selectbox(
                "Filtrer par poste:",
                options=options_postes,
                format_func=lambda x: x["label"] if x else "Aucun",
            )

    # Contenu principal
    if selected_controle:
        controle_id = selected_controle["value"]
        poste_id = selected_poste["value"] if selected_poste else None

        st.header("📋 Données des Relevés Individuels")

        # Récupérer et afficher les données
        releves_df = get_releves_dataframe(controle_id, poste_id)

        if releves_df.empty:
            st.warning("Aucun relevé individuel trouvé pour cette sélection")
        else:
            # Affichage des métriques
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total relevés", len(releves_df))

            with col2:
                ug_uniques = (
                    releves_df["numero_ug"].nunique() if "numero_ug" in releves_df.columns else 0
                )
                st.metric("UG uniques", ug_uniques)

            with col3:
                if "total_facture" in releves_df.columns:
                    total_montant = releves_df["total_facture"].sum()
                    st.metric("Total montant", f"{total_montant:.2f} €")
                else:
                    st.metric("Total montant", "N/A")

            with col4:
                postes_uniques = (
                    releves_df["poste_nom"].nunique() if "poste_nom" in releves_df.columns else 0
                )
                st.metric("Postes", postes_uniques)

            # Onglets pour différentes vues
            tab1, tab2, tab3 = st.tabs(
                ["📊 Tableau détaillé", "📈 Statistiques", "📋 Résumé par UG"]
            )

            with tab1:
                st.subheader("Tableau des relevés individuels")

                # Options d'affichage
                col_options1, col_options2 = st.columns(2)
                with col_options1:
                    show_all_columns = st.checkbox("Afficher toutes les colonnes", value=False)
                with col_options2:
                    highlight_anomalies = st.checkbox("Surligner les anomalies", value=True)

                # Préparer le DataFrame pour l'affichage
                display_df = prepare_releves_for_display(releves_df, show_all_columns)

                # Styling conditionnel
                if highlight_anomalies:
                    display_df = apply_releves_styling(display_df)

                st.dataframe(display_df, use_container_width=True, height=400)

                # Bouton de téléchargement
                csv = releves_df.to_csv(index=False)
                st.download_button(
                    label="📥 Télécharger en CSV",
                    data=csv,
                    file_name=f"releves_individuels_{controle_data['annee']}_{controle_data['groupe_nom']}.csv",
                    mime="text/csv",
                )

            with tab2:
                st.subheader("Statistiques des relevés")

                if "total_facture" in releves_df.columns:
                    # Statistiques des montants
                    st.write("**Distribution des montants:**")
                    montants_stats = releves_df["total_facture"].describe()
                    st.dataframe(montants_stats)

                    # Graphique des montants par poste
                    if "poste_nom" in releves_df.columns:
                        st.write("**Montants par poste:**")
                        montants_par_poste = (
                            releves_df.groupby("poste_nom")["total_facture"]
                            .agg(["sum", "count", "mean"])
                            .round(2)
                        )
                        st.dataframe(montants_par_poste)

                # Statistiques des UG
                if "numero_ug" in releves_df.columns:
                    st.write("**Répartition par UG:**")
                    ug_stats = releves_df["numero_ug"].value_counts().head(10)
                    st.bar_chart(ug_stats)

            with tab3:
                st.subheader("Résumé par UG")

                if "numero_ug" in releves_df.columns:
                    # Résumé par UG
                    resume_cols = ["numero_ug"]
                    if "numero_ca" in releves_df.columns:
                        resume_cols.append("numero_ca")
                    if "total_facture" in releves_df.columns:
                        resume_cols.append("total_facture")
                    if "poste_nom" in releves_df.columns:
                        resume_cols.append("poste_nom")

                    resume_ug = (
                        releves_df[resume_cols]
                        .groupby("numero_ug")
                        .agg(
                            {
                                col: (
                                    "first"
                                    if col in ["numero_ca"]
                                    else "sum" if col == "total_facture" else "count"
                                )
                                for col in resume_cols
                                if col != "numero_ug"
                            }
                        )
                        .reset_index()
                    )

                    st.dataframe(resume_ug, use_container_width=True, height=400)


def get_controles_avec_releves() -> List[Dict]:
    """Récupérer les contrôles qui ont des relevés individuels"""
    with Session(engine) as session:
        # Requête pour récupérer les contrôles avec le nombre de relevés et postes
        query = """
        SELECT 
            cc.id,
            cc.annee,
            g.nom as groupe_nom,
            COUNT(DISTINCT pr.id) as nb_postes,
            COUNT(ri.id) as nb_releves
        FROM controle_charges cc
        JOIN groupe g ON cc.groupe_id = g.id
        LEFT JOIN poste_releve pr ON pr.controle_charges_id = cc.id
        LEFT JOIN releve_individuel ri ON ri.poste_releve_id = pr.id
        GROUP BY cc.id, cc.annee, g.nom
        HAVING COUNT(ri.id) > 0
        ORDER BY cc.annee DESC, g.nom
        """

        result = session.exec(query)
        return [
            {
                "id": row[0],
                "annee": row[1],
                "groupe_nom": row[2],
                "nb_postes": row[3],
                "nb_releves": row[4],
            }
            for row in result
        ]


def get_postes_pour_controle(controle_id: int) -> List[Dict]:
    """Récupérer les postes de relevé pour un contrôle donné"""
    with Session(engine) as session:
        query = """
        SELECT 
            pr.id,
            pr.nom,
            COUNT(ri.id) as nb_releves
        FROM poste_releve pr
        LEFT JOIN releve_individuel ri ON ri.poste_releve_id = pr.id
        WHERE pr.controle_charges_id = ?
        GROUP BY pr.id, pr.nom
        ORDER BY pr.nom
        """

        result = session.exec(query, [controle_id])
        return [{"id": row[0], "nom": row[1], "nb_releves": row[2]} for row in result]


def get_releves_dataframe(controle_id: int, poste_id: Optional[int] = None) -> pd.DataFrame:
    """Récupérer les données des relevés individuels sous forme de DataFrame"""
    with Session(engine) as session:
        # Construire la requête base
        query = """
        SELECT 
            ri.id,
            ri.numero_ug,
            ri.numero_ca,
            ri.nature_ug,
            ri.point_comptage,
            ri.numero_serie_compteur,
            ri.date_releve,
            ri.date_valeur,
            ri.type_releve,
            ri.observations,
            ri.index,
            ri.evolution_index,
            ri.ancien_index,
            ri.nouvel_index,
            ri.consommation,
            ri.montant_consommation,
            ri.montant_abonnement,
            ri.montant_divers,
            ri.total_facture,
            pr.nom as poste_nom,
            cc.annee,
            g.nom as groupe_nom
        FROM releve_individuel ri
        JOIN poste_releve pr ON ri.poste_releve_id = pr.id
        JOIN controle_charges cc ON pr.controle_charges_id = cc.id
        JOIN groupe g ON cc.groupe_id = g.id
        WHERE cc.id = ?
        """

        params = [controle_id]

        # Ajouter le filtre par poste si spécifié
        if poste_id:
            query += " AND pr.id = ?"
            params.append(poste_id)

        query += " ORDER BY ri.numero_ug, ri.numero_ca"

        result = session.exec(query, params)

        # Convertir en DataFrame
        columns = [
            "id",
            "numero_ug",
            "numero_ca",
            "nature_ug",
            "point_comptage",
            "numero_serie_compteur",
            "date_releve",
            "date_valeur",
            "type_releve",
            "observations",
            "index",
            "evolution_index",
            "ancien_index",
            "nouvel_index",
            "consommation",
            "montant_consommation",
            "montant_abonnement",
            "montant_divers",
            "total_facture",
            "poste_nom",
            "annee",
            "groupe_nom",
        ]

        df = pd.DataFrame(list(result), columns=columns)
        return df


def prepare_releves_for_display(df: pd.DataFrame, show_all_columns: bool = False) -> pd.DataFrame:
    """Préparer le DataFrame pour l'affichage"""
    if df.empty:
        return df

    # Colonnes essentielles à toujours afficher
    essential_columns = [
        "numero_ug",
        "numero_ca",
        "poste_nom",
        "type_releve",
        "consommation",
        "total_facture",
    ]

    if show_all_columns:
        # Exclure seulement l'ID et les colonnes techniques
        display_columns = [col for col in df.columns if col not in ["id"]]
    else:
        # Afficher seulement les colonnes essentielles qui existent
        display_columns = [col for col in essential_columns if col in df.columns]

    display_df = df[display_columns].copy()

    # Formatage des colonnes numériques
    for col in display_df.columns:
        if col in [
            "consommation",
            "total_facture",
            "montant_consommation",
            "montant_abonnement",
            "montant_divers",
        ]:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors="coerce")

    return display_df


def apply_releves_styling(df: pd.DataFrame) -> pd.DataFrame:
    """Appliquer un styling conditionnel pour mettre en évidence les anomalies"""
    # Pour l'instant, retourner le DataFrame tel quel
    # On peut ajouter des règles de styling plus tard
    return df


if __name__ == "__main__":
    show_releves_individuels_page()
