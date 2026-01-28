"""
Module de gestion de la base de données SQLite pour BankIA
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional
import json


class Database:
    """Gestion de la base de données SQLite pour l'historique"""
    
    def __init__(self, db_path: str = 'bankia.db'):
        """
        Initialise la connexion à la base de données
        
        Args:
            db_path: Chemin vers le fichier de base de données
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialise les tables de la base de données"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table pour l'historique des paiements
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id INTEGER NOT NULL,
                invoice_id INTEGER NOT NULL,
                invoice_ref TEXT,
                thirdparty_name TEXT,
                amount REAL NOT NULL,
                date_payment TEXT NOT NULL,
                account_id INTEGER,
                account_label TEXT,
                transaction_label TEXT,
                comment TEXT,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'created',
                cancelled_at TEXT,
                cancelled_by TEXT
            )
        ''')
        
        # Table pour l'historique des lignes bancaires
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bank_line_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                line_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                account_label TEXT,
                amount REAL NOT NULL,
                date_line TEXT NOT NULL,
                label TEXT,
                type TEXT,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'created',
                cancelled_at TEXT
            )
        ''')
        
        # Table pour l'historique des actions utilisateur
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                details TEXT,
                created_at TEXT NOT NULL,
                user_name TEXT DEFAULT 'system'
            )
        ''')
        
        # Table pour les transactions importées (éviter les doublons)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS imported_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE NOT NULL,
                date_transaction TEXT NOT NULL,
                label TEXT,
                amount REAL NOT NULL,
                raw_data TEXT,
                import_date TEXT NOT NULL,
                import_file TEXT,
                status TEXT DEFAULT 'pending',
                matched_invoice_id INTEGER,
                matched_invoice_type TEXT,
                matched_invoice_ref TEXT,
                matched_thirdparty TEXT,
                payment_id INTEGER,
                reconciled_at TEXT,
                reconciled_by TEXT
            )
        ''')
        
        # Index pour recherche rapide par hash
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_transactions_hash ON imported_transactions(hash)
        ''')
        
        # Index pour recherche par statut
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_transactions_status ON imported_transactions(status)
        ''')
        
        conn.commit()
        conn.close()
    
    def add_payment(self, payment_id: int, invoice_id: int, invoice_ref: str,
                   thirdparty_name: str, amount: float, date_payment: str,
                   account_id: int, account_label: str, transaction_label: str,
                   comment: str = '') -> int:
        """
        Ajoute un paiement à l'historique
        
        Returns:
            ID de l'enregistrement créé
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO payment_history 
            (payment_id, invoice_id, invoice_ref, thirdparty_name, amount, 
             date_payment, account_id, account_label, transaction_label, 
             comment, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'created')
        ''', (payment_id, invoice_id, invoice_ref, thirdparty_name, amount,
              date_payment, account_id, account_label, transaction_label,
              comment, created_at))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Enregistrer l'action
        self.log_action('payment_created', 'payment', payment_id, {
            'invoice_id': invoice_id,
            'amount': amount
        })
        
        return record_id
    
    def add_bank_line(self, line_id: int, account_id: int, account_label: str,
                     amount: float, date_line: str, label: str, 
                     type: str = 'VIR') -> int:
        """
        Ajoute une ligne bancaire à l'historique
        
        Returns:
            ID de l'enregistrement créé
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO bank_line_history 
            (line_id, account_id, account_label, amount, date_line, 
             label, type, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'created')
        ''', (line_id, account_id, account_label, amount, date_line,
              label, type, created_at))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Enregistrer l'action
        self.log_action('bank_line_created', 'bank_line', line_id, {
            'account_id': account_id,
            'amount': amount
        })
        
        return record_id
    
    def get_payment_history(self, limit: int = 100, offset: int = 0,
                           filters: Optional[Dict] = None) -> List[Dict]:
        """
        Récupère l'historique des paiements
        
        Args:
            limit: Nombre maximum de résultats
            offset: Décalage pour la pagination
            filters: Dictionnaire de filtres (date_from, date_to, invoice_id, etc.)
        
        Returns:
            Liste des paiements
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = 'SELECT * FROM payment_history WHERE 1=1'
        params = []
        
        if filters:
            if filters.get('date_from'):
                query += ' AND date_payment >= ?'
                params.append(filters['date_from'])
            if filters.get('date_to'):
                query += ' AND date_payment <= ?'
                params.append(filters['date_to'])
            if filters.get('invoice_id'):
                query += ' AND invoice_id = ?'
                params.append(filters['invoice_id'])
            if filters.get('status'):
                query += ' AND status = ?'
                params.append(filters['status'])
        
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        payments = []
        for row in rows:
            payments.append({
                'id': row['id'],
                'payment_id': row['payment_id'],
                'invoice_id': row['invoice_id'],
                'invoice_ref': row['invoice_ref'],
                'thirdparty_name': row['thirdparty_name'],
                'amount': row['amount'],
                'date_payment': row['date_payment'],
                'account_id': row['account_id'],
                'account_label': row['account_label'],
                'transaction_label': row['transaction_label'],
                'comment': row['comment'],
                'created_at': row['created_at'],
                'status': row['status'],
                'cancelled_at': row['cancelled_at']
            })
        
        conn.close()
        return payments
    
    def cancel_payment(self, record_id: int, reason: str = '') -> bool:
        """
        Marque un paiement comme annulé
        
        Args:
            record_id: ID de l'enregistrement dans l'historique
            reason: Raison de l'annulation
        
        Returns:
            True si succès, False sinon
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cancelled_at = datetime.now().isoformat()
        
        cursor.execute('''
            UPDATE payment_history 
            SET status = 'cancelled', cancelled_at = ?, comment = comment || ' | Annulé: ' || ?
            WHERE id = ?
        ''', (cancelled_at, reason, record_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if success:
            self.log_action('payment_cancelled', 'payment', record_id, {
                'reason': reason
            })
        
        return success
    
    def get_statistics(self) -> Dict:
        """
        Récupère des statistiques sur les paiements
        
        Returns:
            Dictionnaire avec les statistiques
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total de paiements créés
        cursor.execute('SELECT COUNT(*) FROM payment_history WHERE status = "created"')
        total_created = cursor.fetchone()[0]
        
        # Total de paiements annulés
        cursor.execute('SELECT COUNT(*) FROM payment_history WHERE status = "cancelled"')
        total_cancelled = cursor.fetchone()[0]
        
        # Montant total des paiements créés
        cursor.execute('SELECT SUM(amount) FROM payment_history WHERE status = "created"')
        total_amount = cursor.fetchone()[0] or 0
        
        # Paiements aujourd'hui
        today = datetime.now().date().isoformat()
        cursor.execute('SELECT COUNT(*) FROM payment_history WHERE DATE(created_at) = ?', (today,))
        today_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_created': total_created,
            'total_cancelled': total_cancelled,
            'total_amount': total_amount,
            'today_count': today_count
        }
    
    def log_action(self, action_type: str, entity_type: str, 
                  entity_id: Optional[int], details: Dict):
        """
        Enregistre une action utilisateur
        
        Args:
            action_type: Type d'action (payment_created, payment_cancelled, etc.)
            entity_type: Type d'entité (payment, bank_line, etc.)
            entity_id: ID de l'entité
            details: Détails supplémentaires en JSON
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        created_at = datetime.now().isoformat()
        details_json = json.dumps(details)
        
        cursor.execute('''
            INSERT INTO user_actions 
            (action_type, entity_type, entity_id, details, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (action_type, entity_type, entity_id, details_json, created_at))
        
        conn.commit()
        conn.close()
    
    # ========== Gestion des transactions importées ==========
    
    def _compute_transaction_hash(self, date: str, label: str, amount: float) -> str:
        """
        Calcule un hash unique pour une transaction
        Permet de détecter les doublons
        """
        import hashlib
        # Normaliser les données
        data = f"{date}|{label.strip().upper()}|{amount:.2f}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()[:32]
    
    def import_transactions(self, transactions: List[Dict], filename: str = '') -> Dict:
        """
        Importe des transactions en vérifiant les doublons
        
        Args:
            transactions: Liste des transactions à importer
            filename: Nom du fichier source
        
        Returns:
            Dict avec: imported (list), duplicates (list), new_count, duplicate_count
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        import_date = datetime.now().isoformat()
        imported = []
        duplicates = []
        
        for tx in transactions:
            tx_hash = self._compute_transaction_hash(
                tx.get('date', ''),
                tx.get('label', ''),
                tx.get('amount', 0)
            )
            
            # Vérifier si existe déjà
            cursor.execute('SELECT id, status FROM imported_transactions WHERE hash = ?', (tx_hash,))
            existing = cursor.fetchone()
            
            if existing:
                # Doublon trouvé
                duplicates.append({
                    'transaction': tx,
                    'existing_id': existing[0],
                    'existing_status': existing[1]
                })
            else:
                # Nouvelle transaction
                raw_data = json.dumps(tx.get('raw_data', {}))
                
                cursor.execute('''
                    INSERT INTO imported_transactions 
                    (hash, date_transaction, label, amount, raw_data, import_date, import_file, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                ''', (tx_hash, tx.get('date', ''), tx.get('label', ''), 
                      tx.get('amount', 0), raw_data, import_date, filename))
                
                tx_id = cursor.lastrowid
                imported.append({
                    'id': tx_id,
                    'hash': tx_hash,
                    'transaction': tx
                })
        
        conn.commit()
        conn.close()
        
        return {
            'imported': imported,
            'duplicates': duplicates,
            'new_count': len(imported),
            'duplicate_count': len(duplicates)
        }
    
    def get_pending_transactions(self, limit: int = 2000) -> List[Dict]:
        """
        Récupère les transactions en attente de réconciliation
        
        Returns:
            Liste des transactions pending
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM imported_transactions 
            WHERE status = 'pending'
            ORDER BY date_transaction ASC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        transactions = []
        
        for row in rows:
            raw_data = {}
            if row['raw_data']:
                try:
                    raw_data = json.loads(row['raw_data'])
                except:
                    pass
            
            transactions.append({
                'id': row['id'],
                'hash': row['hash'],
                'date': row['date_transaction'],
                'label': row['label'],
                'amount': row['amount'],
                'raw_data': raw_data,
                'import_date': row['import_date'],
                'import_file': row['import_file'],
                'status': row['status']
            })
        
        conn.close()
        return transactions
    
    def get_all_transactions(self, status: str = None, limit: int = 2000) -> List[Dict]:
        """
        Récupère toutes les transactions avec filtre optionnel par statut
        
        Args:
            status: Filtre par statut ('pending', 'reconciled', 'ignored')
            limit: Nombre max de résultats
        
        Returns:
            Liste des transactions
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT * FROM imported_transactions 
                WHERE status = ?
                ORDER BY date_transaction ASC
                LIMIT ?
            ''', (status, limit))
        else:
            cursor.execute('''
                SELECT * FROM imported_transactions 
                ORDER BY date_transaction ASC
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        transactions = []
        
        for row in rows:
            raw_data = {}
            if row['raw_data']:
                try:
                    raw_data = json.loads(row['raw_data'])
                except:
                    pass
            
            transactions.append({
                'id': row['id'],
                'hash': row['hash'],
                'date': row['date_transaction'],
                'label': row['label'],
                'amount': row['amount'],
                'raw_data': raw_data,
                'import_date': row['import_date'],
                'import_file': row['import_file'],
                'status': row['status'],
                'matched_invoice_id': row['matched_invoice_id'],
                'matched_invoice_type': row['matched_invoice_type'],
                'matched_invoice_ref': row['matched_invoice_ref'],
                'matched_thirdparty': row['matched_thirdparty'],
                'payment_id': row['payment_id'],
                'reconciled_at': row['reconciled_at']
            })
        
        conn.close()
        return transactions
    
    def get_transaction_by_id(self, transaction_id: int) -> Optional[Dict]:
        """
        Récupère une transaction par son ID
        
        Args:
            transaction_id: ID de la transaction
        
        Returns:
            Transaction ou None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM imported_transactions WHERE id = ?', (transaction_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        raw_data = {}
        if row['raw_data']:
            try:
                raw_data = json.loads(row['raw_data'])
            except:
                pass
        
        return {
            'id': row['id'],
            'hash': row['hash'],
            'date': row['date_transaction'],
            'label': row['label'],
            'amount': row['amount'],
            'raw_data': raw_data,
            'import_date': row['import_date'],
            'import_file': row['import_file'],
            'status': row['status'],
            'matched_invoice_id': row['matched_invoice_id'],
            'matched_invoice_type': row['matched_invoice_type'],
            'matched_invoice_ref': row['matched_invoice_ref'],
            'matched_thirdparty': row['matched_thirdparty'],
            'payment_id': row['payment_id'],
            'reconciled_at': row['reconciled_at']
        }
    
    def reconcile_transaction(self, transaction_id: int, invoice_id: int,
                             invoice_type: str, invoice_ref: str,
                             thirdparty_name: str, payment_id: int = None) -> bool:
        """
        Marque une transaction comme réconciliée
        
        Args:
            transaction_id: ID de la transaction importée
            invoice_id: ID de la facture matchée
            invoice_type: Type de facture ('customer' ou 'supplier')
            invoice_ref: Référence de la facture
            thirdparty_name: Nom du tiers
            payment_id: ID du paiement créé (optionnel)
        
        Returns:
            True si succès
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        reconciled_at = datetime.now().isoformat()
        
        cursor.execute('''
            UPDATE imported_transactions 
            SET status = 'reconciled',
                matched_invoice_id = ?,
                matched_invoice_type = ?,
                matched_invoice_ref = ?,
                matched_thirdparty = ?,
                payment_id = ?,
                reconciled_at = ?
            WHERE id = ?
        ''', (invoice_id, invoice_type, invoice_ref, thirdparty_name,
              payment_id, reconciled_at, transaction_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if success:
            self.log_action('transaction_reconciled', 'transaction', transaction_id, {
                'invoice_id': invoice_id,
                'invoice_type': invoice_type,
                'payment_id': payment_id
            })
        
        return success
    
    def ignore_transaction(self, transaction_id: int, reason: str = '') -> bool:
        """
        Marque une transaction comme ignorée
        
        Args:
            transaction_id: ID de la transaction
            reason: Raison de l'ignorance
        
        Returns:
            True si succès
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE imported_transactions 
            SET status = 'ignored'
            WHERE id = ?
        ''', (transaction_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if success:
            self.log_action('transaction_ignored', 'transaction', transaction_id, {
                'reason': reason
            })
        
        return success
    
    def reset_transaction(self, transaction_id: int) -> bool:
        """
        Remet une transaction en statut pending
        
        Args:
            transaction_id: ID de la transaction
        
        Returns:
            True si succès
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE imported_transactions 
            SET status = 'pending',
                matched_invoice_id = NULL,
                matched_invoice_type = NULL,
                matched_invoice_ref = NULL,
                matched_thirdparty = NULL,
                payment_id = NULL,
                reconciled_at = NULL
            WHERE id = ?
        ''', (transaction_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def get_transaction_stats(self) -> Dict:
        """
        Récupère les statistiques sur les transactions importées
        
        Returns:
            Dict avec les stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total par statut
        cursor.execute('''
            SELECT status, COUNT(*), SUM(amount)
            FROM imported_transactions
            GROUP BY status
        ''')
        
        stats_by_status = {}
        for row in cursor.fetchall():
            stats_by_status[row[0]] = {
                'count': row[1],
                'total': row[2] or 0
            }
        
        # Total général
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM imported_transactions')
        total_row = cursor.fetchone()
        
        # Crédits et débits
        cursor.execute('''
            SELECT 
                SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as credits,
                SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) as debits,
                COUNT(CASE WHEN amount > 0 THEN 1 END) as credit_count,
                COUNT(CASE WHEN amount < 0 THEN 1 END) as debit_count
            FROM imported_transactions
            WHERE status = 'pending'
        ''')
        pending_row = cursor.fetchone()
        
        conn.close()
        
        return {
            'total_count': total_row[0] or 0,
            'total_amount': total_row[1] or 0,
            'by_status': stats_by_status,
            'pending_credits': pending_row[0] or 0,
            'pending_debits': pending_row[1] or 0,
            'pending_credit_count': pending_row[2] or 0,
            'pending_debit_count': pending_row[3] or 0
        }

