export interface ExternalProductIdentity {
  brand?: string | null;
  model?: string | null;
  style_code?: string | null;
  color?: string | null;
  size?: string | null;
  asin?: string | null;
  gtin?: string | null;
}

export interface ExternalOfferItem {
  id: string;
  store_name: string;
  store_domain: string;
  store_logo_url?: string | null;
  store_type: 'RETAILER' | 'OFFICIAL_BRAND' | 'MARKETPLACE' | string;
  external_url: string;
  link_type?: 'EXACT' | 'VARIANT_EXACT' | 'MODEL_EXACT' | 'EXACT_PRODUCT' | 'SIMILAR' | 'SEARCH_FALLBACK' | 'UNAVAILABLE' | string | null;
  action_label?: string | null;
  redirect_url: string;
  price?: number | null;
  mrp?: number | null;
  shipping_price?: number;
  total_price?: number | null;
  currency: string;
  difference_from_apex?: number | null;
  price_delta_label?: string | null;
  match_type: 'EXACT' | 'VARIANT_EXACT' | 'MODEL_EXACT' | 'EXACT_PRODUCT' | 'SIMILAR' | 'SEARCH_FALLBACK' | 'UNAVAILABLE' | string;
  match_confidence: number;
  match_reason?: string | null;
  identity_evidence?: Record<string, unknown> | null;
  source_status: 'VERIFIED' | 'CACHED' | 'SEEDED_DEMO' | 'UNAVAILABLE' | string;
  source_verified: boolean;
  availability: 'IN_STOCK' | 'OUT_OF_STOCK' | 'LIMITED_STOCK' | 'UNKNOWN' | string;
  observed_at: string;
  verified_at?: string | null;
  is_lowest: boolean;
  external_product_id?: string | null;
  external_product_title?: string | null;
  external_image_url?: string | null;
  identity?: ExternalProductIdentity | null;
}

export interface CanonicalProductIdentity {
  canonical_product_id: string;
  brand: string;
  title: string;
  category: string;
  subcategory?: string | null;
  model?: string | null;
  style_code?: string | null;
  gtin?: string | null;
  color?: string | null;
  size?: string | null;
  variant?: string | null;
  canonical_image_url: string;
  verified?: boolean;
}

export interface PriceComparisonResponse {
  product_id: string;
  canonical_product?: CanonicalProductIdentity | null;
  product_name: string;
  product_brand?: string | null;
  product_category: string;
  product_image_url?: string | null;
  apex_price: number;
  apex_mrp?: number | null;
  currency: string;
  offers: ExternalOfferItem[];
  lowest_verified_price: number;
  lowest_store: string;
  lowest_verified_retailer?: string | null;
  apex_difference: number;
  apex_is_lowest: boolean;
  checked_sources: number;
  checked_at: string;
  verification_scope?: string;
  cache_status: string;
  summary_text: string;
}

export interface PriceHistoryItem {
  date: string;
  price: number;
  store_name: string;
}

export interface PriceHistoryResponse {
  product_id: string;
  currency: string;
  history: PriceHistoryItem[];
  has_sufficient_data: boolean;
  message?: string | null;
}
