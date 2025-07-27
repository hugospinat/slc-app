"""
Tests pour valider l'architecture refactorisée avec composition et mapping automatique
"""

import tempfile
import shutil
from pathlib import Path
from sqlmodel import Session, select

from slc_app.models.db import engine
from slc_app.models.groupe import Groupe
from slc_app.models.controle_charges import ControleCharges
from slc_app.models.facture import Facture
from slc_app.models.poste import Poste
from slc_app.models.tantieme import Tantieme
from slc_app.models.base_repartition import BaseRepartition
from slc_app.services.importer.ph.ph_importer import importer_ph


def test_architecture_complete():
    """Test complet de l'architecture refactorisée"""

    # Créer un groupe de test
    with Session(engine) as session:
        # Nettoyer d'abord
        session.execute(select(Facture).where(Facture.numero_local.like("TEST_%")))
        for facture in session.exec(select(Facture).where(Facture.numero_local.like("TEST_%"))):
            session.delete(facture)

        # Créer le groupe de test
        groupe_test = Groupe(nom="Test Group Refacto", identifiant="TEST_REFACTO")
        session.add(groupe_test)
        session.commit()
        session.refresh(groupe_test)

        groupe_id = groupe_test.id

    try:
        # Tester l'import avec le nouveau système
        test_zip = Path("tests/data/113RU.zip")
        importer_ph(2024, groupe_id, str(test_zip))

        # Vérifications après import
        with Session(engine) as session:
            # Vérifier contrôle charges créé
            controle = session.exec(
                select(ControleCharges)
                .where(ControleCharges.groupe_id == groupe_id)
                .where(ControleCharges.annee == 2024)
            ).first()

            assert controle is not None, "Le contrôle des charges doit être créé"

            # Vérifier factures créées avec relations
            factures = session.exec(
                select(Facture).join(Poste).where(Poste.controle_id == controle.id)
            ).all()

            assert len(factures) > 0, "Des factures doivent être créées"

            # Vérifier postes créés avec relation contrôle
            postes = session.exec(select(Poste).where(Poste.controle_id == controle.id)).all()

            assert len(postes) > 0, "Des postes doivent être créés"

            # Vérifier que toutes les relations sont bien établies
            for poste in postes:
                assert poste.controle_id == controle.id, "Relation poste-contrôle doit être établie"
                if poste.factures:
                    for facture in poste.factures:
                        assert (
                            facture.poste_id == poste.id
                        ), "Relation facture-poste doit être établie"

            # Vérifier tantièmes si présents (optionnel)
            bases_rep = session.exec(
                select(BaseRepartition).where(BaseRepartition.controle_id == controle.id)
            ).all()

            if bases_rep:  # Si REG114 était présent
                tantiemes = session.exec(
                    select(Tantieme)
                    .join(BaseRepartition)
                    .where(BaseRepartition.controle_id == controle.id)
                ).all()

                # Vérifier relations tantièmes-bases
                for base in bases_rep:
                    assert (
                        base.controle_id == controle.id
                    ), "Relation base-contrôle doit être établie"
                    if base.tantiemes:
                        for tantieme in base.tantiemes:
                            assert (
                                tantieme.base_repartition_id == base.id
                            ), "Relation tantième-base doit être établie"

            print(f"✅ Test réussi:")
            print(f"   - Contrôle: {controle.id}")
            print(f"   - Factures: {len(factures)}")
            print(f"   - Postes: {len(postes)}")
            print(f"   - Bases répartition: {len(bases_rep)}")

    finally:
        # Nettoyage
        with Session(engine) as session:
            # Supprimer le groupe et ses dépendances
            groupe = session.get(Groupe, groupe_id)
            if groupe:
                session.delete(groupe)
                session.commit()


def test_utility_functions_isolation():
    """Test que les fonctions utilitaires fonctionnent en isolation"""
    from slc_app.services.importer.ph.ph_importer import (
        assign_controle_id,
        process_pdf_type,
        create_controle_charges,
    )

    # Test création contrôle charges
    with Session(engine) as session:
        groupe_test = Groupe(nom="Test Utils", identifiant="TEST_UTILS")
        session.add(groupe_test)
        session.commit()
        session.refresh(groupe_test)
        groupe_id = groupe_test.id

    try:
        # Test create_controle_charges
        controle = create_controle_charges(2025, groupe_id)
        assert controle.annee == 2025
        assert controle.groupe_id == groupe_id

        # Test assign_controle_id
        from slc_app.models.poste import Poste

        poste_test = Poste(code="TEST", description="Test")
        assign_controle_id([poste_test], controle.id)
        assert poste_test.controle_id == controle.id

        print("✅ Tests utilitaires réussis")

    finally:
        # Nettoyage
        with Session(engine) as session:
            # Supprimer contrôle et groupe
            if controle.id:
                controle_db = session.get(ControleCharges, controle.id)
                if controle_db:
                    session.delete(controle_db)

            groupe = session.get(Groupe, groupe_id)
            if groupe:
                session.delete(groupe)
            session.commit()


if __name__ == "__main__":
    test_architecture_complete()
    test_utility_functions_isolation()
    print("🎉 Tous les tests de l'architecture refactorisée sont passés !")
