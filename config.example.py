"""
Configuration pour l'application BankIA
Copiez ce fichier en config.py et remplissez vos valeurs
"""
import os

# Configuration Dolibarr API
DOLIBARR_URL = os.getenv('DOLIBARR_URL', 'https://votre-dolibarr.com/api/index.php')
DOLIBARR_BASE_URL = os.getenv('DOLIBARR_BASE_URL', 'https://votre-dolibarr.com')
DOLIBARR_API_KEY = os.getenv('DOLIBARR_API_KEY', 'VOTRE_CLE_API_DOLIBARR')
DOLIBARR_API_LOGIN = os.getenv('DOLIBARR_API_LOGIN', 'admin')

# Configuration OpenAI pour extraction PDF
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'VOTRE_CLE_API_OPENAI')

# Configuration Flask
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
UPLOAD_FOLDER = 'uploads'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Configuration matching
AMOUNT_TOLERANCE = 0.01  # Tolérance pour le matching de montant
DATE_TOLERANCE_DAYS = 7  # Nombre de jours de tolérance pour le matching de date

# Allowed file extensions
ALLOWED_EXTENSIONS = {'csv', 'pdf', 'xlsx', 'xls'}
