"""
Application Flask principale pour BankIA
"""
# Forcer UTF-8 pour Windows
import sys
import os
if sys.platform == 'win32':
    # Désactiver les émojis sur Windows pour éviter UnicodeEncodeError
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH, DOLIBARR_BASE_URL
from csv_parser import BankStatementParser
from dolibarr_client import DolibarrClient
from matcher import TransactionMatcher
from database import Database
from pdf_extractor import PdfExtractor
from datetime import datetime
import json
import pandas as pd
import numpy as np

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# DÉSACTIVER COMPLÈTEMENT LE CACHE (pour le développement)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.jinja_env.auto_reload = True

# Créer le dossier uploads s'il n'existe pas
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialiser les clients
parser = BankStatementParser()
dolibarr = DolibarrClient()
matcher = TransactionMatcher()
db = Database()
pdf_extractor = PdfExtractor()

# Helper pour les logs sans émojis sur Windows
def safe_print(message):
    """Print sans émojis pour éviter UnicodeEncodeError sur Windows"""
    try:
        print(message)
    except UnicodeEncodeError:
        # Remplacer les émojis par du texte
        clean_msg = message.encode('ascii', 'replace').decode('ascii')
        print(clean_msg)


def allowed_file(filename):
    """Vérifie si le fichier est autorisé"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Page principale"""
    from flask import make_response
    response = make_response(render_template('index.html'))
    # Forcer le navigateur à ne PAS mettre en cache
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/test')
def test_page():
    """Page de test simple"""
    from flask import make_response
    response = make_response(render_template('test.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/simple')
def simple_upload():
    """Page d'upload simplifiee"""
    from flask import make_response
    response = make_response(render_template('upload_simple.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/facture')
def invoice_upload():
    """Page d'upload de facture fournisseur avec extraction IA"""
    from flask import make_response
    response = make_response(render_template('invoice_upload.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/rapprochement')
def reconciliation():
    """Page de rapprochement bancaire"""
    from flask import make_response
    response = make_response(render_template('reconciliation.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Endpoint pour uploader un fichier CSV"""
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Parser le CSV
            transactions = parser.parse(filepath)
            
            # Convertir les transactions en format JSON-sérialisable
            # Remplacer NaN par None et s'assurer que tous les types sont compatibles JSON
            def clean_for_json(obj):
                """Récursivement nettoie un objet pour la sérialisation JSON"""
                if isinstance(obj, dict):
                    return {k: clean_for_json(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_for_json(item) for item in obj]
                elif pd.isna(obj) or (isinstance(obj, float) and np.isnan(obj)):
                    return None
                elif isinstance(obj, (np.integer, np.floating)):
                    return float(obj) if isinstance(obj, np.floating) else int(obj)
                elif isinstance(obj, (int, float, str, bool, type(None))):
                    return obj
                else:
                    return str(obj)
            
            transactions_json = [clean_for_json(trans) for trans in transactions]
            
            return jsonify({
                'success': True,
                'filename': filename,
                'transactions_count': len(transactions_json),
                'transactions': transactions_json
            })
        except Exception as e:
            return jsonify({'error': f'Erreur lors du parsing: {str(e)}'}), 500
    
    return jsonify({'error': 'Type de fichier non autorisé'}), 400


@app.route('/api/match', methods=['POST'])
def match_transactions():
    """Endpoint pour matcher les transactions avec Dolibarr"""
    data = request.get_json()
    
    if not data or 'transactions' not in data:
        return jsonify({'error': 'Données invalides'}), 400
    
    transactions = data['transactions']
    account_id = data.get('account_id')
    
    try:
        # Récupérer les factures clients impayées
        customer_invoices = dolibarr.get_invoices(status='unpaid', limit=500)
        print(f"Factures clients récupérées: {len(customer_invoices)}")
        
        # Récupérer les factures fournisseurs impayées
        supplier_invoices = dolibarr.get_supplier_invoices(status='unpaid', limit=500)
        print(f"Factures fournisseurs récupérées: {len(supplier_invoices)}")
        
        # Récupérer les lignes bancaires si un compte est spécifié
        bank_lines = []
        if account_id:
            bank_lines = dolibarr.get_bank_lines(account_id)
        
        # Faire le matching
        matched_transactions = matcher.match_transactions(
            transactions, 
            customer_invoices,
            supplier_invoices,
            bank_lines
        )
        
        return jsonify({
            'success': True,
            'matched_transactions': matched_transactions
        })
    
    except Exception as e:
        import traceback
        print(f"Erreur lors du matching: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Erreur lors du matching: {str(e)}'}), 500


@app.route('/api/dolibarr/accounts', methods=['GET'])
def get_accounts():
    """Récupère la liste des comptes bancaires depuis Dolibarr"""
    try:
        accounts = dolibarr.get_bank_accounts()
        if accounts:
            return jsonify({'success': True, 'accounts': accounts})
        else:
            return jsonify({
                'success': False, 
                'accounts': [],
                'error': 'Aucun compte bancaire trouvé ou endpoint non disponible. Vérifiez la configuration Dolibarr.'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Erreur: {str(e)}', 'accounts': []}), 500


@app.route('/api/dolibarr/test', methods=['GET'])
def test_dolibarr():
    """Test la connexion à Dolibarr"""
    try:
        # Tester avec un endpoint simple comme les factures
        invoices = dolibarr.get_invoices(status='unpaid', limit=1)
        return jsonify({
            'success': True,
            'message': 'Connexion à Dolibarr réussie',
            'config': {
                'url': dolibarr.base_url,
                'api_key_set': bool(dolibarr.api_key and dolibarr.api_key != 'your_api_key_here')
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erreur de connexion: {str(e)}',
            'message': 'Vérifiez votre configuration dans config.py'
        }), 500


@app.route('/api/dolibarr/config', methods=['GET'])
def get_dolibarr_config():
    """Retourne la configuration Dolibarr pour les liens"""
    return jsonify({
        'success': True,
        'base_url': DOLIBARR_BASE_URL,
        'invoice_url': f'{DOLIBARR_BASE_URL}/compta/facture/card.php?facid=',
        'supplier_invoice_url': f'{DOLIBARR_BASE_URL}/fourn/facture/card.php?facid=',
        'thirdparty_url': f'{DOLIBARR_BASE_URL}/societe/card.php?socid='
    })


@app.route('/api/dolibarr/invoices', methods=['GET'])
def get_invoices():
    """Récupère la liste des factures impayées depuis Dolibarr"""
    try:
        status = request.args.get('status', 'unpaid')
        invoices = dolibarr.get_invoices(status=status, limit=500)
        return jsonify({'success': True, 'invoices': invoices})
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/invoices/all', methods=['GET'])
def get_all_invoices():
    """Récupère toutes les factures (clients + fournisseurs) pour le matching manuel"""
    try:
        status = request.args.get('status', 'unpaid')
        
        # Récupérer factures clients
        customer_invoices = dolibarr.get_invoices(status=status, limit=500)
        customer_list = []
        for inv in customer_invoices:
            # Calculer le montant à afficher
            total = float(inv.get('total_ttc', 0))
            remaintopay_raw = inv.get('remaintopay')
            
            # Si remaintopay est défini et > 0, l'utiliser, sinon utiliser le total
            if remaintopay_raw is not None and float(remaintopay_raw) > 0:
                remaintopay = float(remaintopay_raw)
            else:
                remaintopay = total
            
            customer_list.append({
                'id': inv.get('id'),
                'ref': inv.get('ref', ''),
                'ref_ext': inv.get('ref_ext', ''),
                'type': 'customer',
                'type_label': 'Client',
                'thirdparty_name': inv.get('thirdparty', {}).get('name', 'N/A') if inv.get('thirdparty') else 'N/A',
                'total': total,
                'remaintopay': remaintopay,
                'date': inv.get('date', ''),
                'status': inv.get('status', '')
            })
        
        # Récupérer factures fournisseurs
        supplier_invoices = dolibarr.get_supplier_invoices(status=status, limit=500)
        supplier_list = []
        
        # Cache pour éviter de récupérer plusieurs fois le même tiers
        thirdparty_cache = {}
        
        for inv in supplier_invoices:
            # Essayer de récupérer le nom du fournisseur
            thirdparty_name = inv.get('thirdparty_name') or inv.get('socname')
            
            # Si pas de nom, essayer de récupérer via l'API
            if not thirdparty_name and inv.get('socid'):
                socid = inv.get('socid')
                if socid in thirdparty_cache:
                    thirdparty_name = thirdparty_cache[socid]
                else:
                    try:
                        thirdparty = dolibarr.get_thirdparty(int(socid))
                        if thirdparty:
                            thirdparty_name = thirdparty.get('name', f"ID:{socid}")
                            thirdparty_cache[socid] = thirdparty_name
                        else:
                            thirdparty_name = f"ID:{socid}"
                    except:
                        thirdparty_name = f"ID:{socid}"
            
            # Fallback sur ref_supplier si toujours pas de nom
            if not thirdparty_name:
                thirdparty_name = inv.get('ref_supplier', 'N/A')
            
            # Calculer le montant à afficher
            total = float(inv.get('total_ttc') or inv.get('total_ht') or 0)
            remaintopay_raw = inv.get('remaintopay')
            
            # Si remaintopay est défini et > 0, l'utiliser, sinon utiliser le total
            if remaintopay_raw is not None and float(remaintopay_raw) > 0:
                remaintopay = float(remaintopay_raw)
            else:
                remaintopay = total
            
            supplier_list.append({
                'id': inv.get('id'),
                'ref': inv.get('ref', ''),
                'ref_supplier': inv.get('ref_supplier', ''),
                'type': 'supplier',
                'type_label': 'Fournisseur',
                'thirdparty_name': thirdparty_name,
                'total': total,
                'remaintopay': remaintopay,
                'date': inv.get('date', ''),
                'status': inv.get('status', '')
            })
        
        # Combiner et trier par date
        all_invoices = customer_list + supplier_list
        all_invoices.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'invoices': all_invoices,
            'count': {
                'customer': len(customer_list),
                'supplier': len(supplier_list),
                'total': len(all_invoices)
            }
        })
    except Exception as e:
        import traceback
        print(f"Erreur lors de la récupération des factures: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/dolibarr/payment-modes', methods=['GET'])
def get_payment_modes():
    """Retourne les modes de paiement disponibles"""
    # Modes de paiement courants dans Dolibarr
    # Note: Ceci devrait normalement venir de l'API Dolibarr
    payment_modes = [
        {'id': 2, 'code': 'VIR', 'label': 'Virement'},
        {'id': 3, 'code': 'PRE', 'label': 'Prélèvement'},
        {'id': 4, 'code': 'CHQ', 'label': 'Chèque'},
        {'id': 5, 'code': 'CB', 'label': 'Carte bancaire'},
        {'id': 6, 'code': 'LIQ', 'label': 'Espèces'},
    ]
    return jsonify({'success': True, 'payment_modes': payment_modes})


@app.route('/api/dolibarr/create-payment', methods=['POST'])
def create_payment():
    """Créer un paiement dans Dolibarr (facture client ou fournisseur)"""
    data = request.get_json()
    
    required_fields = ['invoice_id', 'datepaye', 'paymentid', 'accountid']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Champ manquant: {field}'}), 400
    
    try:
        invoice_type = data.get('invoice_type', 'customer')
        
        # Récupérer la facture selon son type
        if invoice_type == 'supplier':
            invoice = dolibarr.get_supplier_invoice(data['invoice_id'])
        else:
            invoice = dolibarr.get_invoice(data['invoice_id'])
        
        if not invoice:
            return jsonify({'error': f'Facture {invoice_type} non trouvée'}), 404
        
        # Calculer le montant à payer (par défaut le reste à payer)
        remaintopay = invoice.get('remaintopay')
        total = invoice.get('total_ttc') or invoice.get('total_ht', 0)
        amount_to_pay = abs(float(remaintopay)) if remaintopay is not None else abs(float(total))
        
        # Utiliser le montant fourni ou le reste à payer
        transaction_amount = abs(float(data.get('amount', amount_to_pay)))
        
        print(f"Création paiement {invoice_type}: facture {data['invoice_id']}, montant {transaction_amount}€")
        
        payment_id = dolibarr.add_payment(
            invoice_id=data['invoice_id'],
            datepaye=data['datepaye'],
            paymentid=data['paymentid'],
            accountid=data['accountid'],
            closepaidinvoices=data.get('closepaidinvoices', 'yes'),
            num_payment=data.get('num_payment', ''),
            comment=data.get('comment', ''),
            invoice_type=invoice_type
        )
        
        if payment_id:
            # Récupérer la facture mise à jour pour voir le nouveau statut
            if invoice_type == 'supplier':
                updated_invoice = dolibarr.get_supplier_invoice(data['invoice_id'])
            else:
                updated_invoice = dolibarr.get_invoice(data['invoice_id'])
            
            # Enregistrer dans l'historique
            try:
                # Récupérer les informations du compte
                accounts = dolibarr.get_bank_accounts()
                account_label = next((acc.get('label', '') for acc in accounts if acc.get('id') == data['accountid']), '')
                
                # Récupérer le nom du tiers selon le type
                if invoice_type == 'supplier':
                    thirdparty_name = invoice.get('socid', 'N/A')
                else:
                    thirdparty_name = invoice.get('thirdparty', {}).get('name', '') if invoice.get('thirdparty') else ''
                
                db.add_payment(
                    payment_id=payment_id,
                    invoice_id=data['invoice_id'],
                    invoice_ref=invoice.get('ref', ''),
                    thirdparty_name=thirdparty_name,
                    amount=transaction_amount,
                    date_payment=datetime.fromtimestamp(int(data['datepaye'])).isoformat(),
                    account_id=data['accountid'],
                    account_label=account_label,
                    transaction_label=data.get('comment', '').replace('Paiement automatique depuis relevé bancaire - ', ''),
                    comment=data.get('comment', '')
                )
            except Exception as e:
                print(f"Erreur lors de l'enregistrement dans l'historique: {e}")
            
            return jsonify({
                'success': True, 
                'payment_id': payment_id,
                'invoice': updated_invoice,
                'message': 'Paiement créé avec succès'
            })
        else:
            return jsonify({'error': 'Échec de la création du paiement'}), 500
    
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/dolibarr/create-payment-and-bank-line', methods=['POST'])
def create_payment_and_bank_line():
    """Créer un paiement ET une ligne bancaire dans Dolibarr"""
    data = request.get_json()
    
    required_fields = ['invoice_id', 'datepaye', 'paymentid', 'accountid', 'label', 'amount']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Champ manquant: {field}'}), 400
    
    try:
        # 1. Créer le paiement
        invoice = dolibarr.get_invoice(data['invoice_id'])
        if not invoice:
            return jsonify({'error': 'Facture non trouvée'}), 404
        
        payment_id = dolibarr.add_payment(
            invoice_id=data['invoice_id'],
            datepaye=data['datepaye'],
            paymentid=data['paymentid'],
            accountid=data['accountid'],
            closepaidinvoices=data.get('closepaidinvoices', 'yes'),
            num_payment=data.get('num_payment', ''),
            comment=data.get('comment', '')
        )
        
        if not payment_id:
            return jsonify({'error': 'Échec de la création du paiement'}), 500
        
        # 2. Créer la ligne bancaire
        line_id = None
        bank_line_created = False
        try:
            line_id = dolibarr.add_bank_line(
                account_id=data['accountid'],
                date=data['datepaye'],
                type=data.get('bank_line_type', 'VIR'),
                label=data['label'],
                amount=data['amount'],
                category=data.get('category', 0),
                accountancycode=data.get('accountancycode', ''),
                num_releve=data.get('num_releve', '')
            )
            bank_line_created = line_id is not None
        except Exception as e:
            # Si la création de la ligne bancaire échoue, on continue quand même
            print(f"Erreur lors de la création de la ligne bancaire: {e}")
        
        # 3. Récupérer la facture mise à jour
        updated_invoice = dolibarr.get_invoice(data['invoice_id'])
        
        # Enregistrer dans l'historique
        try:
            accounts = dolibarr.get_bank_accounts()
            account_label = next((acc.get('label', '') for acc in accounts if acc.get('id') == data['accountid']), '')
            
            db.add_payment(
                payment_id=payment_id,
                invoice_id=data['invoice_id'],
                invoice_ref=invoice.get('ref', ''),
                thirdparty_name=invoice.get('thirdparty', {}).get('name', '') if invoice.get('thirdparty') else '',
                amount=abs(float(data['amount'])),
                date_payment=datetime.fromtimestamp(int(data['datepaye'])).isoformat(),
                account_id=data['accountid'],
                account_label=account_label,
                transaction_label=data.get('label', ''),
                comment=data.get('comment', '')
            )
            
            if bank_line_created and line_id:
                db.add_bank_line(
                    line_id=line_id,
                    account_id=data['accountid'],
                    account_label=account_label,
                    amount=abs(float(data['amount'])),
                    date_line=datetime.fromtimestamp(int(data['datepaye'])).isoformat(),
                    label=data.get('label', ''),
                    type=data.get('bank_line_type', 'VIR')
                )
        except Exception as e:
            print(f"Erreur lors de l'enregistrement dans l'historique: {e}")
        
        return jsonify({
            'success': True,
            'payment_id': payment_id,
            'bank_line_id': line_id,
            'bank_line_created': bank_line_created,
            'invoice': updated_invoice,
            'message': f'Paiement créé avec succès{" et ligne bancaire créée" if bank_line_created else ""}'
        })
    
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/dolibarr/create-bank-line', methods=['POST'])
def create_bank_line():
    """Créer une ligne bancaire dans Dolibarr"""
    data = request.get_json()
    
    required_fields = ['account_id', 'date', 'type', 'label', 'amount']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Champ manquant: {field}'}), 400
    
    try:
        line_id = dolibarr.add_bank_line(
            account_id=data['account_id'],
            date=data['date'],
            type=data['type'],
            label=data['label'],
            amount=data['amount'],
            category=data.get('category', 0),
            cheque_number=data.get('cheque_number', ''),
            accountancycode=data.get('accountancycode', ''),
            datev=data.get('datev'),
            num_releve=data.get('num_releve', '')
        )
        
        if line_id:
            return jsonify({'success': True, 'line_id': line_id})
        else:
            return jsonify({'error': 'Échec de la création de la ligne bancaire'}), 500
    
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/history/payments', methods=['GET'])
def get_payment_history():
    """Récupère l'historique des paiements créés"""
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        # Filtres optionnels
        filters = {}
        if request.args.get('date_from'):
            filters['date_from'] = request.args.get('date_from')
        if request.args.get('date_to'):
            filters['date_to'] = request.args.get('date_to')
        if request.args.get('invoice_id'):
            filters['invoice_id'] = int(request.args.get('invoice_id'))
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
        
        payments = db.get_payment_history(limit=limit, offset=offset, filters=filters)
        
        return jsonify({
            'success': True,
            'payments': payments,
            'count': len(payments)
        })
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/history/statistics', methods=['GET'])
def get_statistics():
    """Récupère les statistiques sur les paiements"""
    try:
        stats = db.get_statistics()
        return jsonify({'success': True, 'statistics': stats})
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/history/payments/<int:record_id>/cancel', methods=['POST'])
def cancel_payment(record_id):
    """Annule un paiement dans l'historique"""
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'Annulation manuelle')
        
        success = db.cancel_payment(record_id, reason)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Paiement marqué comme annulé'
            })
        else:
            return jsonify({'error': 'Paiement non trouvé'}), 404
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/invoice/test-pdf', methods=['GET'])
def test_pdf_endpoint():
    """Test simple pour vérifier que l'endpoint PDF fonctionne"""
    return jsonify({
        'success': True,
        'message': 'Endpoint PDF OK',
        'pdf_extractor_loaded': pdf_extractor is not None
    })


@app.route('/api/invoice/create-from-pdf', methods=['POST'])
def create_invoice_from_pdf():
    """Crée une facture fournisseur depuis un PDF via extraction IA"""
    print("\n" + "="*60)
    print("DÉBUT TRAITEMENT PDF")
    print("="*60)
    
    try:
        # Vérifier si un fichier PDF est présent
        print(f"1. Vérification fichier PDF...")
        print(f"   request.files: {list(request.files.keys())}")
        
        if 'pdf' not in request.files:
            print("   [ERR] Aucun fichier 'pdf' dans request.files")
            return jsonify({'error': 'Aucun fichier PDF fourni'}), 400
        
        pdf_file = request.files['pdf']
        print(f"   [OK] Fichier trouvé: {pdf_file.filename}")
        
        if pdf_file.filename == '':
            print("   [ERR] Nom de fichier vide")
            return jsonify({'error': 'Nom de fichier vide'}), 400
        
        if not pdf_file.filename.lower().endswith('.pdf'):
            print(f"   [ERR] Extension invalide: {pdf_file.filename}")
            return jsonify({'error': 'Le fichier doit être un PDF'}), 400
        
        # Récupérer les données de la transaction
        print(f"2. Récupération données transaction...")
        transaction_data_raw = request.form.get('transaction_data', '{}')
        print(f"   Raw data: {transaction_data_raw[:100]}...")
        
        try:
            transaction_data = json.loads(transaction_data_raw)
            print(f"   [OK] Transaction data parsée: montant={transaction_data.get('amount')}")
        except json.JSONDecodeError as e:
            print(f"   [ERR] Erreur parsing JSON: {e}")
            return jsonify({'error': f'Données transaction invalides: {str(e)}'}), 400
        
        # Sauvegarder le PDF temporairement
        print(f"3. Sauvegarde du PDF...")
        filename = secure_filename(pdf_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        print(f"   Chemin: {filepath}")
        
        pdf_file.save(filepath)
        print(f"   [OK] PDF sauvegardé")
        
        print(f"\n[PDF] PDF recu: {filename}")
        
        # Extraire les données via IA
        print(f"\n4. [IA] Extraction des données via IA...")
        try:
            extracted_data = pdf_extractor.extract_invoice_data(filepath)
            print(f"   [OK] Extraction terminée")
        except Exception as e:
            print(f"   [ERR] Erreur extraction: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Erreur extraction PDF: {str(e)}'}), 500
        
        if not extracted_data:
            print("   [ERR] Aucune donnée extraite")
            return jsonify({'error': 'Impossible d\'extraire les données du PDF'}), 500
        
        print(f"   Fournisseur: {extracted_data.get('supplier_name')}")
        print(f"   Montant TTC: {extracted_data.get('amount_ttc')}€")
        print(f"   Référence: {extracted_data.get('invoice_ref')}")
        
        # Étape 1: Chercher ou créer le tiers
        print(f"\n5. Recherche ou création du tiers...")
        supplier_name = extracted_data.get('supplier_name', '').strip()
        print(f"   Nom fournisseur: '{supplier_name}'")
        
        if not supplier_name:
            print("   [ERR] Nom fournisseur vide")
            return jsonify({'error': 'Nom du fournisseur non trouvé dans le PDF'}), 400
        
        # Rechercher le tiers existant
        print(f"   [SEARCH] Recherche dans Dolibarr...")
        try:
            existing_thirdparties = dolibarr.search_thirdparty(supplier_name)
            print(f"   Résultats: {len(existing_thirdparties)} tiers trouvés")
        except Exception as e:
            print(f"   [ERR] Erreur recherche: {e}")
            existing_thirdparties = []
        
        socid = None
        if existing_thirdparties and len(existing_thirdparties) > 0:
            # Dolibarr peut utiliser 'id' ou 'rowid' selon la version
            tp = existing_thirdparties[0]
            raw_id = tp.get('id') or tp.get('rowid')
            # S'assurer que c'est un entier valide
            try:
                socid = int(raw_id)
                print(f"[OK] Tiers trouvé: ID {socid}")
            except (ValueError, TypeError):
                print(f"[WARN] ID tiers invalide: {raw_id}, création d'un nouveau tiers...")
                socid = None
        
        # Si pas de tiers trouvé ou ID invalide, créer le tiers
        if not socid:
            print(f"[NEW] Création du tiers: {supplier_name}")
            socid = dolibarr.create_thirdparty(
                name=supplier_name,
                supplier=True,
                address=extracted_data.get('address', ''),
                zip_code=extracted_data.get('zip_code', ''),
                town=extracted_data.get('town', ''),
                email=extracted_data.get('email', ''),
                phone=extracted_data.get('phone', '')
            )
            
            if not socid:
                return jsonify({'error': 'Impossible de créer le tiers dans Dolibarr'}), 500
            
            print(f"[OK] Tiers créé: ID {socid}")
        
        # Étape 2: Créer la facture fournisseur
        # Ajouter un timestamp pour garantir l'unicité de la référence
        timestamp_suffix = datetime.now().strftime('%Y%m%d%H%M%S')
        base_ref = extracted_data.get('invoice_ref', filename.replace('.pdf', ''))
        invoice_ref = f"{base_ref}-{timestamp_suffix}"
        # Gérer les valeurs None retournées par l'IA
        amount_ht = float(extracted_data.get('amount_ht') or 0)
        amount_ttc = float(extracted_data.get('amount_ttc') or 0)
        tva_amount = float(extracted_data.get('tva_amount') or 0)
        
        # Si montants manquants, utiliser le montant de la transaction
        if amount_ttc == 0 and transaction_data.get('amount'):
            amount_ttc = abs(float(transaction_data['amount']))
            amount_ht = amount_ttc / 1.20  # Supposer 20% TVA
            tva_amount = amount_ttc - amount_ht
        
        # Date de la facture
        invoice_date_str = extracted_data.get('invoice_date', '')
        print(f"   Date extraite du PDF: '{invoice_date_str}'")
        try:
            from dateutil.parser import parse
            parsed_date = parse(invoice_date_str, dayfirst=True)
            invoice_date = int(parsed_date.timestamp())
            print(f"   Date parsee: {parsed_date.strftime('%d/%m/%Y')} -> timestamp {invoice_date}")
        except Exception as date_err:
            print(f"   [WARN] Erreur parsing date '{invoice_date_str}': {date_err}")
            invoice_date = int(datetime.now().timestamp())
            print(f"   Utilisation date du jour: {datetime.now().strftime('%d/%m/%Y')}")
        
        print(f"[MONEY] Création facture: {invoice_ref}, {amount_ttc}€")
        
        description = extracted_data.get('description', 'Facture importée depuis PDF')
        
        # Format ligne selon l'exemple qui fonctionne
        tva_rate = (tva_amount / amount_ht * 100) if amount_ht > 0 else 0
        
        invoice_id = dolibarr.create_supplier_invoice(
            socid=socid,
            ref_supplier=invoice_ref,
            date_invoice=invoice_date,
            total_ht=amount_ht,
            total_tva=tva_amount,
            total_ttc=amount_ttc,
            note=f"Facture importée depuis PDF: {extracted_data.get('supplier_name', '')}",
            lines=[{
                'ref_product': 'SERVICE',
                'product_type': '1',
                'desc': description,
                'pu_ht': str(amount_ht),
                'subprice': str(amount_ht),
                'qty': '1',
                'tva_tx': f"{tva_rate:.2f}",
                'total_ht': str(amount_ht),
                'total_tva': str(tva_amount),
                'total_ttc': str(amount_ttc)
            }]
        )
        
        if not invoice_id:
            print("   [ERR] Échec création facture")
            return jsonify({'error': 'Impossible de créer la facture dans Dolibarr'}), 500
        
        print(f"   [OK] Facture créée: ID {invoice_id}")
        
        # Étape 3: Attacher le PDF à la facture
        print(f"\n6. Attachement du PDF à la facture...")
        attachment_result = None
        try:
            # La référence pour les factures fournisseurs brouillon est (PROVxx)
            invoice_ref_dolibarr = f"(PROV{invoice_id})"
            attachment_result = dolibarr.attach_document(
                module_part='supplier_invoice',
                ref=invoice_ref_dolibarr,
                filepath=filepath,
                filename=f"facture_{invoice_ref}.pdf",
                overwriteifexists=1
            )
            if attachment_result:
                print(f"   [OK] PDF attaché à la facture: {attachment_result}")
            else:
                print(f"   [WARN] Attachement du PDF échoué (facture créée quand même)")
        except Exception as e:
            print(f"   [WARN] Erreur attachement PDF: {e}")
        
        # Nettoyer le fichier temporaire
        print(f"\n7. Nettoyage...")
        try:
            os.remove(filepath)
            print(f"   [OK] Fichier temporaire supprimé")
        except Exception as e:
            print(f"   [WARN] Erreur suppression: {e}")
        
        print("\n" + "="*60)
        print("[OK] TRAITEMENT PDF TERMINÉ AVEC SUCCÈS")
        print("="*60 + "\n")
        
        return jsonify({
            'success': True,
            'invoice_id': invoice_id,
            'invoice_ref': invoice_ref,
            'thirdparty_name': supplier_name,
            'thirdparty_id': socid,
            'amount': amount_ttc,
            'extracted_data': extracted_data,
            'attachment': attachment_result,
            'message': 'Facture fournisseur créée avec succès' + (' et PDF attaché' if attachment_result else '')
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"\n" + "="*60)
        print(f"[ERR] ERREUR CRÉATION FACTURE DEPUIS PDF")
        print("="*60)
        print(f"Erreur: {str(e)}")
        print(f"Type: {type(e).__name__}")
        print(f"Traceback:")
        print(error_trace)
        print("="*60 + "\n")
        return jsonify({
            'error': f'Erreur: {str(e)}',
            'error_type': type(e).__name__,
            'traceback': error_trace
        }), 500


# ========== ENDPOINTS RECONCILIATION BANCAIRE ==========

@app.route('/api/reconciliation/import', methods=['POST'])
def import_bank_statement():
    """
    Importe un relevé bancaire en détectant les doublons
    Stocke les nouvelles transactions en base de données
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
        file.save(filepath)
        
        try:
            # Parser le CSV
            transactions = parser.parse(filepath)
            
            # Importer en base de données (détection doublons)
            result = db.import_transactions(transactions, saved_filename)
            
            return jsonify({
                'success': True,
                'filename': saved_filename,
                'total_in_file': len(transactions),
                'new_transactions': result['new_count'],
                'duplicates': result['duplicate_count'],
                'message': f"{result['new_count']} nouvelles transactions importées, {result['duplicate_count']} doublons ignorés"
            })
        except Exception as e:
            import traceback
            print(f"Erreur import: {e}")
            print(traceback.format_exc())
            return jsonify({'error': f'Erreur lors du parsing: {str(e)}'}), 500
    
    return jsonify({'error': 'Type de fichier non autorisé'}), 400


@app.route('/api/reconciliation/transactions', methods=['GET'])
def get_transactions_to_reconcile():
    """
    Récupère les transactions RAPIDEMENT sans faire le matching
    Le matching sera fait en lazy-loading par transaction
    """
    try:
        status = request.args.get('status', 'pending')
        
        # Récupérer les transactions rapidement
        transactions = db.get_all_transactions(status=status if status != 'all' else None)
        
        # Formater les transactions sans faire le matching (rapide!)
        enriched_transactions = []
        
        for tx in transactions:
            # Formater la date
            try:
                from datetime import datetime as dt
                tx_date = dt.fromtimestamp(int(tx['date']))
                date_str = tx_date.strftime('%d/%m/%Y')
            except:
                date_str = ''
            
            # Extraire infos basiques du libellé (rapide, pas d'API)
            suggested_thirdparty = matcher.extract_thirdparty_from_label(tx['label'])
            extracted_ref = matcher.extract_invoice_ref_from_label(tx['label'])
            search_variants = matcher.get_thirdparty_search_variants(suggested_thirdparty) if suggested_thirdparty else []
            
            tx_data = {
                'id': tx['id'],
                'hash': tx['hash'],
                'date': tx['date'],
                'date_str': date_str,
                'label': tx['label'],
                'amount': tx['amount'],
                'status': tx['status'],
                'import_file': tx.get('import_file', ''),
                'matched_invoice_id': tx.get('matched_invoice_id'),
                'matched_invoice_ref': tx.get('matched_invoice_ref'),
                'matched_thirdparty': tx.get('matched_thirdparty'),
                'invoice_matches': [],  # Sera chargé en lazy
                'suggested_thirdparty': suggested_thirdparty,
                'search_variants': search_variants,
                'extracted_ref': extracted_ref,
                'matching_status': 'pending' if tx['status'] == 'pending' else 'done'
            }
            
            enriched_transactions.append(tx_data)
        
        return jsonify({
            'success': True,
            'transactions': enriched_transactions,
            'stats': db.get_transaction_stats()
        })
        
    except Exception as e:
        import traceback
        print(f"[API] Erreur get_transactions: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/reconciliation/transaction/<int:tx_id>/matches', methods=['GET'])
def get_transaction_matches(tx_id):
    """
    Récupère les matches pour UNE SEULE transaction (lazy loading)
    PRIORITÉ: Si une référence est extraite, chercher d'abord par référence
    """
    try:
        # Récupérer la transaction
        tx = db.get_transaction_by_id(tx_id)
        if not tx:
            return jsonify({'error': 'Transaction non trouvée'}), 404
        
        # Si déjà réconciliée, pas besoin de chercher
        if tx['status'] != 'pending':
            return jsonify({
                'success': True,
                'matches': [],
                'found_thirdparty': None
            })
        
        # Extraire infos
        suggested_thirdparty = matcher.extract_thirdparty_from_label(tx['label'])
        extracted_ref = matcher.extract_invoice_ref_from_label(tx['label'])
        search_variants = matcher.get_thirdparty_search_variants(suggested_thirdparty) if suggested_thirdparty else []
        
        # Parser la date
        try:
            from datetime import datetime as dt
            tx_date = dt.fromtimestamp(int(tx['date']))
            tx_year = tx_date.year
            tx_month = tx_date.month
        except:
            tx_year = None
            tx_month = None
        
        matches = []
        found_thirdparty = None
        is_debit = tx['amount'] < 0
        tx_amount = abs(tx['amount'])
        
        # ============ PRIORITÉ 1: Recherche par référence ============
        if extracted_ref:
            print(f"[MATCH] Recherche par référence: {extracted_ref}")
            try:
                invoice_by_ref = dolibarr.get_invoice_by_ref(extracted_ref)
                if invoice_by_ref:
                    print(f"[MATCH] Facture trouvée par référence: {invoice_by_ref.get('ref')}")
                    
                    # Calculer le score
                    inv_type = invoice_by_ref.get('_invoice_type', 'customer')
                    if is_debit:
                        total = abs(float(invoice_by_ref.get('total_ht') or invoice_by_ref.get('total_ttc') or 0))
                        remain = abs(float(invoice_by_ref.get('remaintopay') or total))
                    else:
                        total = abs(float(invoice_by_ref.get('total_ttc') or 0))
                        remain = abs(float(invoice_by_ref.get('remaintopay') or total))
                    
                    is_paid = remain == 0
                    match_amount = total if is_paid else remain
                    amount_diff = abs(tx_amount - match_amount)
                    
                    score = 150  # Score de base très élevé pour match par référence
                    reasons = [f"Référence exacte: {invoice_by_ref.get('ref')}"]
                    
                    # Bonus si montant correspond aussi
                    if amount_diff < 1:
                        score += 50
                        reasons.append("Montant exact")
                    elif amount_diff / max(tx_amount, match_amount, 1) < 0.05:
                        score += 20
                        reasons.append("Montant proche")
                    
                    matches.append({
                        'invoice': invoice_by_ref,
                        'invoice_type': inv_type,
                        'score': score,
                        'reasons': reasons,
                        'amount_diff': amount_diff,
                        'already_paid': is_paid
                    })
                    
                    # Récupérer le tiers de la facture
                    thirdparty_name = (invoice_by_ref.get('thirdparty', {}) or {}).get('name') or invoice_by_ref.get('socname', '')
                    if thirdparty_name:
                        found_thirdparty = {
                            'id': invoice_by_ref.get('socid') or invoice_by_ref.get('fk_soc'),
                            'name': thirdparty_name
                        }
            except Exception as e:
                print(f"[MATCH] Erreur recherche par référence: {e}")
        
        # ============ PRIORITÉ 2: Recherche par tiers ============
        if not matches and suggested_thirdparty:
            # Chercher le tiers dans Dolibarr
            for variant in search_variants[:3]:
                try:
                    thirdparties = dolibarr.search_thirdparty(variant)
                    if thirdparties:
                        found_thirdparty = {
                            'id': thirdparties[0].get('id'),
                            'name': thirdparties[0].get('name')
                        }
                        break
                except:
                    continue
            
            if found_thirdparty:
                # Récupérer les factures de ce tiers
                try:
                    thirdparty_invoices = dolibarr.get_thirdparty_invoices(
                        found_thirdparty['id'],
                        invoice_type='supplier' if is_debit else 'customer',
                        include_paid=True
                    )
                    
                    for inv in thirdparty_invoices:
                        # Récupérer le montant
                        if is_debit:
                            total = abs(float(inv.get('total_ht') or inv.get('total_ttc') or 0))
                            remain = abs(float(inv.get('remaintopay') or total))
                        else:
                            total = abs(float(inv.get('total_ttc') or 0))
                            remain = abs(float(inv.get('remaintopay') or total))
                        
                        is_paid = inv.get('_already_paid', False) or remain == 0
                        match_amount = total if is_paid else remain
                        
                        # Calculer le score
                        score = 0
                        reasons = []
                        
                        # 1. Correspondance de montant
                        amount_diff = abs(tx_amount - match_amount)
                        if amount_diff < 1:
                            score += 100
                            reasons.append("Montant exact")
                        elif amount_diff / max(tx_amount, match_amount, 1) < 0.01:
                            score += 80
                            reasons.append("Montant proche (1%)")
                        elif amount_diff / max(tx_amount, match_amount, 1) < 0.05:
                            score += 50
                            reasons.append("Montant proche (5%)")
                        
                        # 2. Correspondance de période
                        inv_ref = inv.get('ref', '')
                        inv_period = matcher.extract_period_from_invoice_ref(inv_ref)
                        
                        if inv_period and tx_year:
                            inv_month_num, inv_year_short = inv_period
                            inv_year_full = 2000 + int(inv_year_short)
                            
                            if inv_year_full == tx_year:
                                score += 30
                                reasons.append(f"Année OK ({inv_year_full})")
                                if int(inv_month_num) == tx_month:
                                    score += 20
                                    reasons.append(f"Mois OK ({inv_month_num})")
                            else:
                                score -= 50
                                reasons.append(f"Année différente")
                        
                        # 3. Correspondance de référence
                        if extracted_ref and matcher.refs_match(extracted_ref, inv_ref):
                            score += 80
                            reasons.append(f"Référence: {inv_ref}")
                        
                        if score > 20:
                            matches.append({
                                'invoice': inv,
                                'invoice_type': 'supplier' if is_debit else 'customer',
                                'score': score,
                                'reasons': reasons,
                                'amount_diff': amount_diff,
                                'already_paid': is_paid
                            })
                    
                except Exception as e:
                    print(f"Erreur récupération factures: {e}")
        
        # Trier par score et limiter
        matches.sort(key=lambda x: x.get('score', 0), reverse=True)
        matches = matches[:5]
        
        return jsonify({
            'success': True,
            'matches': matches,
            'found_thirdparty': found_thirdparty
        })
        
    except Exception as e:
        import traceback
        print(f"Erreur get_transaction_matches: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/reconciliation/match', methods=['POST'])
def reconcile_transaction():
    """
    Réconcilie une transaction avec une facture et crée le paiement si nécessaire
    Supporte le rapprochement avec factures déjà payées (sans création de paiement)
    """
    data = request.get_json()
    
    required_fields = ['transaction_id', 'invoice_id', 'invoice_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Champ manquant: {field}'}), 400
    
    try:
        transaction_id = data['transaction_id']
        invoice_id = data['invoice_id']
        invoice_type = data['invoice_type']
        account_id = data.get('account_id')
        payment_mode_id = data.get('payment_mode_id', 2)  # 2 = Virement par défaut
        create_payment = data.get('create_payment', True)
        is_already_paid = data.get('is_already_paid', False)
        
        # Récupérer la transaction
        transactions = db.get_all_transactions()
        tx = next((t for t in transactions if t['id'] == transaction_id), None)
        
        if not tx:
            return jsonify({'error': 'Transaction non trouvée'}), 404
        
        # Récupérer la facture
        if invoice_type == 'supplier':
            invoice = dolibarr.get_supplier_invoice(invoice_id)
        else:
            invoice = dolibarr.get_invoice(invoice_id)
        
        if not invoice:
            return jsonify({'error': 'Facture non trouvée'}), 404
        
        invoice_ref = invoice.get('ref', '')
        thirdparty_name = ''
        
        if invoice.get('thirdparty'):
            thirdparty_name = invoice['thirdparty'].get('name', '')
        elif invoice.get('socid'):
            thirdparty = dolibarr.get_thirdparty(int(invoice['socid']))
            if thirdparty:
                thirdparty_name = thirdparty.get('name', '')
        
        # Vérifier si la facture est déjà payée
        invoice_status = str(invoice.get('status', ''))
        invoice_paye = str(invoice.get('paye', '0'))
        already_paid = is_already_paid or invoice_status == '2' or invoice_paye == '1'
        
        payment_id = None
        message = 'Transaction réconciliée avec succès'
        
        # Créer le paiement seulement si demandé ET facture pas déjà payée
        if create_payment and account_id and not already_paid:
            payment_id = dolibarr.add_payment(
                invoice_id=invoice_id,
                datepaye=str(tx['date']),
                paymentid=payment_mode_id,
                accountid=account_id,
                closepaidinvoices='yes',
                comment=f"Réconciliation automatique - {tx['label']}",
                invoice_type=invoice_type
            )
            
            if payment_id:
                message = 'Transaction réconciliée et paiement créé'
                # Enregistrer dans l'historique des paiements
                try:
                    accounts = dolibarr.get_bank_accounts()
                    account_label = next((acc.get('label', '') for acc in accounts if acc.get('id') == account_id), '')
                    
                    db.add_payment(
                        payment_id=payment_id,
                        invoice_id=invoice_id,
                        invoice_ref=invoice_ref,
                        thirdparty_name=thirdparty_name,
                        amount=abs(tx['amount']),
                        date_payment=datetime.fromtimestamp(int(tx['date'])).isoformat(),
                        account_id=account_id,
                        account_label=account_label,
                        transaction_label=tx['label'],
                        comment=f"Réconciliation bancaire"
                    )
                except Exception as e:
                    print(f"Erreur enregistrement historique: {e}")
        elif already_paid:
            message = 'Transaction rapprochée (facture déjà payée)'
        
        # Marquer la transaction comme réconciliée
        db.reconcile_transaction(
            transaction_id=transaction_id,
            invoice_id=invoice_id,
            invoice_type=invoice_type,
            invoice_ref=invoice_ref,
            thirdparty_name=thirdparty_name,
            payment_id=payment_id
        )
        
        return jsonify({
            'success': True,
            'message': message,
            'payment_id': payment_id,
            'invoice_ref': invoice_ref,
            'thirdparty_name': thirdparty_name,
            'already_paid': already_paid
        })
        
    except Exception as e:
        import traceback
        print(f"Erreur reconcile: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/reconciliation/ignore', methods=['POST'])
def ignore_transaction():
    """
    Marque une transaction comme ignorée
    """
    data = request.get_json()
    
    if 'transaction_id' not in data:
        return jsonify({'error': 'transaction_id manquant'}), 400
    
    try:
        success = db.ignore_transaction(
            data['transaction_id'],
            data.get('reason', '')
        )
        
        if success:
            return jsonify({'success': True, 'message': 'Transaction ignorée'})
        else:
            return jsonify({'error': 'Transaction non trouvée'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/reconciliation/reset', methods=['POST'])
def reset_transaction():
    """
    Remet une transaction en statut pending
    """
    data = request.get_json()
    
    if 'transaction_id' not in data:
        return jsonify({'error': 'transaction_id manquant'}), 400
    
    try:
        success = db.reset_transaction(data['transaction_id'])
        
        if success:
            return jsonify({'success': True, 'message': 'Transaction réinitialisée'})
        else:
            return jsonify({'error': 'Transaction non trouvée'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/reconciliation/stats', methods=['GET'])
def get_reconciliation_stats():
    """
    Retourne les statistiques de réconciliation
    """
    try:
        stats = db.get_transaction_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reconciliation/batch', methods=['POST'])
def batch_reconcile():
    """
    Réconcilie plusieurs transactions en une seule requête
    """
    data = request.get_json()
    
    if 'matches' not in data or not isinstance(data['matches'], list):
        return jsonify({'error': 'Liste de matches manquante'}), 400
    
    try:
        account_id = data.get('account_id')
        payment_mode_id = data.get('payment_mode_id', 2)
        create_payments = data.get('create_payments', True)
        
        results = []
        success_count = 0
        error_count = 0
        
        for match in data['matches']:
            try:
                transaction_id = match['transaction_id']
                invoice_id = match['invoice_id']
                invoice_type = match.get('invoice_type', 'supplier')
                
                # Récupérer la transaction
                transactions = db.get_all_transactions()
                tx = next((t for t in transactions if t['id'] == transaction_id), None)
                
                if not tx:
                    results.append({'transaction_id': transaction_id, 'success': False, 'error': 'Transaction non trouvée'})
                    error_count += 1
                    continue
                
                # Récupérer la facture
                if invoice_type == 'supplier':
                    invoice = dolibarr.get_supplier_invoice(invoice_id)
                else:
                    invoice = dolibarr.get_invoice(invoice_id)
                
                if not invoice:
                    results.append({'transaction_id': transaction_id, 'success': False, 'error': 'Facture non trouvée'})
                    error_count += 1
                    continue
                
                invoice_ref = invoice.get('ref', '')
                thirdparty_name = ''
                
                if invoice.get('thirdparty'):
                    thirdparty_name = invoice['thirdparty'].get('name', '')
                elif invoice.get('socid'):
                    thirdparty = dolibarr.get_thirdparty(int(invoice['socid']))
                    if thirdparty:
                        thirdparty_name = thirdparty.get('name', '')
                
                payment_id = None
                
                # Créer le paiement si demandé
                if create_payments and account_id:
                    payment_id = dolibarr.add_payment(
                        invoice_id=invoice_id,
                        datepaye=str(tx['date']),
                        paymentid=payment_mode_id,
                        accountid=account_id,
                        closepaidinvoices='yes',
                        comment=f"Réconciliation batch - {tx['label']}",
                        invoice_type=invoice_type
                    )
                
                # Marquer comme réconcilié
                db.reconcile_transaction(
                    transaction_id=transaction_id,
                    invoice_id=invoice_id,
                    invoice_type=invoice_type,
                    invoice_ref=invoice_ref,
                    thirdparty_name=thirdparty_name,
                    payment_id=payment_id
                )
                
                results.append({
                    'transaction_id': transaction_id,
                    'success': True,
                    'payment_id': payment_id,
                    'invoice_ref': invoice_ref
                })
                success_count += 1
                
            except Exception as e:
                results.append({
                    'transaction_id': match.get('transaction_id'),
                    'success': False,
                    'error': str(e)
                })
                error_count += 1
        
        return jsonify({
            'success': True,
            'results': results,
            'success_count': success_count,
            'error_count': error_count,
            'message': f"{success_count} transactions réconciliées, {error_count} erreurs"
        })
        
    except Exception as e:
        import traceback
        print(f"Erreur batch: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/thirdparties/search', methods=['GET'])
def search_thirdparties():
    """
    Recherche des tiers par nom avec variantes automatiques
    Ex: "ORIO ILTUD" cherche aussi "ILTUD ORIO", "ORIO", "ILTUD"
    """
    name = request.args.get('name', '')
    
    if len(name) < 2:
        return jsonify({'success': True, 'thirdparties': []})
    
    try:
        # Générer les variantes de recherche
        search_variants = matcher.get_thirdparty_search_variants(name)
        
        all_results = []
        seen_ids = set()
        
        # Chercher avec max 2 variantes pour éviter trop d'appels API
        for variant in search_variants[:2]:
            try:
                results = dolibarr.search_thirdparty(variant)
                if not results:
                    continue
                    
                for tp in results[:10]:  # Max 10 par variante
                    tp_id = tp.get('id')
                    if tp_id and tp_id not in seen_ids:
                        seen_ids.add(tp_id)
                        
                        # Calculer le score de similarité
                        tp_name = tp.get('name', '') or tp.get('nom', '')
                        similarity = matcher.calculate_name_similarity(name, tp_name)
                        
                        all_results.append({
                            'id': tp_id,
                            'name': tp_name,
                            'name_alias': tp.get('name_alias', ''),
                            'is_supplier': tp.get('fournisseur') == '1' or tp.get('fournisseur') == 1,
                            'is_customer': tp.get('client') not in ['0', 0, None],
                            'town': tp.get('town', '') or tp.get('ville', ''),
                            'email': tp.get('email', ''),
                            'similarity': similarity,
                            'matched_variant': variant
                        })
            except Exception:
                pass  # Silencieux pour éviter le spam
        
        # Trier par score de similarité décroissant
        all_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        
        return jsonify({
            'success': True,
            'thirdparties': all_results[:20],  # Max 20 résultats
            'search_variants': search_variants[:3]  # Max 3 variantes affichées
        })
        
    except Exception as e:
        return jsonify({'success': True, 'thirdparties': [], 'error': str(e)})


@app.route('/api/thirdparties/<int:thirdparty_id>/invoices', methods=['GET'])
def get_thirdparty_invoices(thirdparty_id):
    """
    Récupère les factures d'un tiers spécifique (impayées + payées)
    """
    try:
        invoice_type = request.args.get('type', 'all')  # 'customer', 'supplier', 'all'
        include_paid = request.args.get('include_paid', 'true').lower() == 'true'
        
        invoices = []
        
        def add_invoices(inv_list, inv_type, is_paid=False):
            for inv in inv_list:
                # Vérifier le tiers
                if inv_type == 'customer':
                    thirdparty = inv.get('thirdparty', {})
                    if not thirdparty or str(thirdparty.get('id')) != str(thirdparty_id):
                        continue
                else:
                    if str(inv.get('socid')) != str(thirdparty_id):
                        continue
                
                total = float(inv.get('total_ttc') or inv.get('total_ht') or 0)
                remain = float(inv.get('remaintopay') or 0)
                
                invoices.append({
                    'id': inv.get('id'),
                    'ref': inv.get('ref', ''),
                    'ref_supplier': inv.get('ref_supplier', '') if inv_type == 'supplier' else '',
                    'type': inv_type,
                    'type_label': 'Client' if inv_type == 'customer' else 'Fournisseur',
                    'total': total,
                    'remaintopay': remain if not is_paid else 0,
                    'date': inv.get('date', ''),
                    'status': inv.get('status', ''),
                    'is_paid': is_paid
                })
        
        # Factures clients
        if invoice_type in ['customer', 'all']:
            # Impayées
            customer_unpaid = dolibarr.get_invoices(status='unpaid', limit=100)
            add_invoices(customer_unpaid, 'customer', is_paid=False)
            
            # Payées
            if include_paid:
                try:
                    customer_paid = dolibarr.get_invoices(status='paid', limit=100)
                    add_invoices(customer_paid, 'customer', is_paid=True)
                except:
                    pass
        
        # Factures fournisseurs
        if invoice_type in ['supplier', 'all']:
            # Impayées
            supplier_unpaid = dolibarr.get_supplier_invoices(status='unpaid', limit=100)
            add_invoices(supplier_unpaid, 'supplier', is_paid=False)
            
            # Payées
            if include_paid:
                try:
                    supplier_paid = dolibarr.get_supplier_invoices(status='paid', limit=100)
                    add_invoices(supplier_paid, 'supplier', is_paid=True)
                except:
                    pass
        
        # Trier: impayées d'abord, puis par date décroissante
        invoices.sort(key=lambda x: (x.get('is_paid', False), -int(x.get('date') or 0)))
        
        return jsonify({
            'success': True,
            'invoices': invoices,
            'count': len(invoices)
        })
        
    except Exception as e:
        import traceback
        print(f"Erreur thirdparty invoices: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


@app.route('/api/reconciliation/create-invoice-and-match', methods=['POST'])
def create_invoice_and_match():
    """
    Crée une facture depuis un PDF uploadé et la réconcilie avec une transaction
    """
    try:
        if 'pdf' not in request.files:
            return jsonify({'error': 'Aucun fichier PDF fourni'}), 400
        
        pdf_file = request.files['pdf']
        transaction_id = request.form.get('transaction_id')
        account_id = request.form.get('account_id')
        payment_mode_id = request.form.get('payment_mode_id', '2')
        
        if not transaction_id:
            return jsonify({'error': 'transaction_id manquant'}), 400
        
        transaction_id = int(transaction_id)
        
        # Récupérer la transaction
        transactions = db.get_all_transactions()
        tx = next((t for t in transactions if t['id'] == transaction_id), None)
        
        if not tx:
            return jsonify({'error': 'Transaction non trouvée'}), 404
        
        # Sauvegarder le PDF
        filename = secure_filename(pdf_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pdf_file.save(filepath)
        
        # Extraire les données via IA
        extracted_data = pdf_extractor.extract_invoice_data(filepath)
        
        if not extracted_data:
            return jsonify({'error': 'Impossible d\'extraire les données du PDF'}), 500
        
        supplier_name = extracted_data.get('supplier_name', '').strip()
        
        if not supplier_name:
            return jsonify({'error': 'Nom du fournisseur non trouvé dans le PDF'}), 400
        
        # Chercher ou créer le tiers
        existing_thirdparties = dolibarr.search_thirdparty(supplier_name)
        
        socid = None
        if existing_thirdparties and len(existing_thirdparties) > 0:
            tp = existing_thirdparties[0]
            raw_id = tp.get('id') or tp.get('rowid')
            try:
                socid = int(raw_id)
            except (ValueError, TypeError):
                socid = None
        
        if not socid:
            socid = dolibarr.create_thirdparty(
                name=supplier_name,
                supplier=True,
                address=extracted_data.get('address', ''),
                zip_code=extracted_data.get('zip_code', ''),
                town=extracted_data.get('town', ''),
                email=extracted_data.get('email', ''),
                phone=extracted_data.get('phone', '')
            )
            
            if not socid:
                return jsonify({'error': 'Impossible de créer le tiers'}), 500
        
        # Créer la facture
        timestamp_suffix = datetime.now().strftime('%Y%m%d%H%M%S')
        base_ref = extracted_data.get('invoice_ref', filename.replace('.pdf', ''))
        invoice_ref = f"{base_ref}-{timestamp_suffix}"
        
        amount_ht = float(extracted_data.get('amount_ht') or 0)
        amount_ttc = float(extracted_data.get('amount_ttc') or 0)
        tva_amount = float(extracted_data.get('tva_amount') or 0)
        
        # Si montants manquants, utiliser le montant de la transaction
        if amount_ttc == 0:
            amount_ttc = abs(tx['amount'])
            amount_ht = amount_ttc / 1.20
            tva_amount = amount_ttc - amount_ht
        
        # Date de la facture
        invoice_date_str = extracted_data.get('invoice_date', '')
        try:
            from dateutil.parser import parse
            parsed_date = parse(invoice_date_str, dayfirst=True)
            invoice_date = int(parsed_date.timestamp())
        except:
            invoice_date = int(datetime.now().timestamp())
        
        tva_rate = (tva_amount / amount_ht * 100) if amount_ht > 0 else 0
        
        invoice_id = dolibarr.create_supplier_invoice(
            socid=socid,
            ref_supplier=invoice_ref,
            date_invoice=invoice_date,
            total_ht=amount_ht,
            total_tva=tva_amount,
            total_ttc=amount_ttc,
            note=f"Facture importée depuis PDF: {supplier_name}",
            lines=[{
                'ref_product': 'SERVICE',
                'product_type': '1',
                'desc': extracted_data.get('description', 'Facture importée'),
                'pu_ht': str(amount_ht),
                'subprice': str(amount_ht),
                'qty': '1',
                'tva_tx': f"{tva_rate:.2f}",
                'total_ht': str(amount_ht),
                'total_tva': str(tva_amount),
                'total_ttc': str(amount_ttc)
            }]
        )
        
        if not invoice_id:
            return jsonify({'error': 'Impossible de créer la facture'}), 500
        
        # Attacher le PDF
        try:
            invoice_ref_dolibarr = f"(PROV{invoice_id})"
            dolibarr.attach_document(
                module_part='supplier_invoice',
                ref=invoice_ref_dolibarr,
                filepath=filepath,
                filename=f"facture_{invoice_ref}.pdf",
                overwriteifexists=1
            )
        except:
            pass
        
        # Créer le paiement si compte bancaire spécifié
        payment_id = None
        if account_id:
            payment_id = dolibarr.add_payment(
                invoice_id=invoice_id,
                datepaye=str(tx['date']),
                paymentid=int(payment_mode_id),
                accountid=int(account_id),
                closepaidinvoices='yes',
                comment=f"Réconciliation automatique - {tx['label']}",
                invoice_type='supplier'
            )
        
        # Réconcilier la transaction
        db.reconcile_transaction(
            transaction_id=transaction_id,
            invoice_id=invoice_id,
            invoice_type='supplier',
            invoice_ref=invoice_ref,
            thirdparty_name=supplier_name,
            payment_id=payment_id
        )
        
        # Nettoyer
        try:
            os.remove(filepath)
        except:
            pass
        
        return jsonify({
            'success': True,
            'message': 'Facture créée et transaction réconciliée',
            'invoice_id': invoice_id,
            'invoice_ref': invoice_ref,
            'thirdparty_name': supplier_name,
            'thirdparty_id': socid,
            'amount': amount_ttc,
            'payment_id': payment_id,
            'extracted_data': extracted_data
        })
        
    except Exception as e:
        import traceback
        print(f"Erreur create-invoice-and-match: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'Erreur: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)

