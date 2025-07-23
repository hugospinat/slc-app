import logging
import traceback

from sqlmodel import Session, select

from models import ControleCharges, Facture, FactureElectricite, Fournisseur, Poste, TypeFacture, engine
from processors.ged001_processor import Ged001Processor
from utils import logging_config  # noqa: F401
from utils.extraction_champs import appliquer_extractions_automatiques
from utils.fournisseurs import detecter_fournisseurs_depuis_dataframe, obtenir_statistiques_detection


def save_to_database(df, groupe_id, annee, associations_pdfs=None):
    logger = logging.getLogger(__name__)
    """Sauvegarder les données en base avec les PDFs associés et détection automatique des fournisseurs"""
    if associations_pdfs is None:
        associations_pdfs = {}

    # Détecter automatiquement les fournisseurs
    logger.info("Détection automatique des fournisseurs...")
    associations_fournisseurs = detecter_fournisseurs_depuis_dataframe(df)

    if associations_fournisseurs:
        stats = obtenir_statistiques_detection(associations_fournisseurs)
        logger.info(
            f"Détection terminée: {stats['total_factures']} factures, {stats['fournisseurs_detectes']} fournisseurs détectés"
        )
        for nom_fournisseur, details in stats["details_fournisseurs"].items():
            logger.info(f"  - {nom_fournisseur} ({details['type']}): {details['nb_factures']} factures")

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
                    texte_brut = None

                    if numero_facture in associations_pdfs:
                        info_pdf = associations_pdfs[numero_facture]
                        pdf_contenu = info_pdf["pdf_contenu"]
                        pdf_nom = f"{info_pdf['type']}_{numero_facture}.pdf"

                        # Extraire le texte brut du PDF si disponible
                        if pdf_contenu:
                            processor = Ged001Processor()
                            texte_brut = processor.extraire_texte_brut_pdf(pdf_contenu)

                    # Récupérer le fournisseur détecté
                    fournisseur_id = associations_fournisseurs.get(numero_facture)

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
                        texte_brut_pdf=texte_brut,
                        fournisseur_id=fournisseur_id,
                    )

                    session.add(facture)
                    session.flush()  # Pour obtenir l'ID de la facture

                    # Créer automatiquement l'entrée dans la table spécialisée selon le type de fournisseur
                    if fournisseur_id and facture.id is not None:
                        fournisseur = session.get(Fournisseur, fournisseur_id)
                        if fournisseur and fournisseur.type_facture == TypeFacture.ELECTRICITE:
                            # Créer une entrée FactureElectricite
                            facture_electricite = FactureElectricite(
                                facture_id=facture.id,
                                # Les autres champs seront remplis ultérieurement ou restent None
                            )
                            session.add(facture_electricite)
                            logger.info(f"Facture électricité créée pour {numero_facture}")

                        # Ici on peut ajouter d'autres types de factures spécialisées
                        # elif fournisseur.type_facture == TypeFacture.GAZ:
                        #     # Créer une entrée FactureGaz si elle existe
                        #     pass
                        # elif fournisseur.type_facture == TypeFacture.EAU:
                        #     # Créer une entrée FactureEau si elle existe
                        #     pass

                except Exception as e:
                    logger.error(f"Erreur ligne {idx + 1}: {e}")
                    logger.debug(f"Détails de la ligne: {row.to_dict()}")
                    continue

            session.commit()

            # Appliquer les règles d'extraction automatique après la sauvegarde
            logger.info("Application des règles d'extraction automatique...")
            nb_extractions_reussies = 0

            # Récupérer toutes les factures du contrôle de charge nouvellement créé
            factures_a_traiter = []
            # Récupérer les IDs des postes liés à ce contrôle
            postes_ids = [
                poste.id for poste in session.exec(select(Poste).where(Poste.controle_id == controle.id)).all()
            ]
            # Puis récupérer les factures associées à ces postes (sans utiliser in_)
            factures_controle = []
            for poste_id in postes_ids:
                factures_controle.extend(session.exec(select(Facture).where(Facture.poste_id == poste_id)).all())
            for facture in factures_controle:
                if facture.texte_brut_pdf:
                    factures_a_traiter.append(facture)

            for facture in factures_a_traiter:
                try:
                    logger.info(f"Extraction automatique pour facture {facture.numero_facture}...")
                    if appliquer_extractions_automatiques(facture.id):
                        nb_extractions_reussies += 1
                except Exception as e:
                    logger.warning(
                        f"Erreur lors de l'extraction automatique pour facture {facture.numero_facture}: {e}"
                    )

            if nb_extractions_reussies > 0:
                logger.info(f"{nb_extractions_reussies} factures traitées avec extraction automatique")

    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde: {e}")
        logger.debug(traceback.format_exc())
        raise
