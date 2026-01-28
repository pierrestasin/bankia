# BankIA - Matching automatique des relevés bancaires avec Dolibarr

## Description

BankIA est une application web qui permet de :
- Uploader un fichier CSV de relevé bancaire
- Faire un matching automatique avec les factures impayées dans Dolibarr
- Créer des paiements et lignes bancaires dans Dolibarr

## 📚 Documentation

- **[Documentation complète](docs/DOCUMENTATION.md)** - Guide technique détaillé
- **[Roadmap](docs/ROADMAP.md)** - Plan de développement et fonctionnalités planifiées
- **[Changelog](docs/CHANGELOG.md)** - Historique des versions

## Installation

### Prérequis

- Python 3.8 ou supérieur
- Accès à une instance Dolibarr avec API REST activée
- Clé API Dolibarr

### Installation des dépendances

```bash
pip install -r requirements.txt
```

Ou utilisez le script d'installation automatique :
```bash
.\install.bat
```

### Configuration

1. Créez un fichier `.env` ou configurez les variables d'environnement :

```bash
DOLIBARR_URL=http://votre-dolibarr.com/api/index.php
DOLIBARR_API_KEY=votre_cle_api
DOLIBARR_API_LOGIN=admin
SECRET_KEY=votre_secret_key
```

Ou modifiez directement `config.py` avec vos paramètres.

### Lancement de l'application

```bash
python app.py
```

Ou utilisez le script de démarrage :
```bash
.\start.bat
```

L'application sera accessible sur `http://localhost:5000`

## Utilisation

1. **Upload du CSV** : Glissez-déposez ou sélectionnez votre fichier CSV de relevé bancaire
2. **Sélection du compte** : Choisissez le compte bancaire dans Dolibarr
3. **Matching** : Cliquez sur "Effectuer le matching" pour trouver les correspondances
4. **Résultats** : Consultez les résultats et créez les paiements si nécessaire

## Format CSV

Le parser supporte plusieurs formats de CSV courants. Les colonnes attendues sont :
- Date (format: YYYY-MM-DD, DD/MM/YYYY, etc.)
- Libellé/Description
- Montant (ou Débit/Crédit séparés)

## Algorithmes de matching

Le système utilise plusieurs critères pour faire le matching :
- **Montant** : Correspondance exacte ou proche (tolérance configurable)
- **Date** : Correspondance de date (tolérance de 7 jours par défaut)
- **Référence** : Détection automatique des références de factures dans les libellés
- **Tiers** : Correspondance avec le nom du tiers dans le libellé

## API Endpoints

- `POST /api/upload` : Upload d'un fichier CSV
- `POST /api/match` : Effectuer le matching avec Dolibarr
- `GET /api/dolibarr/accounts` : Liste des comptes bancaires
- `GET /api/dolibarr/invoices` : Liste des factures
- `POST /api/dolibarr/create-payment` : Créer un paiement
- `POST /api/dolibarr/create-payment-and-bank-line` : Créer paiement + ligne bancaire
- `POST /api/dolibarr/create-bank-line` : Créer une ligne bancaire

## Structure du projet

```
BankIA/
├── app.py                 # Application Flask principale
├── config.py              # Configuration
├── csv_parser.py          # Parser pour fichiers CSV
├── dolibarr_client.py     # Client API Dolibarr
├── matcher.py             # Algorithme de matching
├── requirements.txt       # Dépendances Python
├── templates/
│   └── index.html        # Interface web
├── uploads/              # Dossier pour les fichiers uploadés
└── docs/                 # Documentation
    ├── DOCUMENTATION.md   # Documentation technique complète
    ├── ROADMAP.md        # Plan de développement
    └── CHANGELOG.md      # Historique des versions
```

## Développement

Pour contribuer ou modifier l'application :

1. Consultez la [documentation technique](docs/DOCUMENTATION.md)
2. Vérifiez le [roadmap](docs/ROADMAP.md) pour les fonctionnalités planifiées
3. Respectez les conventions de code existantes

## Version actuelle

**Version 1.0.0** - Fonctionnalités de base complètes

Voir le [changelog](docs/CHANGELOG.md) pour plus de détails.

## License

MIT License

