"""
Parser pour les fichiers CSV de relevés bancaires
"""
import csv
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import re


class BankStatementParser:
    """Parse les fichiers CSV de relevés bancaires"""
    
    # Formats communs de relevés bancaires (à adapter selon les banques)
    COMMON_FORMATS = [
        {
            'name': 'Standard',
            'columns': ['date', 'label', 'amount', 'balance'],
            'date_format': '%Y-%m-%d',
            'amount_col': 'amount'
        },
        {
            'name': 'French Bank',
            'columns': ['date', 'libelle', 'debit', 'credit', 'solde'],
            'date_format': '%d/%m/%Y',
            'amount_col': None  # Nécessite calcul debit - credit
        }
    ]
    
    def parse(self, file_path: str) -> List[Dict]:
        """
        Parse un fichier CSV ou Excel de relevé bancaire
        
        Args:
            file_path: Chemin vers le fichier CSV ou Excel
        
        Returns:
            Liste des transactions avec les champs normalisés
        """
        df = None
        
        # Vérifier si c'est un fichier Excel
        if file_path.lower().endswith(('.xlsx', '.xls')):
            try:
                df = pd.read_excel(file_path, engine='openpyxl')
                print(f"[PARSER] Fichier Excel lu avec succes: {len(df)} lignes, {len(df.columns)} colonnes")
            except Exception as e:
                print(f"[ERR] Erreur lecture Excel: {e}")
                raise ValueError(f"Impossible de lire le fichier Excel: {e}")
        else:
            # Essayer différents séparateurs et encodages pour CSV
            separators = [';', ',', '\t', '|']
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            
            for sep in separators:
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, sep=sep, engine='python')
                        if len(df.columns) > 1:  # Si on a plusieurs colonnes, c'est bon
                            break
                    except:
                        continue
                if df is not None and len(df.columns) > 1:
                    break
        
        if df is None or len(df.columns) <= 1:
            raise ValueError("Impossible de parser le fichier. Vérifiez le format et l'encodage.")
        
        # Normaliser les noms de colonnes (gérer les accents et espaces)
        df.columns = df.columns.str.strip()
        
        # Créer un mapping pour normaliser les noms de colonnes
        column_mapping = {}
        for col in df.columns:
            normalized = col.lower().strip()
            # Gérer les variantes avec/sans accents
            if 'débit' in normalized or ('debit' in normalized and 'crédit' not in normalized and 'credit' not in normalized):
                column_mapping[col] = 'debit'
            elif 'crédit' in normalized or ('credit' in normalized and 'débit' not in normalized and 'debit' not in normalized):
                column_mapping[col] = 'credit'
            elif 'date' in normalized:
                column_mapping[col] = 'date'
            elif 'libellé' in normalized or 'libelle' in normalized or ('label' in normalized and 'opération' not in normalized):
                column_mapping[col] = 'label'
            elif 'solde' in normalized or 'balance' in normalized:
                column_mapping[col] = 'solde'
        
        # Renommer les colonnes si nécessaire
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        # Maintenant normaliser en minuscules
        df.columns = df.columns.str.lower()
        
        # Détecter le format automatiquement
        transactions = self._detect_and_parse(df)
        
        return transactions
    
    def _detect_and_parse(self, df: pd.DataFrame) -> List[Dict]:
        """Détecte le format et parse les données"""
        transactions = []
        
        # Chercher les colonnes de date (avec/sans accents)
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        if not date_cols:
            raise ValueError("Aucune colonne de date trouvée dans le CSV")
        
        date_col = date_cols[0]
        
        # Chercher les colonnes de montant (avec/sans accents)
        amount_cols = []
        for col in df.columns:
            col_lower = col.lower()
            if any(x in col_lower for x in ['montant', 'amount', 'débit', 'debit', 'crédit', 'credit']):
                amount_cols.append(col)
        
        # Chercher les colonnes de libellé (avec/sans accents)
        label_cols = []
        for col in df.columns:
            col_lower = col.lower()
            if any(x in col_lower for x in ['libelle', 'libellé', 'label', 'description', 'opération', 'operation']):
                label_cols.append(col)
        
        label_col = label_cols[0] if label_cols else None
        
        # Traiter chaque ligne
        for idx, row in df.iterrows():
            try:
                transaction = self._parse_row(row, date_col, amount_cols, label_col)
                if transaction and transaction.get('amount') is not None:
                    transactions.append(transaction)
            except Exception as e:
                print(f"Erreur lors du parsing de la ligne {idx}: {e}")
                continue
        
        return transactions
    
    def _parse_row(self, row: pd.Series, date_col: str, amount_cols: List[str], 
                   label_col: Optional[str]) -> Optional[Dict]:
        """Parse une ligne du CSV"""
        # Parser la date
        date_str = str(row[date_col]).strip()
        date = self._parse_date(date_str)
        if not date:
            return None
        
        # Parser le montant
        amount = self._parse_amount(row, amount_cols)
        if amount is None:
            return None
        
        # Parser le libellé
        label = str(row[label_col]).strip() if label_col else ''
        
        # Chercher une référence de facture dans le libellé
        invoice_ref = self._extract_invoice_ref(label)
        
        # Créer le dictionnaire de transaction en convertissant NaN en None
        raw_data = {}
        for key, value in row.to_dict().items():
            if pd.isna(value):
                raw_data[key] = None
            else:
                raw_data[key] = str(value) if isinstance(value, (int, float)) else value
        
        return {
            'date': date,
            'date_str': date_str,
            'amount': float(amount),  # S'assurer que c'est un float
            'label': label,
            'invoice_ref': invoice_ref,
            'raw_data': raw_data
        }
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse une date en timestamp Unix"""
        # Formats de date courants
        date_formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%Y/%m/%d',
            '%d.%m.%Y',
            '%Y.%m.%d'
        ]
        
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return str(int(dt.timestamp()))
            except:
                continue
        
        return None
    
    def _parse_amount(self, row: pd.Series, amount_cols: List[str]) -> Optional[float]:
        """Parse le montant depuis les colonnes disponibles"""
        def parse_value(val):
            """Parse une valeur en float en gérant les virgules et espaces"""
            if pd.isna(val) or val == '' or val is None:
                return 0.0
            try:
                # Convertir en string et nettoyer
                str_val = str(val).strip()
                if not str_val or str_val.lower() == 'nan':
                    return 0.0
                # Remplacer virgule par point et supprimer les espaces
                str_val = str_val.replace(',', '.').replace(' ', '')
                return float(str_val)
            except:
                return 0.0
        
        # Si on a une colonne 'amount' ou 'montant' directe
        for col in ['amount', 'montant']:
            if col in row.index:
                val = row[col]
                amount = parse_value(val)
                if amount != 0:
                    return amount
        
        # Si on a debit et credit séparés (format français courant)
        debit_col = None
        credit_col = None
        
        # Chercher les colonnes débit/crédit (avec ou sans accents, avec ou sans espaces)
        for col in row.index:
            col_lower = col.lower().strip()
            if 'débit' in col_lower or ('debit' in col_lower and 'credit' not in col_lower and 'crédit' not in col_lower):
                debit_col = col
            elif 'crédit' in col_lower or ('credit' in col_lower and 'debit' not in col_lower and 'débit' not in col_lower):
                credit_col = col
        
        if debit_col and credit_col:
            debit = parse_value(row[debit_col])
            credit = parse_value(row[credit_col])
            
            # Le montant est positif pour un crédit, négatif pour un débit
            if credit > 0:
                return credit
            elif debit > 0:
                return -debit
            elif debit < 0:  # Cas où le débit est déjà négatif dans le CSV
                return debit
            else:
                return None  # Les deux sont vides
        
        # Si seulement crédit existe
        if credit_col:
            credit = parse_value(row[credit_col])
            if credit > 0:
                return credit
        
        # Si seulement débit existe
        if debit_col:
            debit = parse_value(row[debit_col])
            if debit != 0:
                return -abs(debit)  # Toujours négatif pour un débit (même si déjà négatif dans CSV)
        
        # Essayer avec les colonnes trouvées automatiquement
        for col in amount_cols:
            if col in row.index:
                val = row[col]
                amount = parse_value(val)
                if amount != 0:
                    return amount
        
        return None
    
    def _extract_invoice_ref(self, label: str) -> Optional[str]:
        """Extrait une référence de facture depuis le libellé"""
        # Patterns courants pour les références de factures
        # Priorité aux formats IN (les plus courants)
        patterns = [
            # IN2601-0520 ou IN2601-0520/... -> IN2601-0520
            r'(IN\d{4}-\d{3,4})',
            # IN25120498 (sans tiret) -> on le garde tel quel, sera normalisé après
            r'(IN\d{7,8})',
            # FAC2601-0520 ou similaire
            r'(FAC\d{4}-\d{3,4})',
            r'FAC[.\s-]?(\d+)',  # FAC123 ou FAC-123
            r'FAC[.\s-]?([A-Z]{2}\d+)',  # FACA0123
            r'(\d{4}[.\s-]\d{3,})',  # 2024-001 ou 2511-0465
            r'FACTURE[.\s-]?(?:N[°o]?)?[.\s-]?(\d+)',  # FACTURE N°123 ou Facture N251117
            r'N[°o\s]?(\d+)',  # N251117 ou N°123
        ]
        
        for pattern in patterns:
            match = re.search(pattern, label, re.IGNORECASE)
            if match:
                ref = match.group(1) if len(match.groups()) > 0 else match.group(0)
                return ref.upper()
        
        return None

