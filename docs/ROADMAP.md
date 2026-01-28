# BankIA - Plan de développement

## État actuel: Version 1.0.0 ✅

### Fonctionnalités complètes
- ✅ Parsing CSV avec détection automatique
- ✅ Matching intelligent avec Dolibarr
- ✅ Création de paiements
- ✅ Création paiement + ligne bancaire
- ✅ Interface web complète

---

## Prochaines étapes (Priorité)

### Phase 1: Améliorations UX immédiates (1-2 semaines)

#### 1. Historique des paiements créés
**Statut**: ✅ Complété
**Priorité**: Haute
**Description**: 
- ✅ Enregistrer chaque paiement créé dans une base de données (SQLite)
- ✅ Afficher l'historique dans l'interface
- ✅ Permettre l'annulation si nécessaire
- ✅ Statistiques des paiements

**Fichiers modifiés**:
- ✅ `app.py`: Endpoints historique ajoutés
- ✅ `templates/index.html`: Section historique ajoutée
- ✅ `database.py`: Module SQLite créé

#### 2. Filtres et recherche
**Statut**: ✅ Complété
**Priorité**: Haute
**Description**:
- ✅ Filtrer par score, montant, statut
- ✅ Recherche dans libellés
- ✅ Tri multi-colonnes (date, montant, score, libellé)
- ✅ Compteur de résultats filtrés

**Fichiers modifiés**:
- ✅ `templates/index.html`: Interface filtres et fonctions JavaScript ajoutées

#### 3. Export Excel
**Statut**: 📋 À faire
**Priorité**: Moyenne
**Description**:
- Export des résultats de matching en Excel
- Inclure toutes les colonnes pertinentes
- Formatage professionnel

**Fichiers à modifier**:
- `app.py`: Ajouter endpoint export
- Nouveau: `export.py`: Logique d'export Excel

#### 4. Validation par étapes
**Statut**: 📋 À faire
**Priorité**: Moyenne
**Description**:
- Workflow: Draft → Validé → Créé
- Commentaires sur transactions
- Validation batch

**Fichiers à modifier**:
- `app.py`: Ajouter endpoints validation
- `templates/index.html`: UI workflow
- `database.py`: Stocker états

---

### Phase 2: Matching avancé (2-3 semaines)

#### 5. Matching automatique en lot
**Statut**: 📋 À faire
**Priorité**: Haute
**Description**:
- Bouton "Tout matcher automatiquement"
- Filtre par score minimum (ex: >80%)
- Création automatique pour matches sûrs

#### 6. Règles de matching personnalisables
**Statut**: 📋 À faire
**Priorité**: Moyenne
**Description**:
- Interface de configuration des règles
- Pondération des critères
- Sauvegarde des règles

---

### Phase 3: Rapprochement bancaire (3-4 semaines)

#### 7. Interface de rapprochement visuel
**Statut**: 📋 À faire
**Priorité**: Haute
**Description**:
- Vue côte à côte: CSV vs Dolibarr
- Cocher transactions rapprochées
- État de rapprochement

---

## Structure de travail

### Pour chaque fonctionnalité:
1. ✅ Lire la documentation
2. ✅ Identifier les fichiers à modifier
3. ✅ Planifier l'implémentation
4. ✅ Développer
5. ✅ Tester
6. ✅ Mettre à jour la documentation
7. ✅ Marquer comme complété

---

## Checklist de développement

### Avant de commencer une fonctionnalité:
- [ ] Lire `docs/DOCUMENTATION.md`
- [ ] Lire `docs/ROADMAP.md` (ce fichier)
- [ ] Identifier les dépendances
- [ ] Créer une branche si nécessaire

### Pendant le développement:
- [ ] Suivre les conventions de code existantes
- [ ] Ajouter des commentaires
- [ ] Tester manuellement
- [ ] Gérer les erreurs proprement

### Après le développement:
- [ ] Mettre à jour `DOCUMENTATION.md`
- [ ] Mettre à jour `ROADMAP.md`
- [ ] Vérifier compatibilité avec fonctionnalités existantes
- [ ] Documenter les changements dans changelog

---

**Dernière mise à jour**: 2025-11-05

