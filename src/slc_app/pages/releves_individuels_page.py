import pandas as pd
import streamlit as st

from slc_app.services.releves_individuels_service import (
    get_all_controles_charges,
    get_postes_releve_by_controle,
    get_releves_individuels,
    get_stats_releves,
)


def show():
    st.title("Relevés Individuels")
    st.markdown("Visualisation des index de compteurs et leurs évolutions")

    # Sidebar pour les filtres
    with st.sidebar:
        st.header("Filtres")

        # Récupérer tous les contrôles de charges
        controles = get_all_controles_charges()

        if not controles:
            st.warning("Aucun contrôle de charges disponible")
            return

        # Créer les options pour le selectbox
        controle_options = {f"{c.annee} - {c.groupe.nom}": c for c in controles}

        # Sélection du contrôle de charges
        selected_controle_label = st.selectbox(
            "Contrôle de charges (Année - Groupe)", options=list(controle_options.keys()), index=0
        )

        selected_controle = controle_options[selected_controle_label]

        # Récupérer les postes relevé pour ce contrôle
        postes_releve = get_postes_releve_by_controle(selected_controle.id)

        if not postes_releve:
            st.warning("Aucun poste relevé disponible pour ce contrôle")
            return

        # Sélection du poste (pas d'option "Tous")
        poste_options = {p.nom: p.id for p in postes_releve}

        selected_poste_label = st.selectbox(
            "Poste relevé", options=list(poste_options.keys()), index=0
        )

        selected_poste_id = poste_options[selected_poste_label]

    # Zone principale
    st.subheader(f"Relevés pour {selected_controle_label}")
    st.info(f"Poste : {selected_poste_label}")

    # Récupérer les relevés
    releves = get_releves_individuels(
        controle_charges_id=selected_controle.id, poste_releve_id=selected_poste_id
    )

    if not releves:
        st.warning("Aucun relevé trouvé pour les critères sélectionnés")
        return

    # Afficher les statistiques globales
    stats = get_stats_releves(releves)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total relevés", stats["total"])
    with col2:
        st.metric("Consommation totale", f"{stats['consommation_totale']:.0f}")
    with col3:
        st.metric(
            "Évolution moyenne",
            f"{stats['evolution_moyenne']:.1f}" if stats["evolution_moyenne"] else "N/A",
        )
    with col4:
        if stats["evolution_min"] is not None and stats["evolution_max"] is not None:
            st.metric("Min / Max", f"{stats['evolution_min']:.0f} / {stats['evolution_max']:.0f}")
        else:
            st.metric("Min / Max", "N/A")

    # Regrouper les relevés par UG
    releves_par_ug = {}
    for releve in releves:
        ug = releve.numero_ug
        if ug not in releves_par_ug:
            releves_par_ug[ug] = []
        releves_par_ug[ug].append(releve)

    # Trier les UG par numéro
    ugs_triees = sorted(releves_par_ug.keys())

    # Afficher un dataframe pour chaque UG
    st.subheader(f"Détail des relevés par UG ({len(ugs_triees)} UG)")

    for ug in ugs_triees:
        releves_ug = releves_par_ug[ug]

        # Calculer la consommation totale de l'UG
        consommation_ug = sum(
            r.evolution_index for r in releves_ug if r.evolution_index is not None
        )

        # Afficher l'en-tête de l'UG avec sa consommation
        nature_ug = releves_ug[0].nature_ug or "Non spécifiée"
        st.markdown(f"### UG {ug} - {nature_ug}")
        st.markdown(f"**Consommation totale : {consommation_ug:.0f}**")

        # Préparer les données pour le dataframe de cette UG
        data_ug = []
        for releve in releves_ug:
            data_ug.append(
                {
                    "N° CA": releve.numero_ca,
                    "Point comptage": releve.point_comptage or "",
                    "N° Compteur": releve.numero_serie_compteur or "",
                    "Date relevé": (
                        releve.date_releve.strftime("%d/%m/%Y") if releve.date_releve else ""
                    ),
                    "Type relevé": releve.type_releve or "",
                    "Index relevé": releve.index_releve if releve.index_releve is not None else "",
                    "Évolution index": (
                        releve.evolution_index if releve.evolution_index is not None else ""
                    ),
                    "Observations": releve.observations or "",
                }
            )

        # Créer et afficher le dataframe pour cette UG
        df_ug = pd.DataFrame(data_ug)
        st.dataframe(df_ug, use_container_width=True, hide_index=True)

        # Ajouter un espace entre les UG
        st.markdown("---")

    # Options d'export global
    if releves:
        st.subheader("Export")

        # Préparer toutes les données pour l'export
        all_data = []
        for ug in ugs_triees:
            releves_ug = releves_par_ug[ug]
            consommation_ug = sum(
                r.evolution_index for r in releves_ug if r.evolution_index is not None
            )

            for releve in releves_ug:
                all_data.append(
                    {
                        "N° UG": releve.numero_ug,
                        "Nature UG": releve.nature_ug or "",
                        "Consommation UG": consommation_ug,
                        "N° CA": releve.numero_ca,
                        "Point comptage": releve.point_comptage or "",
                        "N° Compteur": releve.numero_serie_compteur or "",
                        "Date relevé": (
                            releve.date_releve.strftime("%d/%m/%Y") if releve.date_releve else ""
                        ),
                        "Type relevé": releve.type_releve or "",
                        "Index relevé": (
                            releve.index_releve if releve.index_releve is not None else ""
                        ),
                        "Évolution index": (
                            releve.evolution_index if releve.evolution_index is not None else ""
                        ),
                        "Observations": releve.observations or "",
                    }
                )

        df_export = pd.DataFrame(all_data)
        csv = df_export.to_csv(index=False, sep=";", encoding="utf-8-sig")

        st.download_button(
            label="Télécharger en CSV",
            data=csv,
            file_name=f"releves_individuels_{selected_controle.annee}_{selected_controle.groupe.nom}_{selected_poste_label}.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    show()
