# Guide de dépannage - Erreur 404 API Dolibarr

## Problème : Erreur 404 sur l'endpoint bankaccounts

Si vous rencontrez une erreur 404 lors de la récupération des comptes bancaires, voici les causes possibles et solutions :

### 1. Vérifier que le module Banque est activé

Dans Dolibarr :
- Allez dans **Home > Setup > Modules/Features**
- Cherchez le module **"Bank"** ou **"Banque"**
- Assurez-vous qu'il est **activé** (icône verte)

### 2. Vérifier l'URL de l'API

L'URL dans `config.py` doit être au format :
```
https://votre-domaine.com/dolibarr/api/index.php
```

Testez l'URL directement dans votre navigateur :
```
https://marina.doli.bar/dolibarr/api/index.php/invoices?DOLAPIKEY=votre_cle
```

### 3. Vérifier la clé API

Dans Dolibarr :
- Allez dans **Home > Setup > API Keys**
- Créez une clé API si vous n'en avez pas
- Assurez-vous que la clé a les droits nécessaires :
  - **Read** pour les factures (invoices)
  - **Read** pour les comptes bancaires (bankaccounts)

### 4. Tester la connexion

Utilisez l'endpoint de test dans l'application :
```
http://localhost:5000/api/dolibarr/test
```

### 5. Endpoints alternatifs

Si l'endpoint `bankaccounts` ne fonctionne pas, votre version de Dolibarr pourrait utiliser :
- `bankaccounts/index`
- `bank_accounts`
- Ou nécessiter des paramètres supplémentaires

### 6. Vérifier la version de Dolibarr

Certaines versions anciennes de Dolibarr peuvent avoir des endpoints différents. Vérifiez la documentation de votre version :
- Dolibarr 18+ : `/api/index.php/bankaccounts`
- Versions antérieures : peut nécessiter un format différent

### 7. Activer l'API REST

Assurez-vous que l'API REST est activée :
- **Home > Setup > Modules/Features**
- Cherchez **"REST API"** ou **"API REST"**
- Activez-le si nécessaire

### Solution temporaire

Si les comptes bancaires ne sont pas disponibles via l'API, vous pouvez :
1. Créer manuellement les lignes bancaires dans Dolibarr après le matching
2. Utiliser uniquement le matching avec les factures (sans comptes bancaires)

### Vérification rapide

Dans votre console PowerShell, testez :
```powershell
python -c "from dolibarr_client import DolibarrClient; from config import DOLIBARR_URL, DOLIBARR_API_KEY; client = DolibarrClient(); print('URL:', client.base_url); print('Test invoices:', client.get_invoices(limit=1))"
```

