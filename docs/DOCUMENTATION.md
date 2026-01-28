# Documentation BankIA - Système de Matching Bancaire avec Dolibarr

## Table des matières
1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Fonctionnalités implémentées](#fonctionnalités-implémentées)
4. [Fonctionnalités en cours](#fonctionnalités-en-cours)
5. [Fonctionnalités planifiées](#fonctionnalités-planifiées)
6. [Guide technique](#guide-technique)
7. [API Reference](#api-reference)

---

## Vue d'ensemble

**BankIA** est une application web qui automatise le matching entre les relevés bancaires CSV et les factures Dolibarr, permettant la création automatique de paiements.

### Objectifs principaux
- Parser les fichiers CSV de relevés bancaires
- Matcher automatiquement avec les factures Dolibarr impayées
- Créer les paiements et lignes bancaires dans Dolibarr
- Faciliter la gestion de la comptabilité

### Stack technique
- **Backend**: Python Flask
- **Frontend**: HTML/CSS/JavaScript vanilla
- **API**: Dolibarr REST API
- **Data Processing**: Pandas, NumPy
- **Parser**: CSV avec détection automatique de format

---

## Architecture

### Structure des fichiers
```
BankIA/
├── app.py                 # Application Flask principale
├── config.py              # Configuration (Dolibarr, Flask)
├── csv_parser.py          # Parser CSV avec détection automatique
├── dolibarr_client.py     # Client API Dolibarr
├── matcher.py             # Algorithme de matching intelligent
├── database.py            # Gestion base de données SQLite
├── requirements.txt       # Dépendances Python
├── templates/
│   └── index.html        # Interface web
├── uploads/              # Fichiers CSV uploadés
├── bankia.db            # Base de données SQLite (créée automatiquement)
└── docs/                 # Documentation (ce fichier)
```

### Flux de données
```
CSV Upload → Parser → Transactions → Matcher → Matches → Validation → Dolibarr API
                                                              ↓
                                                      Paiements créés
```

### Composants principaux

#### 1. CSV Parser (`csv_parser.py`)
- Détection automatique du séparateur (; , \t)
- Gestion des accents et encodages
- Calcul automatique des montants (crédit/débit)
- Extraction des références de factures

#### 2. Dolibarr Client (`dolibarr_client.py`)
- Communication avec API REST Dolibarr
- Gestion des erreurs et retry
- Normalisation des URLs

#### 3. Matcher (`matcher.py`)
- Matching par montant (tolérance configurable)
- Matching par date (tolérance 7 jours)
- Matching par référence de facture
- Matching par nom de tiers
- Score de confiance (0-100%)

---

## Fonctionnalités implémentées

### ✅ Version 1.0 - Core Functionality

#### Parsing CSV
- [x] Upload de fichiers CSV
- [x] Détection automatique du format
- [x] Support point-virgule et virgule
- [x] Gestion des accents (Débit, Crédit)
- [x] Parsing des dates (DD/MM/YYYY)
- [x] Conversion montants (virgule → point)
- [x] Extraction références factures

#### Matching
- [x] Matching avec factures impayées Dolibarr
- [x] Score de confiance (0-100%)
- [x] Affichage des meilleurs matches
- [x] Raisons de matching détaillées

#### Paiements
- [x] Création de paiement simple
- [x] Création paiement + ligne bancaire
- [x] Vérification montants avant création
- [x] Confirmation avec détails
- [x] Retour statut facture après paiement

#### Interface
- [x] Upload drag & drop
- [x] Affichage des résultats de matching
- [x] Boutons d'action par transaction
- [x] Messages de confirmation/erreur

---

## Fonctionnalités implémentées

### ✅ Version 1.0 - Core Functionality

#### Parsing CSV
- [x] Upload de fichiers CSV
- [x] Détection automatique du format
- [x] Support point-virgule et virgule
- [x] Gestion des accents (Débit, Crédit)
- [x] Parsing des dates (DD/MM/YYYY)
- [x] Conversion montants (virgule → point)
- [x] Extraction références factures

#### Matching
- [x] Matching avec factures impayées Dolibarr
- [x] Score de confiance (0-100%)
- [x] Affichage des meilleurs matches
- [x] Raisons de matching détaillées

#### Paiements
- [x] Création de paiement simple
- [x] Création paiement + ligne bancaire
- [x] Vérification montants avant création
- [x] Confirmation avec détails
- [x] Retour statut facture après paiement

#### Interface
- [x] Upload drag & drop
- [x] Affichage des résultats de matching
- [x] Boutons d'action par transaction
- [x] Messages de confirmation/erreur

---

## Fonctionnalités en cours

### 🔄 Version 1.1 - Améliorations UX (EN COURS)

#### Historique et traçabilité
- [x] Journal des paiements créés (SQLite)
- [x] Historique des actions utilisateur
- [x] Affichage historique dans l'interface
- [x] Statistiques des paiements
- [x] Annulation de paiements dans l'historique
- [ ] Export des résultats

#### Améliorations matching
- [x] Filtres et recherche
- [x] Tri multi-colonnes
- [x] Recherche dans libellés
- [x] Filtres par score, montant, statut
- [ ] Vue détaillée des matches

---

## Fonctionnalités planifiées

### 📋 Version 1.2 - Matching avancé
- [ ] Matching automatique en lot
- [ ] Règles de matching personnalisables
- [ ] Aide à la décision intelligente

### 📋 Version 1.3 - Rapprochement bancaire
- [ ] Interface de rapprochement visuel
- [ ] Cocher transactions rapprochées
- [ ] État de rapprochement par période

### 📋 Version 1.4 - Analyse et reporting
- [ ] Tableaux de bord
- [ ] Export Excel/PDF
- [ ] Statistiques avancées

### 📋 Version 2.0 - Fonctionnalités avancées
- [ ] Multi-utilisateurs
- [ ] Machine Learning pour matching
- [ ] OCR pour PDFs

---

## Guide technique

### Configuration

#### Variables d'environnement
```python
DOLIBARR_URL = 'https://votre-domaine.com/api/index.php'
DOLIBARR_API_KEY = 'votre_cle_api'
DOLIBARR_API_LOGIN = 'admin'
SECRET_KEY = 'secret_key_flask'
```

#### Configuration matching
```python
AMOUNT_TOLERANCE = 0.01  # Tolérance montant
DATE_TOLERANCE_DAYS = 7  # Tolérance date
```

### Endpoints API

#### Upload CSV
```
POST /api/upload
Content-Type: multipart/form-data
Body: file (CSV)

Response: {
  "success": true,
  "transactions_count": 15,
  "transactions": [...]
}
```

#### Matching
```
POST /api/match
Content-Type: application/json
Body: {
  "transactions": [...],
  "account_id": 1
}

Response: {
  "success": true,
  "matched_transactions": [...]
}
```

#### Créer paiement
```
POST /api/dolibarr/create-payment
Content-Type: application/json
Body: {
  "invoice_id": 123,
  "datepaye": "1730851200",
  "paymentid": 2,
  "accountid": 1,
  "amount": 100.50
}

Response: {
  "success": true,
  "payment_id": 456,
  "invoice": {...}
}
```

#### Historique des paiements
```
GET /api/history/payments?limit=50&offset=0

Response: {
  "success": true,
  "payments": [...],
  "count": 50
}
```

#### Statistiques
```
GET /api/history/statistics

Response: {
  "success": true,
  "statistics": {
    "total_created": 25,
    "total_cancelled": 2,
    "total_amount": 15000.50,
    "today_count": 5
  }
}
```

#### Annuler un paiement dans l'historique
```
POST /api/history/payments/{record_id}/cancel
Content-Type: application/json
Body: {
  "reason": "Erreur de saisie"
}

Response: {
  "success": true,
  "message": "Paiement marqué comme annulé"
}
```

### Format CSV supporté

#### Format standard français
```csv
Date comptable; Libellé opération; Débit; Crédit; Solde
05/11/2025;VIRT RECU CLIENT;;100,00;1000,00
```

#### Colonnes détectées automatiquement
- Date: `Date comptable`, `Date`, `date`
- Libellé: `Libellé opération`, `Libellé`, `Label`, `Description`
- Montant: `Débit`, `Crédit`, `Montant`, `Amount`

### Algorithme de matching

#### Score de matching
- **Montant exact** (100%): Différence < 0.01€ → +100 points
- **Montant très proche** (90%): Différence < 0.1% → +90 points
- **Montant proche** (70%): Différence < 1% → +70 points
- **Montant relativement proche** (40%): Différence < 5% → +40 points
- **Référence trouvée**: +50 points
- **Référence partielle**: +30 points
- **Date proche** (0-7 jours): +20-30 points
- **Nom tiers trouvé**: +20 points

#### Score minimum pour "bon match"
- Score >= 50: Match considéré comme valide
- Score >= 80: Match de haute confiance

---

## API Reference

### DolibarrClient

#### `get_invoices(status='unpaid', limit=100)`
Récupère les factures impayées depuis Dolibarr.

#### `get_bank_accounts()`
Récupère la liste des comptes bancaires.

#### `add_payment(invoice_id, datepaye, paymentid, accountid, ...)`
Crée un paiement pour une facture.

#### `add_bank_line(account_id, date, type, label, amount, ...)`
Crée une ligne bancaire.

### BankStatementParser

#### `parse(file_path)`
Parse un fichier CSV et retourne une liste de transactions.

### Database

#### `add_payment(payment_id, invoice_id, invoice_ref, ...)`
Enregistre un paiement dans l'historique SQLite.

#### `get_payment_history(limit, offset, filters)`
Récupère l'historique des paiements avec filtres optionnels.

#### `get_statistics()`
Récupère les statistiques sur les paiements créés.

#### `cancel_payment(record_id, reason)`
Marque un paiement comme annulé dans l'historique.

### TransactionMatcher

#### `match_transactions(csv_transactions, invoices, bank_lines)`
Match les transactions CSV avec les factures et lignes bancaires Dolibarr.

---

## Changelog

### Version 1.0.0 (2025-11-05)
- ✅ Parsing CSV avec détection automatique
- ✅ Matching intelligent avec factures Dolibarr
- ✅ Création de paiements
- ✅ Création paiement + ligne bancaire
- ✅ Interface web complète

---

## Notes de développement

### Bonnes pratiques
- Toujours vérifier la documentation avant modification
- Tester chaque fonctionnalité avant de passer à la suivante
- Documenter les changements dans ce fichier
- Respecter la structure existante

### Prochaines étapes
1. Implémenter l'historique des paiements
2. Ajouter les filtres et recherche
3. Créer l'export Excel

---

**Dernière mise à jour**: 2025-11-05
**Version actuelle**: 1.1.0 (en développement)

