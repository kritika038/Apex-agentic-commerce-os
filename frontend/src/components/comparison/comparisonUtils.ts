import type { PriceComparisonResponse, ExternalOfferItem } from '../../lib/types/comparison';

export interface PriceComparisonUIState {
  hasMultipleVerifiedStores: boolean;
  hasCanonicalVerified: boolean;
  headerTitle: string;
  headerBadgeText: string;
  headerSupportingText?: string;
  isHeaderEmerald: boolean;
  lowestPriceBannerTitle: string;
  lowestPriceBannerDescription: string;
  lowestPriceBadgeText: string;
  verifiedOffers: ExternalOfferItem[];
  fallbackOffers: ExternalOfferItem[];
  hasExternalVerifiedOffers: boolean;
}

/**
 * Deterministically computes the UI presentation state for Price Intelligence
 * according to strict verified-sources rules:
 *
 * 1. When there is only an Apex/first-party verified offer and NO verified external offer:
 *    - Header Badge: "CANONICAL PRODUCT VERIFIED"
 *    - Supporting text: "No verified external offers available for this product."
 *    - Lowest price messaging: "Lowest verified price among checked sources" (Apex is the only verified source).
 *
 * 2. ONLY show "SAME PHYSICAL PRODUCT ACROSS VERIFIED STORES" when there are at least
 *    TWO verified store listings (Apex + at least 1 verified external retailer).
 *
 * 3. Never use an Apex image as a substitute for an external retailer image.
 */
export function getPriceComparisonUIState(data: PriceComparisonResponse | null): PriceComparisonUIState {
  if (!data) {
    return {
      hasMultipleVerifiedStores: false,
      hasCanonicalVerified: false,
      headerTitle: 'AI Price Intelligence',
      headerBadgeText: 'CANONICAL PRODUCT VERIFIED',
      headerSupportingText: 'No verified external offers available for this product.',
      isHeaderEmerald: false,
      lowestPriceBannerTitle: 'Lowest verified price among checked sources',
      lowestPriceBannerDescription: 'Apex Store is the only verified source for this product.',
      lowestPriceBadgeText: 'Apex Verified Source',
      verifiedOffers: [],
      fallbackOffers: [],
      hasExternalVerifiedOffers: false,
    };
  }

  const hasCanonicalVerified = Boolean(data.canonical_product?.verified);

  const verifiedOffers = (data.offers || []).filter(
    (o) =>
      hasCanonicalVerified &&
      (o.match_type === 'VARIANT_EXACT' ||
        o.match_type === 'EXACT' ||
        o.match_type === 'MODEL_EXACT' ||
        o.match_type === 'EXACT_PRODUCT' ||
        o.match_type === 'EXACT_VERIFIED') &&
      o.price !== null &&
      Boolean(o.external_url) &&
      !o.external_url.includes('/search') &&
      !o.external_url.includes('/s?')
  );

  const fallbackOffers = (data.offers || []).filter(
    (o) => !verifiedOffers.some((vo) => vo.id === o.id)
  );

  // At least 2 verified stores (Apex + at least 1 external verified)
  const hasMultipleVerifiedStores = hasCanonicalVerified && verifiedOffers.length >= 1;

  let headerBadgeText: string;
  let headerSupportingText: string | undefined;
  let isHeaderEmerald = false;

  if (hasMultipleVerifiedStores) {
    headerBadgeText = 'SAME PHYSICAL PRODUCT ACROSS VERIFIED STORES';
    headerSupportingText = undefined;
    isHeaderEmerald = true;
  } else {
    headerBadgeText = 'CANONICAL PRODUCT VERIFIED';
    headerSupportingText = 'No verified external offers available for this product.';
    isHeaderEmerald = false;
  }

  let lowestPriceBannerTitle: string;
  let lowestPriceBannerDescription: string;
  let lowestPriceBadgeText: string;

  if (hasMultipleVerifiedStores) {
    lowestPriceBannerTitle = 'Lowest Verified Deal';
    lowestPriceBannerDescription = data.summary_text || `Lowest verified price on ${data.lowest_store}.`;
    lowestPriceBadgeText = data.apex_is_lowest ? 'Best Price at Apex' : `${data.lowest_store} Deal`;
  } else {
    lowestPriceBannerTitle = 'Lowest verified price among checked sources';
    lowestPriceBannerDescription = 'Apex Store is the only verified source for this product.';
    lowestPriceBadgeText = 'Apex Verified Source';
  }

  return {
    hasMultipleVerifiedStores,
    hasCanonicalVerified,
    headerTitle: 'AI Price Intelligence',
    headerBadgeText,
    headerSupportingText,
    isHeaderEmerald,
    lowestPriceBannerTitle,
    lowestPriceBannerDescription,
    lowestPriceBadgeText,
    verifiedOffers,
    fallbackOffers,
    hasExternalVerifiedOffers: verifiedOffers.length > 0,
  };
}
