# Guide d'installation BankIA

## Étape 1 : Installation de Python

Python n'est pas encore installé sur votre système. Voici comment l'installer :

### Option 1 : Installation depuis python.org (Recommandé)

1. Allez sur https://www.python.org/downloads/
2. Téléchargez Python 3.11 ou supérieur pour Windows
3. Pendant l'installation, **cochez la case "Add Python to PATH"** (très important !)
4. Cliquez sur "Install Now"

### Option 2 : Installation depuis Microsoft Store

1. Ouvrez le Microsoft Store
2. Recherchez "Python 3.11" ou "Python 3.12"
3. Cliquez sur "Installer"

## Étape 2 : Vérifier l'installation

Ouvrez un nouveau PowerShell et exécutez :

```powershell
python --version
```

Vous devriez voir quelque chose comme `Python 3.11.x`

## Étape 3 : Installation des dépendances

Une fois Python installé, exécutez dans le dossier BankIA :

```powershell
python -m pip install -r requirements.txt
```

OU si `python` ne fonctionne pas :

```powershell
python3 -m pip install -r requirements.txt
```

OU :

```powershell
py -m pip install -r requirements.txt
```

## Étape 4 : Configuration

Avant de lancer l'application, configurez vos paramètres Dolibarr dans `config.py` :

```python
DOLIBARR_URL = 'http://votre-dolibarr.com/api/index.php'
DOLIBARR_API_KEY = 'votre_cle_api'
DOLIBARR_API_LOGIN = 'admin'
```

## Étape 5 : Lancement

```powershell
python app.py
```

L'application sera accessible sur http://localhost:5000

## Dépannage

Si vous rencontrez des erreurs :

1. **"Python n'est pas reconnu"** : Python n'est pas dans votre PATH. Réinstallez Python en cochant "Add Python to PATH"

2. **"pip n'est pas reconnu"** : Utilisez `python -m pip` au lieu de `pip` directement

3. **Erreur de connexion à Dolibarr** : Vérifiez que :
   - L'URL Dolibarr est correcte
   - L'API REST est activée dans Dolibarr
   - La clé API est valide

