import traceback

from sqlmodel import Session, select

from models import ControleCharges, Facture, Poste, engine


def save_to_database(df, groupe_id, annee, associations_pdfs=None):
    """Sauvegarder les données en base avec les PDFs associés"""
    if associations_pdfs is None:
        associations_pdfs = {}

    try:
        with Session(engine) as session:
            controle = session.exec(
                select(ControleCharges).where(ControleCharges.groupe_id == groupe_id, ControleCharges.annee == annee)
            ).first()

            if not controle:
                controle = ControleCharges(groupe_id=groupe_id, annee=annee)
                session.add(controle)
                session.commit()
                session.refresh(controle)

            postes_distincts = df["nature"].dropna().unique()
            postes_map = {}

            for code_poste in postes_distincts:
                if " - " in code_poste:
                    code, nom = code_poste.split(" - ", 1)
                else:
                    code = code_poste
                    nom = code_poste

                poste = session.exec(select(Poste).where(Poste.controle_id == controle.id, Poste.code == code)).first()

                if not poste and controle.id is not None:
                    poste = Poste(controle_id=controle.id, code=code, nom=nom, rapport="")
                    session.add(poste)
                    session.commit()
                    session.refresh(poste)

                postes_map[code_poste] = poste

            for idx, (index, row) in enumerate(df.iterrows()):
                try:
                    nature = str(row["nature"])
                    if nature not in postes_map:
                        continue

                    poste = postes_map[nature]
                    numero_facture = str(row["numero_facture"])

                    try:
                        montant = float(row["montant_comptable"])
                    except (ValueError, TypeError):
                        continue

                    pdf_nom = None
                    pdf_contenu = None
                    if numero_facture in associations_pdfs:
                        info_pdf = associations_pdfs[numero_facture]
                        pdf_contenu = info_pdf["pdf_contenu"]
                        pdf_nom = f"{info_pdf['type']}_{numero_facture}.pdf"

                    facture = Facture(
                        poste_id=poste.id,
                        nature=nature,
                        numero_facture=numero_facture,
                        code_journal=str(row["code_journal"]),
                        numero_compte_comptable=str(row["numero_compte_comptable"]),
                        montant_comptable=montant,
                        libelle_ecriture=str(row["libelle_ecriture"]),
                        references_partenaire_facture=str(row["references_partenaire_facture"]),
                        fichier_source=str(row["fichier_source"]),
                        ligne_pdf=int(row["ligne_pdf"]),
                        pdf_facture_nom=pdf_nom,
                        pdf_facture_contenu=pdf_contenu,
                    )

                    session.add(facture)

                except Exception as e:
                    print(f"❌ Erreur ligne {idx + 1}: {e}")
                    print("Détails de la ligne:", row.to_dict())
                    continue

            session.commit()

    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        traceback.print_exc()
        raise
