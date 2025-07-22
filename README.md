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

## Structure du projet

- `app.py` : Application Streamlit principale
- `models.py` : Modèles SQLModel pour la base de données
- `file_processor.py` : Logique de traitement des fichiers ZIP/PDF
- `requirements.txt` : Dépendances Python
- `charge_control.db` : Base de données SQLite (créée automatiquement)

## Workflow

1. **Créer un groupe** : Définir nom et identifiant du groupe
2. **Importer un fichier ZIP** : Upload du ZIP contenant les PDF REG010
3. **Extraction automatique** : Le système extrait et filtre les données
4. **Validation** : Réviser et valider/contester chaque facture
5. **Tableau de bord** : Visualiser les statistiques

## Schéma de données

### Tables principales :
- **Groupe** : Informations du groupe (nom, identifiant)
- **ControleCharges** : Contrôle par année et groupe
- **Facture** : Données extraites avec 7 champs :
  - Nature
  - N° Facture  
  - Code Journal
  - N° Cpte Comptable
  - Montant Comptable
  - Libelle Ecriture
  - References Partenaire facture

### Statuts de validation :
- `en_attente` : Facture en attente de validation
- `validee` : Facture validée
- `contestee` : Facture contestée (avec commentaire)

## Technologies utilisées

- **Python 3.x**
- **SQLModel** : ORM moderne basé sur Pydantic
- **Streamlit** : Framework web pour applications de données
- **Tabula-py** : Extraction de tableaux depuis PDF
- **Pandas** : Manipulation de données
- **SQLite** : Base de données locale