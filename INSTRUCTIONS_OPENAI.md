# Configuration OpenAI pour extraction PDF

## 📋 Fonctionnalité

L'application peut maintenant **créer automatiquement des factures fournisseurs** depuis des PDF grâce à l'IA :

1. **Upload d'un PDF** de facture fournisseur
2. **Extraction automatique** des informations (nom fournisseur, montant, date, etc.)
3. **Création automatique du tiers** dans Dolibarr (si non existant)
4. **Création de la facture fournisseur** dans Dolibarr

---

## 🔑 Configuration de la clé API OpenAI

### Option 1 : Via variable d'environnement (Recommandé)

**Windows PowerShell :**
```powershell
$env:OPENAI_API_KEY = "sk-votre-clé-api-ici"
```

**Windows CMD :**
```cmd
set OPENAI_API_KEY=sk-votre-clé-api-ici
```

**Linux/Mac :**
```bash
export OPENAI_API_KEY="sk-votre-clé-api-ici"
```

### Option 2 : Modifier directement `config.py`

Ouvrez `config.py` et remplacez :
```python
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
```

Par :
```python
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'sk-votre-clé-api-ici')
```

---

## 🎯 Obtenir une clé API OpenAI

1. Allez sur https://platform.openai.com/api-keys
2. Connectez-vous ou créez un compte
3. Cliquez sur "Create new secret key"
4. Copiez la clé (format: `sk-...`)
5. **Important** : Configurez un budget mensuel pour éviter les surprises

**Coût approximatif** : ~0.01-0.05€ par facture analysée (GPT-4 Vision)

---

## 🧪 Mode Simulation (sans clé API)

Si vous **n'avez pas de clé OpenAI**, l'application fonctionne en **mode simulation** :
- Les données sont simulées (nom fournisseur, montants, etc.)
- Utile pour tester le workflow sans coût
- Une fois prêt, ajoutez votre clé pour l'extraction réelle

---

## 📦 Installation des dépendances

```bash
pip install openai
```

**C'est tout !** GPT-4o supporte directement les PDF, pas besoin d'installer Poppler ou d'autres outils.

---

## 🚀 Utilisation

1. **Uploadez votre CSV** de relevé bancaire
2. **Faites le matching** avec Dolibarr
3. Pour les transactions **sans match** :
   - Section "🤖 Ou créer depuis PDF"
   - Cliquez sur "📄 Uploader facture PDF"
   - Sélectionnez la facture fournisseur (PDF)
   - L'IA extrait automatiquement les infos
   - La facture est créée dans Dolibarr

---

## ✨ Ce qui est extrait automatiquement

- ✅ Nom du fournisseur
- ✅ Numéro de facture
- ✅ Date de facture
- ✅ Montant HT, TVA, TTC
- ✅ Adresse, email, téléphone
- ✅ Description des prestations
- ✅ Conditions de paiement

Si le fournisseur n'existe pas dans Dolibarr, il est **créé automatiquement** !

---

## 🔧 Dépannage

### Erreur "openai module not found"
```bash
pip install openai
```

### Erreur "pdf2image not found"
```bash
pip install pdf2image
# Puis installer Poppler (voir ci-dessus)
```

### "Invalid API key"
- Vérifiez que votre clé commence par `sk-`
- Vérifiez qu'elle est active sur platform.openai.com
- Vérifiez qu'elle n'a pas expiré

### "Rate limit exceeded"
- Vous avez dépassé votre quota OpenAI
- Attendez quelques secondes ou augmentez votre limite

---

## 💡 Conseils

- **Testez d'abord en mode simulation** (sans clé API)
- **Vérifiez les données extraites** avant validation
- **Les PDF de bonne qualité** donnent de meilleurs résultats
- **L'IA comprend plusieurs langues** (français, anglais, etc.)

---

## 📞 Support

En cas de problème :
1. Vérifiez les logs dans le terminal Flask
2. Les messages d'erreur sont affichés dans l'interface
3. Le mode simulation permet de tester sans API

Bon matching ! 🚀

