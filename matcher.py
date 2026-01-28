"""
Algorithme de matching entre transactions CSV et données Dolibarr
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from config import AMOUNT_TOLERANCE, DATE_TOLERANCE_DAYS
import math
import re


class TransactionMatcher:
    """Gère le matching entre transactions CSV et factures/lignes bancaires Dolibarr"""
    
    # Patterns pour extraire le nom du tiers depuis le libellé bancaire
    # Ordre important : les plus spécifiques en premier
    LABEL_PATTERNS = [
        # VIRT RECU M. JULIEN-PIERRE OFF EUR -> JULIEN-PIERRE OFF (ignore M. Mme etc)
        r'VIRT\s+RECU\s+(?:M\.|MME|MR|MRS|MLLE)?\s*([A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+){0,2})\s+EUR',
        # VIRT RECU ORIO ILTUD EUR 950,00 de ORIO ILTUD -> ORIO ILTUD
        r'VIRT\s+RECU\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+EUR',
        # VIRT RECU SARL SPEH IN... -> SARL SPEH ou SPEH
        r'VIRT\s+RECU\s+((?:SARL|SAS|EURL|SA|SCI|SNC|SASU)?\s*[A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+)?)\s+IN',
        # VIRT RECU NOM PRENOM ... -> NOM PRENOM (avant EUR/XPF/IN//)
        r'VIRT\s+RECU\s+(?:M\.|MME|MR|MRS|MLLE)?\s*([A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+){0,2})(?:\s+EUR|\s+XPF|\s+IN|\s+/)',
        # VIRT FAV GESCOAD Facture -> GESCOAD
        r'VIRT\s+(?:FAV|EUR)\s+([A-Z][A-Z0-9\s\-\.]+?)(?:\s+Facture|\s+FAC|\s+N\d|\s+EUR|\s*$)',
        # PREL C/C VITI SAS VITI PRELEVEMENT -> VITI SAS ou VITI
        r'PREL\s+C/C\s+([A-Z][A-Z0-9\s\-\.]+?)(?:\s+PREL|\s+PRELEVEMENT|\s*$)',
        # FRS TRANSF FAV Gilbert EHUEINA -> Gilbert EHUEINA  
        r'(?:FRS\s+)?TRANSF\s+FAV\s+([A-Z][A-Za-z0-9\s\-\.]+?)(?:\s+EUR|\s+XPF|\s+\d|\s*$)',
        # CION TRANSF FAV Gilbert -> Gilbert
        r'CION\s+(?:S/\s+)?(?:TRANSF\s+)?(?:FAV\s+)?([A-Z][A-Za-z0-9\s\-\.]+?)(?:\s+EUR|\s+XPF|\s+\d|\s*$)',
        # VIR ETR RECU O/ BENJAMIN -> BENJAMIN
        r'VIR\s+ETR\s+RECU\s+O/\s*([A-Z][A-Za-z0-9\s\-\.]+?)(?:\s+EUR|\s+XPF|\s+\d|\s*$)',
        # VIR SEPA RECU DE: NOM PRENOM -> NOM PRENOM
        r'VIR\s+(?:SEPA\s+)?RECU\s+(?:DE:?\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})',
        # PREL C/C SAS ONATI -> SAS ONATI ou ONATI
        r'PREL\s+C/C\s+(?:SAS\s+)?([A-Z][A-Z0-9\s\-\.]+?)(?:\s+-|\s+ABONNE|\s+FAC|\s*$)',
    ]
    
    def __init__(self):
        self.amount_tolerance = AMOUNT_TOLERANCE
        self.date_tolerance_days = DATE_TOLERANCE_DAYS
    
    def extract_thirdparty_from_label(self, label: str) -> Optional[str]:
        """Extrait le nom potentiel du tiers depuis un libellé bancaire"""
        if not label:
            return None
        
        label_upper = label.upper().strip()
        
        for pattern in self.LABEL_PATTERNS:
            match = re.search(pattern, label_upper, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Nettoyer le nom (retirer les mots inutiles à la fin)
                name = re.sub(r'\s+(EUR|XPF|USD|CHF|\d+[,\.]\d+).*$', '', name)
                name = re.sub(r'\s+de\s+.*$', '', name, flags=re.IGNORECASE)
                name = re.sub(r'\s+/\s*$', '', name)
                name = re.sub(r'\s+IN\d+.*$', '', name)  # Retirer les références IN
                name = name.strip()
                
                # Nettoyer les formes juridiques au début si le reste est assez long
                name_without_legal = re.sub(r'^(SARL|SAS|EURL|SA|SCI|SNC|SASU|ETS|CIE)\s+', '', name)
                if len(name_without_legal) >= 3:
                    # Garder le nom avec la forme juridique mais aussi proposer sans
                    name = name_without_legal
                
                if len(name) >= 3:  # Au moins 3 caractères
                    return name
        
        return None
    
    def get_thirdparty_search_variants(self, name: str) -> List[str]:
        """
        Génère des variantes de recherche pour un nom de tiers
        Ex: "ORIO ILTUD" -> ["ORIO ILTUD", "ILTUD ORIO", "ORIO", "ILTUD"]
        """
        if not name:
            return []
        
        variants = []
        name = name.strip()
        
        # Nom original
        variants.append(name)
        
        # Version title case
        variants.append(name.title())
        
        # Si le nom contient des espaces, essayer les parties inversées
        parts = name.split()
        if len(parts) >= 2:
            # Inverser les parties (NOM PRENOM -> PRENOM NOM)
            reversed_name = ' '.join(reversed(parts))
            variants.append(reversed_name)
            variants.append(reversed_name.title())
            
            # Chaque partie séparément
            for part in parts:
                if len(part) >= 3:
                    variants.append(part)
                    variants.append(part.title())
        
        # Retirer les doublons tout en gardant l'ordre
        seen = set()
        unique_variants = []
        for v in variants:
            v_lower = v.lower()
            if v_lower not in seen:
                seen.add(v_lower)
                unique_variants.append(v)
        
        return unique_variants
    
    # Mapping des mois français vers numéros
    MONTH_NAMES = {
        'janvier': '01', 'jan': '01', 'janv': '01',
        'fevrier': '02', 'février': '02', 'fev': '02', 'févr': '02',
        'mars': '03', 'mar': '03',
        'avril': '04', 'avr': '04',
        'mai': '05',
        'juin': '06', 'jun': '06',
        'juillet': '07', 'juil': '07', 'jul': '07',
        'aout': '08', 'août': '08', 'aou': '08',
        'septembre': '09', 'sept': '09', 'sep': '09',
        'octobre': '10', 'oct': '10',
        'novembre': '11', 'nov': '11',
        'decembre': '12', 'décembre': '12', 'dec': '12', 'déc': '12'
    }
    
    def extract_period_from_label(self, label: str) -> Optional[Tuple[str, str]]:
        """
        Extrait le mois et l'année depuis le libellé de la transaction
        Ex: "Amarrage Edo janvier 25" -> ('01', '25')
        Ex: "Loyer mars 2025" -> ('03', '25')
        Ex: "Facture 01/2025" -> ('01', '25')
        Returns: (mois, année courte) ou None
        """
        if not label:
            return None
        
        label_lower = label.lower()
        
        # Pattern 1: "mois année" (janvier 25, mars 2025, etc.)
        for month_name, month_num in self.MONTH_NAMES.items():
            pattern = rf'\b{month_name}\s*[\'"]?\s*(\d{{2}}(?:\d{{2}})?)\b'
            match = re.search(pattern, label_lower)
            if match:
                year = match.group(1)
                if len(year) == 4:
                    year = year[2:]  # 2025 -> 25
                return (month_num, year)
        
        # Pattern 2: "MM/YYYY" ou "MM-YYYY" ou "MM.YYYY"
        match = re.search(r'\b(\d{2})[/\-\.](\d{4})\b', label)
        if match:
            month = match.group(1)
            year = match.group(2)[2:]  # 2025 -> 25
            if 1 <= int(month) <= 12:
                return (month, year)
        
        # Pattern 3: "MM/YY" ou "MM-YY"
        match = re.search(r'\b(\d{2})[/\-\.](\d{2})\b', label)
        if match:
            month = match.group(1)
            year = match.group(2)
            if 1 <= int(month) <= 12:
                return (month, year)
        
        return None
    
    def extract_period_from_invoice_ref(self, ref: str) -> Optional[Tuple[str, str]]:
        """
        Extrait le mois et l'année depuis une référence de facture Dolibarr
        Ex: "IN2501-0235" -> ('01', '25') pour janvier 2025
        Ex: "IN2601-0540" -> ('01', '26') pour janvier 2026
        Ex: "(PROV25)" -> None (pas de mois)
        Returns: (mois, année courte) ou None
        """
        if not ref:
            return None
        
        # Pattern IN + année(2) + mois(2) + numéro
        # Ex: IN2501-0235 = année 25, mois 01
        match = re.search(r'IN(\d{2})(\d{2})[-\s]?\d+', ref, re.IGNORECASE)
        if match:
            year = match.group(1)  # 25
            month = match.group(2)  # 01
            if 1 <= int(month) <= 12:
                return (month, year)
        
        # Pattern FA ou FAC + année + mois
        match = re.search(r'FA[C]?(\d{2})(\d{2})[-\s]?\d+', ref, re.IGNORECASE)
        if match:
            year = match.group(1)
            month = match.group(2)
            if 1 <= int(month) <= 12:
                return (month, year)
        
        return None
    
    def period_matches(self, label_period: Tuple[str, str], invoice_period: Tuple[str, str]) -> Tuple[bool, int]:
        """
        Compare deux périodes et retourne (correspondance, bonus/malus)
        - Même mois et année: +30 (bonus)
        - Même année, mois différent: 0
        - Année différente: -50 (malus important)
        """
        if not label_period or not invoice_period:
            return (False, 0)
        
        label_month, label_year = label_period
        inv_month, inv_year = invoice_period
        
        # Même année et même mois = parfait
        if label_year == inv_year and label_month == inv_month:
            return (True, 30)
        
        # Même année, mois différent = acceptable
        if label_year == inv_year:
            return (False, 0)
        
        # Année différente = mauvais match, pénalité importante
        return (False, -50)
    
    def normalize_name_for_comparison(self, name: str) -> str:
        """Normalise un nom pour la comparaison (minuscule, sans accents, sans espaces multiples)"""
        if not name:
            return ''
        # Minuscule
        name = name.lower().strip()
        # Remplacer les caractères accentués courants
        replacements = {
            'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
            'à': 'a', 'â': 'a', 'ä': 'a',
            'î': 'i', 'ï': 'i',
            'ô': 'o', 'ö': 'o',
            'ù': 'u', 'û': 'u', 'ü': 'u',
            'ç': 'c', 'ñ': 'n'
        }
        for old, new in replacements.items():
            name = name.replace(old, new)
        # Retirer les caractères spéciaux
        name = re.sub(r'[^a-z0-9\s]', '', name)
        # Normaliser les espaces
        name = ' '.join(name.split())
        return name
    
    def names_match(self, name1: str, name2: str) -> bool:
        """
        Vérifie si deux noms correspondent (avec inversion possible)
        Ex: "ORIO ILTUD" == "Iltud Orio"
        """
        if not name1 or not name2:
            return False
        
        n1 = self.normalize_name_for_comparison(name1)
        n2 = self.normalize_name_for_comparison(name2)
        
        # Correspondance directe
        if n1 == n2:
            return True
        
        # Correspondance avec parties inversées
        parts1 = n1.split()
        parts2 = n2.split()
        
        if len(parts1) >= 2 and len(parts2) >= 2:
            # Vérifier si c'est le même nom inversé
            if set(parts1) == set(parts2):
                return True
        
        # Vérifier si un nom contient tous les mots de l'autre
        if len(parts1) >= 2 and len(parts2) >= 2:
            if all(p in parts2 for p in parts1) or all(p in parts1 for p in parts2):
                return True
        
        return False
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calcule un score de similarité entre deux noms (0-100)
        Gère l'inversion des prénoms/noms
        """
        if not name1 or not name2:
            return 0.0
        
        n1 = self.normalize_name_for_comparison(name1)
        n2 = self.normalize_name_for_comparison(name2)
        
        # Correspondance exacte
        if n1 == n2:
            return 100.0
        
        parts1 = set(n1.split())
        parts2 = set(n2.split())
        
        # Correspondance exacte des parties (ordre différent)
        if parts1 == parts2:
            return 95.0
        
        # Intersection des parties
        if parts1 and parts2:
            intersection = len(parts1 & parts2)
            union = len(parts1 | parts2)
            jaccard = intersection / union
            
            # Bonus si toutes les parties d'un nom sont dans l'autre
            if parts1.issubset(parts2) or parts2.issubset(parts1):
                return max(70.0, jaccard * 100)
            
            if jaccard > 0:
                return jaccard * 80
        
        # Vérifier si un nom commence par l'autre ou l'inverse
        if n1.startswith(n2) or n2.startswith(n1):
            return 60.0
        
        # Vérifier si un mot clé est présent
        for part in parts1:
            if len(part) >= 4 and part in n2:
                return 50.0
        
        return 0.0
    
    def match_transactions(self, csv_transactions: List[Dict], 
                         customer_invoices: List[Dict],
                         supplier_invoices: List[Dict], 
                         bank_lines: List[Dict]) -> List[Dict]:
        """
        Match les transactions CSV avec les factures et lignes bancaires
        
        Args:
            csv_transactions: Liste des transactions du CSV
            customer_invoices: Liste des factures clients depuis Dolibarr
            supplier_invoices: Liste des factures fournisseurs depuis Dolibarr
            bank_lines: Liste des lignes bancaires depuis Dolibarr
        
        Returns:
            Liste des transactions avec leurs matches potentiels
        """
        matched_transactions = []
        
        for transaction in csv_transactions:
            matches = {
                'transaction': transaction,
                'invoice_matches': [],
                'bank_line_matches': [],
                'best_match': None,
                'match_score': 0
            }
            
            # Déterminer quel type de facture chercher selon le montant
            transaction_amount = transaction['amount']
            
            if transaction_amount > 0:
                # Crédit (entrée d'argent) -> Facture client
                invoice_matches = self._match_with_invoices(transaction, customer_invoices, invoice_type='customer')
            else:
                # Débit (sortie d'argent) -> Facture fournisseur
                invoice_matches = self._match_with_invoices(transaction, supplier_invoices, invoice_type='supplier')
            
            matches['invoice_matches'] = invoice_matches
            
            # Chercher des matches avec les lignes bancaires existantes
            bank_line_matches = self._match_with_bank_lines(transaction, bank_lines)
            matches['bank_line_matches'] = bank_line_matches
            
            # Déterminer le meilleur match
            best_match = self._determine_best_match(invoice_matches, bank_line_matches)
            matches['best_match'] = best_match
            
            if best_match:
                matches['match_score'] = best_match.get('score', 0)
            
            matched_transactions.append(matches)
        
        return matched_transactions
    
    def _match_with_invoices(self, transaction: Dict, invoices: List[Dict], invoice_type: str = 'customer') -> List[Dict]:
        """
        Trouve les factures correspondant à une transaction
        
        Args:
            transaction: Transaction du CSV
            invoices: Liste des factures
            invoice_type: Type de facture ('customer' ou 'supplier')
        """
        matches = []
        transaction_amount = abs(transaction['amount'])
        transaction_date = datetime.fromtimestamp(int(transaction['date']))
        
        # Extraire l'année de la transaction (format court: 25 pour 2025)
        transaction_year = str(transaction_date.year)[2:]  # 2025 -> "25"
        transaction_month = f"{transaction_date.month:02d}"  # 1 -> "01"
        
        for invoice in invoices:
            # Pour les factures fournisseurs, le champ peut être différent
            if invoice_type == 'supplier':
                total_ht = invoice.get('total_ht') or invoice.get('total_ttc') or 0
                invoice_amount = abs(float(total_ht)) if total_ht else 0
                remaintopay_raw = invoice.get('remaintopay')
                remain_to_pay = abs(float(remaintopay_raw)) if remaintopay_raw is not None else invoice_amount
            else:
                total_ttc = invoice.get('total_ttc') or 0
                invoice_amount = abs(float(total_ttc)) if total_ttc else 0
                remaintopay_raw = invoice.get('remaintopay')
                remain_to_pay = abs(float(remaintopay_raw)) if remaintopay_raw is not None else invoice_amount
            
            # Ignorer les factures sans montant
            if invoice_amount == 0:
                continue
            
            # Score de matching
            score = 0
            reasons = []
            
            # Matching par montant
            amount_match = self._match_amount(transaction_amount, remain_to_pay)
            if amount_match['matched']:
                score += amount_match['score']
                reasons.append(f"Montant correspond ({amount_match['reason']})")
            
            # Matching par période - PRIORITÉ: utiliser la date de transaction
            invoice_ref = invoice.get('ref', '')
            invoice_period = self.extract_period_from_invoice_ref(invoice_ref)
            
            # D'abord vérifier si l'année de la facture correspond à l'année de la transaction
            if invoice_period:
                inv_month, inv_year = invoice_period
                
                # Si l'année de la facture ne correspond pas à la transaction = GROS malus
                if inv_year != transaction_year:
                    score -= 80  # Pénalité très importante pour mauvaise année
                    reasons.append(f"⚠️ Année incorrecte: transaction={transaction_year}, facture={inv_year}")
                else:
                    # Même année = bonus
                    score += 20
                    reasons.append(f"Année correspond (20{inv_year})")
                    
                    # Bonus supplémentaire si même mois
                    if inv_month == transaction_month:
                        score += 15
                        reasons.append(f"Mois correspond ({inv_month})")
            
            # Ensuite vérifier si le libellé mentionne une période spécifique
            label_period = self.extract_period_from_label(transaction.get('label', ''))
            if label_period and invoice_period:
                label_month, label_year = label_period
                inv_month, inv_year = invoice_period
                
                if label_year == inv_year and label_month == inv_month:
                    score += 25
                    reasons.append(f"Période libellé correspond ({label_month}/{label_year})")
                elif label_year != inv_year:
                    score -= 30  # Malus supplémentaire si le libellé mentionne une autre année
                    reasons.append(f"⚠️ Libellé mentionne {label_month}/{label_year}")
            
            # Matching par référence dans le libellé
            # Extraire la référence depuis le libellé de la transaction
            extracted_ref = self.extract_invoice_ref_from_label(transaction.get('label', ''))
            tx_ref = transaction.get('invoice_ref') or extracted_ref
            
            if tx_ref:
                invoice_ref = invoice.get('ref', '')
                invoice_ref_supplier = invoice.get('ref_supplier', '')
                invoice_ref_ext = invoice.get('ref_ext', '')
                
                # Normaliser toutes les références
                tx_ref_normalized = self.normalize_invoice_ref(tx_ref)
                
                # Vérifier correspondance avec ref, ref_supplier ou ref_ext
                refs_to_check = [invoice_ref, invoice_ref_supplier, invoice_ref_ext]
                
                for inv_ref in refs_to_check:
                    if inv_ref and self.refs_match(tx_ref, inv_ref):
                        score += 80  # Score très élevé pour une correspondance de référence
                        reasons.append(f"Référence {tx_ref_normalized} correspond à {inv_ref}")
                        break
                else:
                    # Vérifier correspondance partielle
                    tx_ref_clean = self._normalize_ref(tx_ref)
                    for inv_ref in refs_to_check:
                        if inv_ref:
                            inv_ref_clean = self._normalize_ref(inv_ref)
                            # Les 4 derniers chiffres correspondent
                            if len(tx_ref_clean) >= 4 and len(inv_ref_clean) >= 4:
                                if tx_ref_clean[-4:] == inv_ref_clean[-4:]:
                                    score += 40
                                    reasons.append(f"Référence partielle: ...{tx_ref_clean[-4:]}")
                                    break
            
            # Matching par date (si la facture a une date d'échéance)
            if invoice.get('date_lim_reglement'):
                due_date = datetime.fromtimestamp(int(invoice['date_lim_reglement']))
                date_match = self._match_date(transaction_date, due_date)
                if date_match['matched']:
                    score += date_match['score']
                    reasons.append(f"Date proche ({date_match['reason']})")
            
            # Matching par tiers - CRITIQUE: une facture doit correspondre au bon tiers
            thirdparty_name = None
            if invoice.get('thirdparty'):
                thirdparty_name = invoice['thirdparty'].get('name', '')
            elif invoice.get('thirdparty_name'):
                thirdparty_name = invoice.get('thirdparty_name', '')
            elif invoice.get('socname'):
                thirdparty_name = invoice.get('socname', '')
            
            transaction_label = transaction.get('label', '')
            
            # Extraire le nom potentiel du libellé
            extracted_name = self.extract_thirdparty_from_label(transaction_label)
            
            # Variable pour tracker si le tiers correspond
            thirdparty_matches = False
            
            if thirdparty_name and extracted_name:
                # Utiliser le nouveau système de comparaison intelligent
                name_similarity = self.calculate_name_similarity(extracted_name, thirdparty_name)
                
                if name_similarity >= 70:
                    thirdparty_matches = True
                    score += 60  # Gros bonus pour tiers qui correspond
                    reasons.append(f"✓ Tiers correspond: {extracted_name} ≈ {thirdparty_name}")
                elif name_similarity >= 50:
                    thirdparty_matches = True
                    score += 40
                    reasons.append(f"Tiers similaire: {extracted_name} ~ {thirdparty_name}")
                elif name_similarity < 30:
                    # Le tiers de la facture ne correspond PAS au tiers du libellé
                    # C'est probablement une mauvaise facture -> GROS malus
                    score -= 100
                    reasons.append(f"⛔ Tiers différent: {extracted_name} ≠ {thirdparty_name}")
            
            # Fallback: vérifier si le nom du tiers est directement dans le libellé
            if thirdparty_name and transaction_label and not thirdparty_matches:
                thirdparty_upper = thirdparty_name.upper()
                label_upper = transaction_label.upper()
                
                # Vérifier correspondance directe
                if thirdparty_upper in label_upper:
                    thirdparty_matches = True
                    score += 50
                    reasons.append("✓ Nom du tiers dans le libellé")
                else:
                    # Essayer chaque partie du nom
                    name_parts = [p for p in thirdparty_upper.split() if len(p) > 2]
                    if name_parts:
                        matched_parts = sum(1 for part in name_parts if part in label_upper)
                        match_ratio = matched_parts / len(name_parts)
                        
                        if match_ratio >= 0.5:
                            thirdparty_matches = True
                            score += 30
                            reasons.append(f"Parties du nom trouvées ({matched_parts}/{len(name_parts)})")
                        elif extracted_name and match_ratio == 0:
                            # Aucune partie du nom trouvée et on a extrait un autre nom
                            # C'est probablement une mauvaise facture
                            score -= 80
                            reasons.append(f"⛔ Tiers non trouvé dans libellé")
            
            # Seuil minimum de 30 pour éviter les matchs peu fiables
            if score >= 30:
                matches.append({
                    'invoice': invoice,
                    'invoice_type': invoice_type,
                    'score': max(0, score),  # Pas de score négatif affiché
                    'reasons': reasons,
                    'amount_diff': abs(transaction_amount - remain_to_pay),
                    'matched': True
                })
        
        # Trier par score décroissant
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches[:5]  # Retourner les 5 meilleurs matches
    
    def _match_with_bank_lines(self, transaction: Dict, bank_lines: List[Dict]) -> List[Dict]:
        """Trouve les lignes bancaires correspondant à une transaction"""
        matches = []
        transaction_amount = abs(transaction['amount'])
        transaction_date = datetime.fromtimestamp(int(transaction['date']))
        
        for bank_line in bank_lines:
            bank_amount = abs(float(bank_line.get('amount', 0)))
            
            score = 0
            reasons = []
            
            # Matching par montant exact
            if math.isclose(transaction_amount, bank_amount, abs_tol=self.amount_tolerance):
                score += 100
                reasons.append("Montant exact")
            
            # Matching par libellé similaire
            bank_label = bank_line.get('label', '').upper()
            transaction_label = transaction.get('label', '').upper()
            if bank_label and transaction_label:
                similarity = self._calculate_similarity(bank_label, transaction_label)
                if similarity > 0.7:
                    score += int(similarity * 30)
                    reasons.append(f"Libellé similaire ({similarity:.0%})")
            
            # Matching par date
            if bank_line.get('date'):
                bank_date = datetime.fromtimestamp(int(bank_line['date']))
                date_match = self._match_date(transaction_date, bank_date)
                if date_match['matched']:
                    score += date_match['score']
                    reasons.append(f"Date proche ({date_match['reason']})")
            
            if score > 30:
                matches.append({
                    'bank_line': bank_line,
                    'score': score,
                    'reasons': reasons,
                    'amount_diff': abs(transaction_amount - bank_amount),
                    'matched': True
                })
        
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches[:3]  # Retourner les 3 meilleurs matches
    
    def _match_amount(self, amount1: float, amount2: float) -> Dict:
        """Vérifie si deux montants correspondent"""
        diff = abs(amount1 - amount2)
        
        # Montant exact
        if diff < self.amount_tolerance:
            return {'matched': True, 'score': 100, 'reason': 'Montant exact'}
        
        # Montant très proche (tolérance 0.1%)
        if diff / max(amount1, amount2) < 0.001:
            return {'matched': True, 'score': 90, 'reason': 'Montant très proche'}
        
        # Montant proche (tolérance 1%)
        if diff / max(amount1, amount2) < 0.01:
            return {'matched': True, 'score': 70, 'reason': 'Montant proche'}
        
        # Montant relativement proche (tolérance 5%)
        if diff / max(amount1, amount2) < 0.05:
            return {'matched': True, 'score': 40, 'reason': 'Montant relativement proche'}
        
        return {'matched': False, 'score': 0, 'reason': ''}
    
    def _match_date(self, date1: datetime, date2: datetime) -> Dict:
        """Vérifie si deux dates correspondent"""
        diff_days = abs((date1 - date2).days)
        
        if diff_days == 0:
            return {'matched': True, 'score': 30, 'reason': 'Même jour'}
        elif diff_days <= 1:
            return {'matched': True, 'score': 25, 'reason': f'{diff_days} jour(s) d\'écart'}
        elif diff_days <= self.date_tolerance_days:
            return {'matched': True, 'score': 20 - diff_days, 'reason': f'{diff_days} jours d\'écart'}
        
        return {'matched': False, 'score': 0, 'reason': ''}
    
    def _normalize_ref(self, ref: str) -> str:
        """Normalise une référence pour faciliter la comparaison"""
        if not ref:
            return ''
        # Supprimer les espaces, tirets, points
        normalized = str(ref).upper().replace(' ', '').replace('-', '').replace('.', '').replace('_', '')
        return normalized
    
    def extract_invoice_ref_from_label(self, label: str) -> Optional[str]:
        """
        Extrait une référence de facture depuis un libellé bancaire
        Gère les formats: IN2601-0520, IN25120498, etc.
        """
        if not label:
            return None
        
        label_upper = label.upper()
        
        # Pattern 1: IN2601-0520 (avec tiret)
        match = re.search(r'(IN\d{4}-\d{3,4})', label_upper)
        if match:
            return match.group(1)
        
        # Pattern 2: IN25120498 (sans tiret) -> normaliser en IN2512-0498
        match = re.search(r'IN(\d{4})(\d{3,4})', label_upper)
        if match:
            return f"IN{match.group(1)}-{match.group(2)}"
        
        # Pattern 3: FAC similaire
        match = re.search(r'(FAC\d{4}-\d{3,4})', label_upper)
        if match:
            return match.group(1)
        
        match = re.search(r'FAC(\d{4})(\d{3,4})', label_upper)
        if match:
            return f"FAC{match.group(1)}-{match.group(2)}"
        
        return None
    
    def normalize_invoice_ref(self, ref: str) -> str:
        """
        Normalise une référence de facture pour la comparaison
        IN25120498 -> IN2512-0498
        IN2512-0498 -> IN2512-0498
        """
        if not ref:
            return ''
        
        ref = str(ref).upper().strip()
        
        # Si déjà au bon format avec tiret
        if re.match(r'^IN\d{4}-\d{3,4}$', ref):
            return ref
        
        # Si format sans tiret IN25120498
        match = re.match(r'^IN(\d{4})(\d{3,4})$', ref)
        if match:
            return f"IN{match.group(1)}-{match.group(2)}"
        
        # Même chose pour FAC
        if re.match(r'^FAC\d{4}-\d{3,4}$', ref):
            return ref
        
        match = re.match(r'^FAC(\d{4})(\d{3,4})$', ref)
        if match:
            return f"FAC{match.group(1)}-{match.group(2)}"
        
        return ref
    
    def refs_match(self, ref1: str, ref2: str) -> bool:
        """
        Vérifie si deux références de facture correspondent
        Gère les différents formats (avec/sans tiret)
        """
        if not ref1 or not ref2:
            return False
        
        norm1 = self.normalize_invoice_ref(ref1)
        norm2 = self.normalize_invoice_ref(ref2)
        
        if norm1 == norm2:
            return True
        
        # Comparaison sans tirets ni espaces
        clean1 = self._normalize_ref(ref1)
        clean2 = self._normalize_ref(ref2)
        
        if clean1 == clean2:
            return True
        
        # Vérifier si l'un contient l'autre
        if clean1 in clean2 or clean2 in clean1:
            return True
        
        return False
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calcule la similarité entre deux chaînes (simplifié)"""
        if not str1 or not str2:
            return 0.0
        
        # Jaccard similarity simplifié
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _determine_best_match(self, invoice_matches: List[Dict], 
                             bank_line_matches: List[Dict]) -> Optional[Dict]:
        """Détermine le meilleur match global"""
        all_matches = []
        
        for match in invoice_matches:
            all_matches.append({
                'type': 'invoice',
                'invoice_type': match.get('invoice_type', 'customer'),
                'data': match['invoice'],
                'score': match['score'],
                'reasons': match['reasons'],
                'amount_diff': match['amount_diff']
            })
        
        for match in bank_line_matches:
            all_matches.append({
                'type': 'bank_line',
                'data': match['bank_line'],
                'score': match['score'],
                'reasons': match['reasons'],
                'amount_diff': match['amount_diff']
            })
        
        if not all_matches:
            return None
        
        # Retourner le match avec le score le plus élevé
        best = max(all_matches, key=lambda x: x['score'])
        
        # Ne considérer comme bon match que si le score est > 50
        if best['score'] < 50:
            return None
        
        return best

