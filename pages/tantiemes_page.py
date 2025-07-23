from typing import Dict, List

import pandas as pd
import streamlit as st
from sqlmodel import Session, select

from models import BaseRepartition, ControleCharges, Groupe, Tantieme, engine


def show_tantiemes_page():
    """Page de visualisation des tantièmes par contrôle de charges"""

    st.title("📊 Visualisation des Tantièmes")
    st.markdown("Consultez les tantièmes par contrôle de charges et bases de répartition")

    # Sidebar pour sélection du contrôle
    with st.sidebar:
        st.header("🔧 Sélection du Contrôle")

        # Récupérer les contrôles disponibles avec tantièmes
        controles_disponibles = get_controles_avec_tantiemes()

        if not controles_disponibles:
            st.warning("Aucun contrôle avec tantièmes trouvé")
            st.stop()

        # Créer les options pour la selectbox
        options_controles = []
        for controle in controles_disponibles:
            label = f"{controle['annee']} - {controle['groupe_nom']} ({controle['nb_bases']} bases)"
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
            **Bases de répartition:** {controle_data['nb_bases']}
            **Total tantièmes:** {controle_data['nb_tantiemes']}
            """
            )

    if not selected_controle:
        st.info("👈 Sélectionnez un contrôle de charges dans la sidebar")
        return

    controle_id = selected_controle["value"]

    # Layout principal en deux colonnes
    col1, col2 = st.columns([1, 2])

    with col1:
        st.header("📋 Bases de Répartition")

        # Récupérer et afficher les bases de répartition
        bases_data = get_bases_repartition_summary(controle_id)

        if bases_data:
            # Créer un DataFrame pour l'affichage
            df_bases = pd.DataFrame(bases_data)

            # Afficher le tableau des bases
            st.dataframe(
                df_bases,
                column_config={
                    "code": "Code",
                    "nom": "Nom de la base",
                    "nb_tantiemes": st.column_config.NumberColumn("Nb Tantièmes", format="%d"),
                    "total_tantiemes": st.column_config.NumberColumn("Total", format="%.2f"),
                },
                hide_index=True,
                use_container_width=True,
            )

            # Sélection d'une base pour le détail
            st.subheader("🔍 Sélection détaillée")
            codes_bases = [base["code"] for base in bases_data]
            selected_base_code = st.selectbox(
                "Choisir une base de répartition:",
                options=codes_bases,
                format_func=lambda x: f"{x} - {next(b['nom'] for b in bases_data if b['code'] == x)}",
            )
        else:
            st.warning("Aucune base de répartition trouvée")
            selected_base_code = None

    with col2:
        st.header("🏠 Détail des Tantièmes")

        if selected_base_code:
            # Récupérer les tantièmes pour la base sélectionnée
            tantiemes_data = get_tantiemes_detail(controle_id, selected_base_code)

            if tantiemes_data:
                # Informations sur la base sélectionnée
                base_info = next(b for b in bases_data if b["code"] == selected_base_code)
                st.info(
                    f"""
                **Base:** {base_info['code']} - {base_info['nom']}
                **Nombre de tantièmes:** {base_info['nb_tantiemes']}
                **Total:** {base_info['total_tantiemes']:.2f}
                """
                )

                # Créer un DataFrame pour l'affichage
                df_tantiemes = pd.DataFrame(tantiemes_data)

                # Afficher le tableau des tantièmes
                st.dataframe(
                    df_tantiemes,
                    column_config={
                        "numero_ug": "N° UG",
                        "numero_ca": "N° CA",
                        "debut_occupation": st.column_config.DateColumn("Début occupation", format="DD/MM/YYYY"),
                        "fin_occupation": st.column_config.DateColumn("Fin occupation", format="DD/MM/YYYY"),
                        "tantieme": st.column_config.NumberColumn("Tantième", format="%.2f"),
                        "reliquat": st.column_config.NumberColumn("Reliquat", format="%.2f"),
                    },
                    hide_index=True,
                    use_container_width=True,
                )

                # Statistiques
                st.subheader("📈 Statistiques")
                col_stat1, col_stat2, col_stat3 = st.columns(3)

                with col_stat1:
                    st.metric("Total Tantièmes", f"{len(tantiemes_data)}")

                with col_stat2:
                    total_tantieme = sum(float(t["tantieme"]) for t in tantiemes_data if t["tantieme"])
                    st.metric("Somme Tantièmes", f"{total_tantieme:.2f}")

                with col_stat3:
                    moyenne_tantieme = total_tantieme / len(tantiemes_data) if tantiemes_data else 0
                    st.metric("Moyenne", f"{moyenne_tantieme:.2f}")

            else:
                st.warning(f"Aucun tantième trouvé pour la base {selected_base_code}")
        else:
            st.info("👈 Sélectionnez une base de répartition pour voir les détails")


def get_controles_avec_tantiemes() -> List[Dict]:
    """Récupérer tous les contrôles qui ont des tantièmes"""
    try:
        with Session(engine) as session:
            # Approche SQLModel pure : pas de joins complexes
            bases_existantes = session.exec(select(BaseRepartition)).all()

            # Grouper par controle_id
            controles_avec_bases = {}
            for base in bases_existantes:
                if base.controle_id not in controles_avec_bases:
                    controles_avec_bases[base.controle_id] = []
                controles_avec_bases[base.controle_id].append(base)

            controles = []
            for controle_id, bases_du_controle in controles_avec_bases.items():
                # Récupérer le contrôle et le groupe
                controle = session.get(ControleCharges, controle_id)
                if not controle:
                    continue

                groupe = session.get(Groupe, controle.groupe_id)
                if not groupe:
                    continue

                # Compter les tantièmes pour ce contrôle - Solution simple
                total_tantiemes = 0
                for base in bases_du_controle:
                    tantiemes_de_la_base = session.exec(
                        select(Tantieme).where(Tantieme.base_repartition_id == base.id)
                    ).all()
                    total_tantiemes += len(tantiemes_de_la_base)

                controles.append(
                    {
                        "id": controle.id,
                        "annee": controle.annee,
                        "groupe_nom": groupe.nom,
                        "nb_bases": len(bases_du_controle),
                        "nb_tantiemes": total_tantiemes,
                    }
                )

            return controles

    except Exception as e:
        st.error(f"Erreur lors de la récupération des contrôles: {str(e)}")
        return []


def get_bases_repartition_summary(controle_id: int) -> List[Dict]:
    """Récupérer le résumé des bases de répartition pour un contrôle"""
    try:
        with Session(engine) as session:
            statement = (
                select(BaseRepartition).where(BaseRepartition.controle_id == controle_id).order_by(BaseRepartition.code)
            )

            bases = session.exec(statement).all()

            bases_summary = []
            for base in bases:
                # Compter les tantièmes et calculer le total
                tantiemes = session.exec(select(Tantieme).where(Tantieme.base_repartition_id == base.id)).all()

                total_tantiemes = sum(float(t.tantieme) for t in tantiemes if t.tantieme is not None)

                bases_summary.append(
                    {
                        "code": base.code,
                        "nom": base.nom,
                        "nb_tantiemes": len(tantiemes),
                        "total_tantiemes": total_tantiemes,
                    }
                )

            return bases_summary

    except Exception as e:
        st.error(f"Erreur lors de la récupération des bases: {str(e)}")
        return []


def get_tantiemes_detail(controle_id: int, base_code: str) -> List[Dict]:
    """Récupérer le détail des tantièmes pour une base de répartition"""
    try:
        with Session(engine) as session:
            # Trouver d'abord la base
            base = session.exec(
                select(BaseRepartition)
                .where(BaseRepartition.controle_id == controle_id)
                .where(BaseRepartition.code == base_code)
            ).first()

            if not base:
                return []

            # Puis récupérer les tantièmes
            tantiemes = session.exec(
                select(Tantieme).where(Tantieme.base_repartition_id == base.id).order_by(Tantieme.numero_ug)
            ).all()

            tantiemes_detail = []
            for tantieme in tantiemes:
                tantiemes_detail.append(
                    {
                        "numero_ug": tantieme.numero_ug,
                        "numero_ca": tantieme.numero_ca,
                        "debut_occupation": tantieme.debut_occupation,
                        "fin_occupation": tantieme.fin_occupation,
                        "tantieme": tantieme.tantieme,
                        "reliquat": tantieme.reliquat,
                    }
                )

            return tantiemes_detail

    except Exception as e:
        st.error(f"Erreur lors de la récupération des tantièmes: {str(e)}")
        return []


if __name__ == "__main__":
    show_tantiemes_page()
