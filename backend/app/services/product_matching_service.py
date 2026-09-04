import re
from typing import Dict, Any, Tuple, Optional
from decimal import Decimal

class ProductMatchingService:
    """
    Deterministic Multi-Tier Product Matching Engine.
    
    Guarantees:
    - Never hallucinates identical product status.
    - Deterministic hierarchy: GTIN/EAN -> Model Number -> SKU -> Brand+Model -> Title+Variant -> Similar.
    - Returns match_type, confidence score, and explainable audit reason.
    """

    @staticmethod
    def match_products(
        apex_product: Dict[str, Any],
        candidate_product: Dict[str, Any]
    ) -> Tuple[str, float, str]:
        """
        Determines the match classification between an Apex product and an external candidate.
        
        Returns:
            (match_type, confidence, reason)
            match_type: EXACT, VARIANT_EXACT, HIGH_CONFIDENCE, SIMILAR, NO_MATCH
        """
        # Tier 1: Exact GTIN / EAN / UPC match (Definitive global identifier)
        apex_gtin = (apex_product.get("gtin") or "").strip()
        cand_gtin = (candidate_product.get("gtin") or "").strip()
        if apex_gtin and cand_gtin and apex_gtin.lower() == cand_gtin.lower():
            apex_color = (apex_product.get("attributes", {}).get("color") or "").lower()
            cand_color = (candidate_product.get("attributes", {}).get("color") or "").lower()
            apex_size = (apex_product.get("attributes", {}).get("size") or "").lower()
            cand_size = (candidate_product.get("attributes", {}).get("size") or "").lower()
            if (apex_color and cand_color and apex_color == cand_color) and (not apex_size or not cand_size or apex_size == cand_size):
                return "VARIANT_EXACT", 1.0, f"Verified Variant Exact Match: Identical GTIN ({apex_gtin}) and Variant ({apex_color.title()})"
            return "EXACT", 1.0, f"Verified Exact Match: Identical Global Trade Item Number (GTIN: {apex_gtin})"

        # Tier 2: Exact Manufacturer Model Number / Style Code
        apex_model = (apex_product.get("model_number") or "").strip()
        cand_model = (candidate_product.get("model_number") or "").strip()
        if apex_model and cand_model and apex_model.lower() == cand_model.lower():
            apex_color = (apex_product.get("attributes", {}).get("color") or "").lower()
            cand_color = (candidate_product.get("attributes", {}).get("color") or "").lower()
            apex_size = (apex_product.get("attributes", {}).get("size") or "").lower()
            cand_size = (candidate_product.get("attributes", {}).get("size") or "").lower()
            if (apex_color and cand_color and apex_color == cand_color) and (not apex_size or not cand_size or apex_size == cand_size):
                return "VARIANT_EXACT", 0.99, f"Verified Variant Exact Match: Identical Style Code ({apex_model}) and Variant ({apex_color.title()})"
            elif (apex_color and cand_color and apex_color != cand_color) or (apex_size and cand_size and apex_size != cand_size):
                return "MODEL_EXACT", 0.90, f"Model Match: Identical Style Code ({apex_model}) but variant differs ({apex_color or apex_size} vs {cand_color or cand_size})"
            return "EXACT", 0.99, f"Verified Exact Match: Identical Model Number ({apex_model})"

        # Tier 3: Exact SKU matching where provided
        apex_sku = (apex_product.get("sku") or "").strip()
        cand_sku = (candidate_product.get("sku") or "").strip()
        if apex_sku and cand_sku and apex_sku.lower() == cand_sku.lower():
            return "EXACT", 0.98, f"Verified Exact Match: Identical SKU Identifier ({apex_sku})"

        # Normalize Brands and Titles
        apex_brand = (apex_product.get("brand") or "").strip().lower()
        cand_brand = (candidate_product.get("brand") or "").strip().lower()
        apex_title = (apex_product.get("name") or "").strip().lower()
        cand_title = (candidate_product.get("name") or "").strip().lower()

        # Tier 4: Brand + Exact Title Match
        if apex_brand and cand_brand and apex_brand == cand_brand:
            clean_apex = ProductMatchingService._normalize_text(apex_title)
            clean_cand = ProductMatchingService._normalize_text(cand_title)
            
            # Check for Variant match (e.g. Size, Color)
            apex_color = (apex_product.get("attributes", {}).get("color") or "").lower()
            cand_color = (candidate_product.get("attributes", {}).get("color") or "").lower()
            apex_size = (apex_product.get("attributes", {}).get("size") or "").lower()
            cand_size = (candidate_product.get("attributes", {}).get("size") or "").lower()

            if (apex_color and cand_color and apex_color != cand_color) or (apex_size and cand_size and apex_size != cand_size):
                return "MODEL_EXACT", 0.85, f"Model Match: Same model but variant differs ({apex_color or apex_size} vs {cand_color or cand_size})"

            if clean_apex == clean_cand:
                return "EXACT", 0.96, f"Verified Exact Match: Brand ({apex_brand.title()}) and normalized model title identical"

            # Token overlap score
            tokens_apex = set(clean_apex.split())
            tokens_cand = set(clean_cand.split())
            intersection = tokens_apex.intersection(tokens_cand)
            union = tokens_apex.union(tokens_cand)
            jaccard = len(intersection) / len(union) if union else 0.0

            if jaccard >= 0.75:
                if (apex_color and cand_color and apex_color != cand_color) or (apex_size and cand_size and apex_size != cand_size):
                    return "MODEL_EXACT", 0.85, f"Model Match: Brand matches but variant differs ({apex_color or apex_size} vs {cand_color or cand_size})"
                return "SIMILAR", 0.75, f"Similar Product: High lexical overlap ({int(jaccard * 100)}%) within brand {apex_brand.title()}"

        # Tier 5: Category & Keyword similarity across different brands -> SIMILAR
        apex_cat = (apex_product.get("category") or "").lower()
        cand_cat = (candidate_product.get("category") or "").lower()
        if apex_cat and cand_cat and (apex_cat in cand_cat or cand_cat in apex_cat):
            clean_apex = ProductMatchingService._normalize_text(apex_title)
            clean_cand = ProductMatchingService._normalize_text(cand_title)
            tokens_apex = set(clean_apex.split())
            tokens_cand = set(clean_cand.split())
            if len(tokens_apex.intersection(tokens_cand)) >= 2:
                return "SIMILAR", 0.55, "Similar Product: Matches category and functional keywords"

        return "UNAVAILABLE", 0.0, "No verified match found"

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
