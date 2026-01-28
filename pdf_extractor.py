"""
Extraction d'informations depuis des factures PDF via IA (OpenAI GPT-5-mini avec support vision)
"""
import base64
import json
import os
from typing import Dict, Optional
from config import OPENAI_API_KEY


class PdfExtractor:
    """Extrait les informations d'une facture PDF via OpenAI (support PDF natif)"""
    
    def __init__(self):
        self.api_key = OPENAI_API_KEY
    
    def extract_invoice_data(self, pdf_path: str) -> Optional[Dict]:
        """
        Extrait les données d'une facture depuis un PDF
        Utilise la conversion PDF -> Image + GPT-5-mini Vision (methode la plus rapide)
        
        Returns:
            Dict avec: supplier_name, invoice_ref, invoice_date, amount_ht, amount_ttc, tva, 
                      address, email, phone, etc.
        """
        if not self.api_key:
            print("[WARN] OPENAI_API_KEY non configuree. Utilisation du mode simulation.")
            return self._simulate_extraction(pdf_path)
        
        # Utiliser directement la méthode image (plus rapide)
        return self._extract_via_image(pdf_path)
    
    def _extract_via_image(self, pdf_path: str) -> Optional[Dict]:
        """Extraction via conversion PDF -> Image puis envoi à l'API OpenAI"""
        
        # Prompt défini en dehors du try pour être accessible dans le fallback
        prompt = """Analyse cette facture et extrait les informations suivantes au format JSON strict:

{
  "supplier_name": "Nom du fournisseur",
  "invoice_ref": "Numéro de facture",
  "invoice_date": "Date au format DD/MM/YYYY",
  "amount_ht": montant_hors_taxes_en_nombre,
  "amount_ttc": montant_toutes_taxes_comprises_en_nombre,
  "tva_amount": montant_tva_en_nombre,
  "tva_rate": taux_tva_en_pourcentage,
  "address": "Adresse complète du fournisseur",
  "zip_code": "Code postal",
  "town": "Ville",
  "email": "Email si présent",
  "phone": "Téléphone si présent",
  "description": "Description des prestations/produits",
  "payment_terms": "Conditions de paiement si présentes"
}

Réponds UNIQUEMENT avec le JSON, sans texte supplémentaire."""

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            images_base64 = self._pdf_to_images_base64(pdf_path)
            
            if not images_base64:
                return self._simulate_extraction(pdf_path)

            print(f"[IA] Envoi de {len(images_base64)} image(s) a GPT-5-mini...")
            
            # Construire le contenu avec toutes les images
            content = []
            for i, img_base64 in enumerate(images_base64):
                content.append({
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{img_base64}"
                })
            content.append({
                "type": "input_text",
                "text": prompt
            })
            
            # Utiliser la nouvelle API responses avec GPT-5-mini
            response = client.responses.create(
                model="gpt-5-mini",
                input=[
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            )
            
            # Vérifier que la réponse existe
            content = getattr(response, 'output_text', None)
            
            if not content:
                # Essayer d'autres attributs possibles
                if hasattr(response, 'output') and response.output:
                    for item in response.output:
                        if hasattr(item, 'content') and item.content:
                            for c in item.content:
                                if hasattr(c, 'text'):
                                    content = c.text
                                    break
                
                if not content:
                    print(f"[ERR] Reponse vide de l'API. Response: {response}")
                    raise ValueError("Reponse vide de l'API OpenAI")
            
            print(f"[IA] Reponse recue: {content[:200]}...")
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            print(f"[IA] Extraction reussie: {data.get('supplier_name', 'N/A')}")
            return data
            
        except Exception as e:
            print(f"[ERR] Erreur extraction via API responses: {e}")
            print("[INFO] Tentative avec l'API chat.completions...")
            
            # Fallback vers l'ancienne API plus stable
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key)
                
                images_base64 = self._pdf_to_images_base64(pdf_path)
                if not images_base64:
                    return self._simulate_extraction(pdf_path)
                
                # Construire le contenu avec toutes les images
                message_content = [{"type": "text", "text": prompt}]
                for img_base64 in images_base64:
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_base64}"
                        }
                    })
                
                print(f"[IA] Envoi de {len(images_base64)} image(s) a GPT-5-mini (fallback)...")
                
                response = client.chat.completions.create(
                    model="gpt-5-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": message_content
                        }
                    ],
                    max_tokens=1000
                )
                
                content = response.choices[0].message.content
                print(f"[IA] Reponse recue (fallback): {content[:200]}...")
                
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                data = json.loads(content.strip())
                print(f"[IA] Extraction reussie (fallback): {data.get('supplier_name', 'N/A')}")
                return data
                
            except Exception as e2:
                print(f"[ERR] Erreur fallback: {e2}")
                return self._simulate_extraction(pdf_path)
    
    def _read_pdf_base64(self, pdf_path: str) -> str:
        """Lit un PDF et retourne son contenu encodé en base64"""
        try:
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            base64_string = base64.b64encode(pdf_bytes).decode('utf-8')
            print(f"[PDF] Fichier lu: {len(base64_string)} caracteres base64")
            return base64_string
        except Exception as e:
            print(f"[ERR] Erreur lecture PDF: {e}")
            return ""
    
    def _pdf_to_image_base64(self, pdf_path: str) -> str:
        """Convertit la première page d'un PDF en image base64 (pour compatibilité)"""
        images = self._pdf_to_images_base64(pdf_path)
        return images[0] if images else ""
    
    def _pdf_to_images_base64(self, pdf_path: str) -> list:
        """Convertit TOUTES les pages d'un PDF en images base64"""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(pdf_path)
            
            if len(doc) == 0:
                print("[ERR] Le PDF est vide")
                return []
            
            print(f"[PDF] Conversion du PDF en images ({len(doc)} pages)...")
            
            images_base64 = []
            total_size = 0
            
            for i, page in enumerate(doc):
                # Resolution 1.5x (bon compromis vitesse/qualite)
                mat = fitz.Matrix(1.5, 1.5)
                pix = page.get_pixmap(matrix=mat)
                
                # Convertir en JPEG (plus petit que PNG)
                jpg_bytes = pix.tobytes("jpeg")
                image_base64 = base64.b64encode(jpg_bytes).decode('utf-8')
                images_base64.append(image_base64)
                
                size_kb = len(jpg_bytes) / 1024
                total_size += size_kb
                print(f"   Page {i+1}: {size_kb:.0f} KB")
            
            doc.close()
            
            print(f"[PDF] {len(images_base64)} images generees: {total_size:.0f} KB total")
            return images_base64
            
        except ImportError:
            print("[ERR] PyMuPDF (fitz) non installe. Installez avec: pip install PyMuPDF")
            return []
        except Exception as e:
            print(f"[ERR] Erreur conversion PDF->Images: {e}")
            return []
    
    def _simulate_extraction(self, pdf_path: str) -> Dict:
        """Mode simulation pour tester sans API OpenAI"""
        import os
        filename = os.path.basename(pdf_path)
        
        return {
            "supplier_name": "FOURNISSEUR SIMULÉ",
            "invoice_ref": f"SIM-{filename[:10]}",
            "invoice_date": "01/01/2025",
            "amount_ht": 1000.00,
            "amount_ttc": 1200.00,
            "tva_amount": 200.00,
            "tva_rate": 20.0,
            "address": "123 Rue de la Simulation",
            "zip_code": "75001",
            "town": "Paris",
            "email": "contact@simulation.fr",
            "phone": "0123456789",
            "description": "Prestation simulée depuis PDF",
            "payment_terms": "30 jours",
            "is_simulation": True
        }

