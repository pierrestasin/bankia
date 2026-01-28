# BankIA - Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [1.0.0] - 2025-11-05

### Ajouté
- Parser CSV avec détection automatique du format
- Support point-virgule et virgule comme séparateurs
- Gestion des accents dans les colonnes (Débit, Crédit, Libellé)
- Parsing des dates en format DD/MM/YYYY
- Conversion automatique des montants (virgule → point)
- Extraction des références de factures dans les libellés
- Matching intelligent avec factures Dolibarr impayées
- Score de confiance pour chaque match (0-100%)
- Création de paiements dans Dolibarr
- Création combinée paiement + ligne bancaire
- Interface web complète avec drag & drop
- Gestion des erreurs API Dolibarr
- Validation des montants avant création de paiement
- Retour du statut de facture après paiement

### Technique
- Architecture Flask avec endpoints REST
- Client API Dolibarr avec gestion d'erreurs
- Algorithme de matching multi-critères
- Nettoyage JSON (NaN → None)
- Support multi-encodages CSV

---

## [Unreleased] - Fonctionnalités en développement

### Ajouté - Version 1.1.0 (En cours)
- ✅ Historique des paiements créés (base de données SQLite)
- ✅ Affichage de l'historique dans l'interface
- ✅ Statistiques des paiements (total créés, montant total, aujourd'hui, annulés)
- ✅ Annulation de paiements dans l'historique
- ✅ Journal des actions utilisateur
- ✅ Enregistrement automatique lors de la création de paiements

### Planifié
- Filtres et recherche dans les transactions
- Export Excel des résultats
- Validation par étapes (workflow)
- Matching automatique en lot
- Règles de matching personnalisables
- Interface de rapprochement bancaire

---

## Légende

- `Ajouté` : Nouvelles fonctionnalités
- `Modifié` : Changements dans les fonctionnalités existantes
- `Déprécié` : Fonctionnalités qui seront supprimées
- `Supprimé` : Fonctionnalités supprimées
- `Corrigé` : Corrections de bugs
- `Sécurité` : Corrections de vulnérabilités

