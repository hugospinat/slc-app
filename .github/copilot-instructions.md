<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Application de Contrôle des Charges

Cette application Python utilise SQLModel et Streamlit pour le contrôle des charges.

## Architecture

- **SQLModel** : ORM pour la gestion de la base de données SQLite
- **Streamlit** : Interface utilisateur web
- **Tabula-py** : Extraction de données depuis les PDF
- **Pandas** : Manipulation des données

## Modèles de données

- **Groupe** : Représente un groupe avec nom et identifiant
- **ControleCharges** : Contrôle par année et groupe
- **Facture** : Données extraites des PDF avec statut de validation

## Fonctionnalités principales

1. Import de fichiers ZIP contenant des PDF REG010, REG114, GED001
   - Extraction des PDF et stockage dans la base de données
   - Association des factures aux groupes
2. Extraction automatique des données avec tabula (option lattice)
3. Filtrage des lignes avec montant décimal valide (5ème colonne)
4. Interface de validation/contestation des factures
5. Tableau de bord avec statistiques

## Conventions de code

- Utiliser des noms de variables en français pour correspondre au domaine métier
- Les montants sont stockés en float avec validation regex
- Les statuts : "en_attente", "validee", "contestee"
