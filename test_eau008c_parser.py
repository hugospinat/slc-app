"""Test pour le parser EAU008C"""

from sqlmodel import Session
import os

from slc_app.models import (
    ControleCharges,
    Groupe,
    PosteReleve,
    ReleveIndividuel,
    engine,
    create_db_and_tables,
)
from slc_app.services.importer.ph.eau008c_parser import ParserEAU008C


def test_eau008c_parser():
    """Test du parser EAU008C avec le fichier d'exemple"""

    # Supprimer la base de données existante si elle existe
    db_path = "database.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print("📁 Base de données existante supprimée")

    # Créer les tables en base de données
    create_db_and_tables()
    print("📁 Nouvelles tables créées")

    # Chemin vers le fichier de test
    eau008c_path = "/home/daenorks/vscode_project/slc-app/tests/data/113RU/EAU008C - RELEVÉS COMPTEURS CONSOS ET RÉGULARISATIONS - 113RU.pdf"

    with Session(engine) as session:
        # Créer un groupe de test
        groupe_test = Groupe(identifiant="113RU", nom="Groupe Test 113RU")
        session.add(groupe_test)
        session.commit()
        session.refresh(groupe_test)

        # Créer un contrôle de charges de test
        controle_test = ControleCharges(annee=2024, groupe_id=groupe_test.id)
        session.add(controle_test)
        session.commit()
        session.refresh(controle_test)

        # Tester le parser
        parser = ParserEAU008C()

        try:
            # Extraction des données du PDF
            df_extracted = parser._extract_data_from_pdf(eau008c_path)
            print(
                f"✅ Extraction réussie: {len(df_extracted)} lignes, {df_extracted.shape[1]} colonnes"
            )

            # Traitement des données
            df_releves, df_postes = parser._process_extracted_data(df_extracted)
            print(f"✅ Traitement réussi: {len(df_releves)} relevés, {len(df_postes)} postes")

            # Sauvegarde en base de données
            if not df_releves.empty and not df_postes.empty:
                releves, postes = parser._save_to_database(
                    df_releves, df_postes, controle_test.id, session
                )
                print(f"✅ Sauvegarde réussie: {len(releves)} relevés, {len(postes)} postes")

                # Vérifier que les données sont bien en base
                from sqlmodel import select

                postes_count = len(
                    session.exec(
                        select(PosteReleve).where(PosteReleve.controle_id == controle_test.id)
                    ).all()
                )
                releves_count = len(session.exec(select(ReleveIndividuel)).all())

                print(f"✅ Vérification base: {postes_count} postes, {releves_count} relevés")

                assert postes_count > 0, "Aucun poste de relevé trouvé en base"
                assert releves_count > 0, "Aucun relevé individuel trouvé en base"

            else:
                print("⚠️ Pas de données à sauvegarder")

        except Exception as e:
            print(f"❌ Erreur durant le test: {e}")
            raise


if __name__ == "__main__":
    test_eau008c_parser()
    print("🎉 Test EAU008C terminé avec succès!")
