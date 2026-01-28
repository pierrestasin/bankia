"""
Client pour interagir avec l'API Dolibarr
"""
import requests
from config import DOLIBARR_URL, DOLIBARR_API_KEY, DOLIBARR_API_LOGIN
from typing import List, Dict, Optional
import json


class DolibarrClient:
    """Client pour interagir avec l'API REST Dolibarr"""
    
    def __init__(self):
        self.base_url = DOLIBARR_URL
        self.api_key = DOLIBARR_API_KEY
        self.login = DOLIBARR_API_LOGIN
        self.session = requests.Session()
        self.session.headers.update({
            'DOLAPIKEY': self.api_key,
            'Content-Type': 'application/json'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Effectue une requête HTTP vers l'API Dolibarr"""
        # Nettoyer l'URL de base
        base_url = self.base_url.rstrip('/')
        
        # Si l'URL ne se termine pas par /api/index.php, l'ajouter
        if not base_url.endswith('/api/index.php'):
            if base_url.endswith('/api'):
                base_url = f"{base_url}/index.php"
            elif not base_url.endswith('/index.php'):
                # Si l'URL contient déjà /dolibarr/, on la garde telle quelle
                # Sinon, on ajoute /api/index.php
                if '/dolibarr/' in base_url:
                    if not base_url.endswith('/api/index.php'):
                        base_url = f"{base_url.rstrip('/')}/api/index.php"
                else:
                    # Cas où l'URL est juste le domaine, on ajoute /api/index.php
                    base_url = f"{base_url}/api/index.php"
        
        # Construire l'URL complète
        url = f"{base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Gérer les erreurs de manière plus détaillée
            if response.status_code == 404:
                print(f"Erreur 404: Endpoint non trouvé - {url}")
                print(f"Vérifiez que l'endpoint '{endpoint}' existe dans votre version de Dolibarr")
                return None
            elif response.status_code == 401:
                print(f"Erreur 401: Authentification échouée")
                print(f"Vérifiez votre clé API Dolibarr dans config.py")
                return None
            
            # Dolibarr retourne parfois 501 mais crée quand même la ressource
            # On ignore donc les erreurs 501 pour POST (création)
            if response.status_code >= 400 and response.status_code != 501:
                response.raise_for_status()
            
            if response.content:
                try:
                    result = response.json()
                    # Pour les créations (POST), le résultat est souvent juste l'ID
                    if isinstance(result, (int, str)):
                        return result
                    return result
                except ValueError as e:
                    # Si ce n'est pas du JSON, c'est peut-être juste un ID en texte
                    text = response.text.strip()
                    # Essayer de parser comme un entier (ID)
                    try:
                        return int(text)
                    except ValueError:
                        # Si ce n'est pas un nombre, c'est une erreur
                        if text.startswith('<!'):
                            print(f"❌ Page HTML d'erreur reçue de Dolibarr")
                            print(f"URL: {url}")
                            print(f"Status: {response.status_code}")
                        elif text:
                            # C'est un message d'erreur texte, pas un ID valide
                            print(f"❌ Réponse texte non-numérique de Dolibarr: {text[:200]}")
                        return None
            return None
        except requests.exceptions.RequestException as e:
            print(f"Erreur API Dolibarr: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status code: {e.response.status_code}")
                print(f"Response: {e.response.text[:500]}")
            return None
    
    def get_invoices(self, status: str = 'unpaid', limit: int = 100) -> List[Dict]:
        """
        Récupère les factures impayées depuis Dolibarr
        
        Args:
            status: Statut des factures ('unpaid', 'paid', 'draft', 'cancelled')
            limit: Nombre maximum de factures à récupérer
        
        Returns:
            Liste des factures
        """
        params = {
            'status': status,
            'limit': limit,
            'sortfield': 't.rowid',  # Utiliser rowid au lieu de date pour compatibilité
            'sortorder': 'DESC'
        }
        result = self._make_request('GET', 'invoices', params=params)
        return result if isinstance(result, list) else []
    
    def get_invoice(self, invoice_id: int) -> Optional[Dict]:
        """Récupère une facture spécifique par son ID"""
        return self._make_request('GET', f'invoices/{invoice_id}')
    
    def get_invoice_by_ref(self, ref: str) -> Optional[Dict]:
        """
        Recherche une facture par sa référence (client ou fournisseur)
        
        Args:
            ref: Référence de la facture (ex: IN2412-0222)
        
        Returns:
            Facture trouvée ou None
        """
        if not ref:
            return None
        
        # Normaliser la référence (enlever espaces, mettre en majuscule)
        ref_clean = ref.strip().upper()
        
        # Chercher dans les factures clients
        try:
            result = self._make_request('GET', 'invoices', params={
                'sqlfilters': f"(t.ref:like:'{ref_clean}%')",
                'limit': 10
            })
            if result and isinstance(result, list):
                for inv in result:
                    inv_ref = (inv.get('ref') or '').upper()
                    if inv_ref == ref_clean or ref_clean in inv_ref:
                        inv['_invoice_type'] = 'customer'
                        return inv
        except:
            pass
        
        # Chercher sans sqlfilters (fallback)
        try:
            result = self._make_request('GET', 'invoices', params={'limit': 500})
            if result and isinstance(result, list):
                for inv in result:
                    inv_ref = (inv.get('ref') or '').upper()
                    if inv_ref == ref_clean or ref_clean in inv_ref or inv_ref.replace('-', '') == ref_clean.replace('-', ''):
                        inv['_invoice_type'] = 'customer'
                        return inv
        except:
            pass
        
        # Chercher dans les factures fournisseurs
        endpoints = ['supplierinvoices', 'supplier_invoices']
        for endpoint in endpoints:
            try:
                result = self._make_request('GET', endpoint, params={'limit': 500})
                if result and isinstance(result, list):
                    for inv in result:
                        inv_ref = (inv.get('ref') or inv.get('ref_supplier') or '').upper()
                        if inv_ref == ref_clean or ref_clean in inv_ref or inv_ref.replace('-', '') == ref_clean.replace('-', ''):
                            inv['_invoice_type'] = 'supplier'
                            return inv
                    break
            except:
                continue
        
        return None
    
    def get_supplier_invoices(self, status: str = 'unpaid', limit: int = 100) -> List[Dict]:
        """
        Récupère les factures fournisseurs depuis Dolibarr
        
        Args:
            status: Statut des factures ('unpaid', 'paid', 'draft', 'cancelled')
            limit: Nombre maximum de factures à récupérer
        
        Returns:
            Liste des factures fournisseurs
        """
        # Paramètres simplifiés pour éviter les erreurs SQL
        params = {
            'limit': limit
        }
        
        result = None
        
        # Essayer différents endpoints
        endpoints = ['supplierinvoices', 'supplier_invoices', 'fournisseur/factures']
        
        for endpoint in endpoints:
            try:
                result = self._make_request('GET', endpoint, params=params)
                if result and isinstance(result, list):
                    break
            except:
                continue
        
        if not result:
            return []
        
        # S'assurer que c'est une liste
        if not isinstance(result, list):
            return []
        
        # Filtrer par statut si demandé
        if status:
            if status == 'unpaid':
                # Statut 1 = validée/impayée, paye = 0
                filtered = [inv for inv in result 
                           if str(inv.get('status')) == '1' or str(inv.get('paye')) == '0']
                return filtered
            elif status == 'paid':
                # Statut 2 = payée ou paye = 1
                filtered = [inv for inv in result 
                           if str(inv.get('status')) == '2' or str(inv.get('paye')) == '1']
                return filtered
        
        return result
    
    def get_supplier_invoice(self, invoice_id: int) -> Optional[Dict]:
        """Récupère une facture fournisseur spécifique par son ID"""
        result = self._make_request('GET', f'supplier_invoices/{invoice_id}')
        if not result:
            result = self._make_request('GET', f'supplierinvoices/{invoice_id}')
        return result
    
    def get_thirdparty(self, thirdparty_id: int) -> Optional[Dict]:
        """Récupère les informations d'un tiers par son ID"""
        # Essayer différents endpoints selon la version de Dolibarr (societes en premier)
        endpoints = [f'societes/{thirdparty_id}', f'thirdparties/{thirdparty_id}']
        
        for endpoint in endpoints:
            try:
                result = self._make_request('GET', endpoint)
                if result and isinstance(result, dict):
                    return result
            except:
                continue
        
        return None
    
    def search_thirdparty(self, name: str) -> List[Dict]:
        """Recherche un tiers par nom avec correspondance précise"""
        endpoints = ['thirdparties', 'societes']
        
        for endpoint in endpoints:
            try:
                result = self._make_request('GET', endpoint, params={'limit': 500})
                if result and isinstance(result, list):
                    name_lower = name.lower().strip()
                    name_parts = [p for p in name_lower.split() if len(p) >= 2]
                    
                    exact_matches = []
                    all_words_matches = []
                    
                    for tp in result:
                        tp_name = (tp.get('name', '') or tp.get('nom', '')).lower().strip()
                        
                        # Match exact (priorité maximale)
                        if tp_name == name_lower:
                            exact_matches.append(tp)
                            continue
                        
                        # Match si le nom contient TOUS les mots recherchés
                        if name_parts and all(part in tp_name for part in name_parts):
                            all_words_matches.append(tp)
                    
                    # Retourner les matchs exacts en priorité
                    if exact_matches:
                        print(f"   [SEARCH] Match exact trouvé pour '{name}'")
                        return exact_matches
                    
                    # Sinon retourner les matchs avec tous les mots
                    if all_words_matches:
                        print(f"   [SEARCH] {len(all_words_matches)} tiers contenant tous les mots de '{name}'")
                        return all_words_matches
                    
                    # Pas de correspondance suffisante
                    print(f"   [SEARCH] Aucun tiers correspondant à '{name}' dans Dolibarr")
                    return []
            except Exception as e:
                print(f"   [SEARCH] Erreur endpoint {endpoint}: {e}")
                continue
        
        return []
    
    def get_thirdparty_invoices(self, thirdparty_id: int, invoice_type: str = 'customer', 
                                include_paid: bool = True) -> List[Dict]:
        """
        Récupère les factures d'un tiers spécifique
        
        Args:
            thirdparty_id: ID du tiers
            invoice_type: 'customer' ou 'supplier'
            include_paid: Inclure les factures payées
        
        Returns:
            Liste des factures du tiers
        """
        all_invoices = []
        
        if invoice_type == 'supplier':
            # Factures fournisseurs
            endpoints = ['supplierinvoices', 'supplier_invoices', 'fournisseur/factures']
            for endpoint in endpoints:
                try:
                    # Factures impayées
                    result = self._make_request('GET', endpoint, params={
                        'thirdparty_ids': thirdparty_id,
                        'limit': 100
                    })
                    if result and isinstance(result, list):
                        # Filtrer par tiers
                        for inv in result:
                            socid = inv.get('socid') or inv.get('fk_soc')
                            if str(socid) == str(thirdparty_id):
                                # Déterminer si payée
                                remain = float(inv.get('remaintopay') or inv.get('total_ht') or 0)
                                inv['_already_paid'] = remain == 0
                                all_invoices.append(inv)
                        break
                except:
                    continue
        else:
            # Factures clients
            try:
                # Récupérer toutes les factures et filtrer par tiers
                statuses = ['unpaid']
                if include_paid:
                    statuses.append('paid')
                
                for status in statuses:
                    result = self._make_request('GET', 'invoices', params={
                        'thirdparty_ids': thirdparty_id,
                        'status': status,
                        'limit': 100
                    })
                    if result and isinstance(result, list):
                        for inv in result:
                            socid = inv.get('socid') or inv.get('fk_soc')
                            if str(socid) == str(thirdparty_id):
                                inv['_already_paid'] = (status == 'paid')
                                all_invoices.append(inv)
            except Exception as e:
                print(f"Erreur récupération factures tiers: {e}")
        
        return all_invoices
    
    def create_thirdparty(self, name: str, supplier: bool = True, customer: bool = False,
                         address: str = '', zip_code: str = '', town: str = '',
                         country_code: str = 'FR', phone: str = '', email: str = '',
                         code_fournisseur: str = '') -> Optional[int]:
        """
        Crée un tiers dans Dolibarr
        
        Returns:
            ID du tiers créé ou None
        """
        data = {
            'name': name,
            'name_alias': '',
            'address': address,
            'zip': zip_code,
            'town': town,
            'country_code': country_code,
            'phone': phone,
            'email': email,
            'client': '0' if not customer else '1',
            'fournisseur': '1' if supplier else '0',
            'code_fournisseur': code_fournisseur or 'auto'
        }
        
        print(f"DEBUG: Création tiers avec données: {data}")
        
        # Essayer différents endpoints selon la version de Dolibarr (societes en premier)
        endpoints = ['societes', 'thirdparties']
        
        for endpoint in endpoints:
            try:
                result = self._make_request('POST', endpoint, json=data)
                if result:
                    # Vérifier que le résultat est un ID valide (entier)
                    try:
                        thirdparty_id = int(result)
                        print(f"DEBUG: Tiers créé avec succès via {endpoint}, ID: {thirdparty_id}")
                        return thirdparty_id
                    except (ValueError, TypeError):
                        print(f"DEBUG: Résultat non valide (pas un ID): {result}")
                        continue
            except:
                continue
        
        print(f"DEBUG: Échec création tiers")
        return None
    
    def create_supplier_invoice(self, socid: int, ref_supplier: str, date_invoice: str,
                                total_ht: float, total_tva: float = 0, total_ttc: float = None,
                                lines: List[Dict] = None, note: str = '') -> Optional[int]:
        """
        Crée une facture fournisseur dans Dolibarr
        
        Args:
            socid: ID du tiers fournisseur
            ref_supplier: Référence de la facture fournisseur
            date_invoice: Date de la facture au format YYYY-MM-DD ou timestamp
            total_ht: Montant HT
            total_tva: Montant TVA
            total_ttc: Montant TTC (calculé automatiquement si non fourni)
            lines: Lignes de la facture (optionnel)
            note: Note/commentaire
        
        Returns:
            ID de la facture créée ou None
        """
        # Convertir en timestamp string comme dans l'exemple
        if isinstance(date_invoice, int):
            date_str = str(date_invoice)  # Garder le timestamp tel quel
        elif isinstance(date_invoice, str):
            # Si c'est une date YYYY-MM-DD, convertir en timestamp
            if '-' in date_invoice:
                from datetime import datetime
                dt = datetime.strptime(date_invoice, '%Y-%m-%d')
                date_str = str(int(dt.timestamp()))
            else:
                date_str = date_invoice
        else:
            date_str = str(int(datetime.now().timestamp()))
        
        if total_ttc is None:
            total_ttc = total_ht + total_tva
        
        # Lignes par défaut si non fournies (format exact selon l'exemple)
        if not lines:
            tva_rate = (total_tva / total_ht * 100) if total_ht > 0 else 0
            lines = [{
                'ref_product': 'SERVICE',  # Référence produit par défaut
                'product_type': '1',  # 1 = Service
                'desc': note or 'Ligne facture importée depuis PDF',
                'pu_ht': str(total_ht),
                'subprice': str(total_ht),
                'qty': '1',
                'tva_tx': f"{tva_rate:.2f}",
                'total_ht': str(total_ht),
                'total_tva': str(total_tva),
                'total_ttc': str(total_ttc)
            }]
        
        # Format selon l'API Dolibarr
        data = {
            'ref': 'Auto',
            'ref_supplier': ref_supplier,
            'socid': str(socid),
            'date': date_str,  # Date de la facture (timestamp)
            'total_ht': str(total_ht),
            'total_tva': str(total_tva),
            'total_ttc': str(total_ttc),
            'note': note or 'Facture importée depuis PDF',
            'lines': lines
        }
        
        print(f"DEBUG: Création facture fournisseur avec données: {data}")
        
        # Utiliser l'endpoint correct selon la doc
        result = self._make_request('POST', 'supplierinvoices', json=data)
        
        if result:
            print(f"DEBUG: Facture créée avec succès, résultat: {result}")
        else:
            print(f"DEBUG: Échec création facture")
        
        return result if result else None
    
    def get_bank_accounts(self) -> List[Dict]:
        """Récupère la liste des comptes bancaires"""
        # Utiliser les mêmes paramètres que dans la documentation
        params = {
            'sortfield': 't.rowid',
            'sortorder': 'ASC',
            'limit': 100
        }
        result = self._make_request('GET', 'bankaccounts', params=params)
        
        if result:
            # Si le résultat est une liste, la retourner directement
            if isinstance(result, list):
                return result
            # Si c'est un dict avec une clé 'accounts' ou similaire
            if isinstance(result, dict):
                if 'accounts' in result:
                    return result['accounts']
                if 'data' in result:
                    return result['data']
                # Si c'est directement le résultat
                return [result]
        
        return []
    
    def get_bank_lines(self, account_id: int, sqlfilters: str = '') -> List[Dict]:
        """
        Récupère les lignes bancaires d'un compte
        
        Args:
            account_id: ID du compte bancaire
            sqlfilters: Filtres SQL optionnels
        
        Returns:
            Liste des lignes bancaires
        """
        params = {}
        if sqlfilters:
            params['sqlfilters'] = sqlfilters
        result = self._make_request('GET', f'bankaccounts/{account_id}/lines', params=params)
        return result if result else []
    
    def add_payment(self, invoice_id: int, datepaye: str, paymentid: int, 
                    accountid: int, closepaidinvoices: str = 'yes',
                    num_payment: str = '', comment: str = '', invoice_type: str = 'customer') -> Optional[int]:
        """
        Ajoute un paiement à une facture (client ou fournisseur)
        
        Args:
            invoice_id: ID de la facture
            datepaye: Date du paiement (timestamp)
            paymentid: ID du mode de paiement
            accountid: ID du compte bancaire
            closepaidinvoices: 'yes' ou 'no' pour fermer les factures payées
            num_payment: Numéro de paiement optionnel
            comment: Commentaire optionnel
            invoice_type: 'customer' ou 'supplier'
        
        Returns:
            ID du paiement créé ou None en cas d'erreur
        """
        data = {
            'datepaye': datepaye,
            'paymentid': paymentid,
            'closepaidinvoices': closepaidinvoices,
            'accountid': accountid,
            'num_payment': num_payment,
            'comment': comment
        }
        
        # Endpoint différent selon le type de facture
        if invoice_type == 'supplier':
            endpoint = f'supplier_invoices/{invoice_id}/payments'
            # Essayer aussi l'ancien endpoint si le premier échoue
            result = self._make_request('POST', endpoint, json=data)
            if not result:
                endpoint = f'supplierinvoices/{invoice_id}/payments'
                result = self._make_request('POST', endpoint, json=data)
        else:
            endpoint = f'invoices/{invoice_id}/payments'
            result = self._make_request('POST', endpoint, json=data)
        
        return result if result else None
    
    def add_bank_line(self, account_id: int, date: str, type: str, label: str, 
                     amount: float, category: int = 0, cheque_number: str = '',
                     accountancycode: str = '', datev: str = None, 
                     num_releve: str = '') -> Optional[int]:
        """
        Ajoute une ligne bancaire
        
        Args:
            account_id: ID du compte bancaire
            date: Date de l'opération (timestamp)
            type: Type de paiement (VIR, PRE, CHQ, etc.)
            label: Libellé de l'opération
            amount: Montant
            category: Catégorie optionnelle
            cheque_number: Numéro de chèque optionnel
            accountancycode: Code comptable optionnel
            datev: Date de valeur optionnelle
            num_releve: Numéro de relevé optionnel
        
        Returns:
            ID de la ligne créée ou None en cas d'erreur
        """
        data = {
            'date': date,
            'type': type,
            'label': label,
            'amount': amount,
            'category': category,
            'cheque_number': cheque_number,
            'accountancycode': accountancycode,
            'datev': datev or date,
            'num_releve': num_releve
        }
        result = self._make_request('POST', f'bankaccounts/{account_id}/lines', json=data)
        return result if result else None
    
    def attach_document(self, module_part: str, ref: str, filepath: str, 
                        filename: str = None, overwriteifexists: int = 0) -> Optional[str]:
        """
        Attache un document (fichier) à un objet Dolibarr
        
        Args:
            module_part: Type de l'objet ('supplier_invoice', 'invoice', 'thirdparty', etc.)
            ref: Référence de l'objet (ex: '(PROV1)' pour une facture fournisseur)
            filepath: Chemin local du fichier à uploader
            filename: Nom du fichier (optionnel, utilise le nom du fichier si non fourni)
            overwriteifexists: 1 pour écraser si existe, 0 sinon
        
        Returns:
            Chemin du document créé dans Dolibarr ou None
        """
        import base64
        import os
        
        if not os.path.exists(filepath):
            print(f"Erreur: Fichier non trouvé: {filepath}")
            return None
        
        # Lire le fichier et encoder en base64
        with open(filepath, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode('utf-8')
        
        # Nom du fichier
        if not filename:
            filename = os.path.basename(filepath)
        
        # Données pour l'API
        data = {
            'filename': filename,
            'modulepart': module_part,
            'ref': ref,
            'subdir': '',
            'filecontent': file_content,
            'fileencoding': 'base64',
            'overwriteifexists': overwriteifexists
        }
        
        print(f"DEBUG: Attachement document - module={module_part}, ref={ref}, file={filename}")
        
        result = self._make_request('POST', 'documents/upload', json=data)
        
        if result:
            print(f"DEBUG: Document attaché avec succès: {result}")
            return result
        else:
            print(f"DEBUG: Échec attachement document")
            return None
    
    def get_supplier_invoice_by_ref(self, ref_supplier: str) -> Optional[Dict]:
        """
        Récupère une facture fournisseur par sa référence fournisseur
        
        Args:
            ref_supplier: Référence fournisseur de la facture
        
        Returns:
            Dictionnaire avec les données de la facture ou None
        """
        # Rechercher par ref_supplier
        params = {'sqlfilters': f"t.ref_supplier:=:'{ref_supplier}'"}
        result = self._make_request('GET', 'supplierinvoices', params=params)
        
        if result and isinstance(result, list) and len(result) > 0:
            return result[0]
        return None

