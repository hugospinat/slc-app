# Application de Contrôle des Charges

Application Python utilisant SQLModel et Streamlit pour le contrôle des charges à partir de fichiers PDF.

## Fonctionnalités

- **Import de fichiers ZIP** : Upload et extraction automatique des fichiers ZIP
- **Traitement des PDF REG010** : Extraction des données avec Tabula-py
- **Base de données SQLModel** : Stockage structuré des données
- **Interface Streamlit** : Interface web intuitive
- **Validation des factures** : Système de validation/contestation

## Installation

1. Créer et activer l'environnement virtuel :

```bash
# L'environnement .venv est déjà créé
.venv\Scripts\activate
```

2. Installer les dépendances :

```bash
pip install -r requirements.txt
```

## Utilisation

1. Lancer l'application :

```bash
streamlit run app.py
```

2. Ouvrir votre navigateur à l'adresse : http://localhost:8501

#<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Application de Contrôle des Charges

Cette application Python utilise SQLModel et Streamlit pour le contrôle des charges.

## Architecture

- **SQLModel** : ORM pour la gestion de la base de données SQLite
- **Streamlit** : Interface utilisateur web
- **Tabula-py** : Extraction de données depuis les PDF
- **Pandas** : Manipulation des données

Merci d'utiliser exclusivement SQLModel pour les modèles de données et les requêtes SQL. Évitez d'utiliser SQLAlchemy directement.

## Modèles de données

- **Groupe** : Représente un groupe avec nom et identifiant
- **ControleCharges** : Contrôle des charges pour une année et un groupe
- **Facture** : Données extraites des PDF avec statut de validation, rattaché à un Poste
- **FacturePDF** : Représente un PDF de facture avec son contenu et ses métadonnées
- **Poste** : Poste des charges rattachés à un ControleCharges
- **Tantieme** : Représente les tantièmes d'une UG dans une BaseRepartition
- **TypeFacture** : Enumération des types de factures des tables de factures étendues (électricité, eau, etc.)
- **BaseRepartition** : Représente les bases de répartition pour les postes de charges, rattachées à un ControleCharges
- **FactureEtendue** : FactureElectricite, FactureEau, FactureGaz, etc. Représente les factures étendues avec des champs spécifiques pour chaque type de facture, rattachées à une Facture.
- **Fournisseur** : Représente un fournisseur avec son nom et ses regex de reconnaissance et le champ dans le quel applique le regex pour associe le fournisseur à la Facture. De plus, il est associé à un TypeFacture étendu (c'est ce qui permet de savoir si c'est une facture d'électricité, d'eau, etc.).
- **RegleExtractionChamp** : Rattaché à un Fournissuer. Représente les règles d'extraction des données depuis les PDF, avec regex et choix du champ d'output de la Facture ou FactureEtendue

## Processus d'importation

1. Décompression des fichiers ZIP
2. Création du ControleCharges pour l'année et le groupe
3. Importation séquentiel des PDF REG010, REG114, GED001
   - Extraction des données avec tabula (fonction `_extract_data_from_pdf`)
   - Nettoyage et validation des données exclusivement avec pandas (fonction `_process_extracted_data`)
   - Sauvegarde des données extraites dans la base de données (fonction `_save_to_db`, exclusivement avec SQLModel .add_all()) retournant les objets SQLModel correspondants

### Gestion des erreurs

- Lever des exceptions explicites si l’erreur est grave ou si le format est incorrect, par exemple en utilisant `raise ValueError("Message d'erreur")` ou `raise Exception("Message d'erreur")` pour les erreurs générales.
- Logguer les événements et contextes, même sans plantage
- Combiner les deux intelligemment :
  - log + raise si tu veux que l’info soit visible dans les logs et remonter au caller
  - log seul si tu veux continuer malgré une anomalie non critique
  - raise seul si c’est une erreur franche, et que tu laisses le contexte gérer

## Fonctionnalités principales

1. Import de fichiers ZIP contenant des PDF REG010, REG114, GED001
   - Extraction des PDF et stockage dans la base de données
2. Extraction automatique des données avec tabula (option lattice)
3. Reconnaissance des Fournisseurs grace au regex fournisseur et typage des factures grace à cela (un Type de facture étendu est associé à chaque Fournisseur)
4. Puis application des règles d'extraction fournisseur pour remplir les champs de la Facture ou FactureEtendue
5. TODO : Gestion des regles métiers et validation ou rejet des factures / tantièmes à partir de celles-ci
6. TODO : Gestion des allers-retours SLC - association - bailleur (et suivi des échanges)

## Style attendu

- Favoriser les `@classmethod` pour les méthodes d’import depuis DataFrame
- Utiliser des `Enum` pour les colonnes sources (éviter les chaînes brutes)
