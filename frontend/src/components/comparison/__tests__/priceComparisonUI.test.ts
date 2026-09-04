import { test, describe } from 'node:test';
import assert from 'node:assert';
import { getPriceComparisonUIState } from '../comparisonUtils.ts';
import type { PriceComparisonResponse } from '../../../lib/types/comparison.ts';

describe('Price Intelligence UI Wording & State Tests', () => {

  // =========================================================================
  // SCENARIO A: Apex-Only Verified Product (No External Verified Offer)
  // =========================================================================
  test('Scenario A: Apex-only verified product renders CANONICAL PRODUCT VERIFIED and single-source lowest price banner', () => {
    const mockData: PriceComparisonResponse = {
      product_id: 'prod_apex_only_001',
      product_name: 'SpeedFlow Marathon Shoes',
      product_brand: 'Adidas',
      product_category: 'Running',
      product_image_url: 'https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a',
      apex_price: 2999.0,
      apex_mrp: 3999.0,
      currency: 'INR',
      canonical_product: {
        canonical_product_id: 'canon_adidas_duramo_speed_black',
        brand: 'Adidas',
        title: 'Adidas Duramo Speed Road Running Shoes',
        category: 'Running',
        style_code: 'IE7263',
        gtin: '4066749964179',
        variant: 'Core Black',
        canonical_image_url: 'https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a',
        verified: true,
      },
      offers: [
        {
          id: 'off_amz_search',
          store_name: 'Amazon India',
          store_domain: 'amazon.in',
          store_type: 'MARKETPLACE',
          external_url: 'https://www.amazon.in/s?k=Adidas+Duramo+Speed+IE7263',
          redirect_url: '/api/v1/external-offers/redirect?target=https://www.amazon.in',
          match_type: 'SEARCH_FALLBACK',
          match_confidence: 0.6,
          source_status: 'VERIFIED',
          source_verified: true,
          availability: 'UNKNOWN',
          observed_at: '2026-09-03T21:00:00Z',
          is_lowest: false,
          price: null,
          external_image_url: null,
        },
        {
          id: 'off_fk_search',
          store_name: 'Flipkart',
          store_domain: 'flipkart.com',
          store_type: 'MARKETPLACE',
          external_url: 'https://www.flipkart.com/search?q=SpeedFlow+Marathon+Shoes',
          redirect_url: '/api/v1/external-offers/redirect?target=https://www.flipkart.com',
          match_type: 'SEARCH_FALLBACK',
          match_confidence: 0.6,
          source_status: 'VERIFIED',
          source_verified: true,
          availability: 'UNKNOWN',
          observed_at: '2026-09-03T21:00:00Z',
          is_lowest: false,
          price: null,
          external_image_url: null,
        }
      ],
      lowest_verified_price: 2999.0,
      lowest_store: 'Apex Store',
      lowest_verified_retailer: 'Apex Store',
      apex_difference: 0,
      apex_is_lowest: true,
      checked_sources: 1,
      checked_at: '2026-09-03T21:00:00Z',
      cache_status: 'LIVE',
      summary_text: 'Apex Store offers verified in-stock pricing at ₹2,999.00.',
    };

    const ui = getPriceComparisonUIState(mockData);

    // 1. Must NOT show "SAME PHYSICAL PRODUCT ACROSS VERIFIED STORES"
    assert.strictEqual(ui.hasMultipleVerifiedStores, false);
    assert.strictEqual(ui.headerBadgeText, 'CANONICAL PRODUCT VERIFIED');
    assert.strictEqual(ui.headerSupportingText, 'No verified external offers available for this product.');
    assert.strictEqual(ui.isHeaderEmerald, false);

    // 2. Lowest-price messaging must indicate Apex is the only verified source
    assert.strictEqual(ui.lowestPriceBannerTitle, 'Lowest verified price among checked sources');
    assert.strictEqual(ui.lowestPriceBannerDescription, 'Apex Store is the only verified source for this product.');
    assert.strictEqual(ui.lowestPriceBadgeText, 'Apex Verified Source');

    // 3. No verified external offers
    assert.strictEqual(ui.hasExternalVerifiedOffers, false);
    assert.strictEqual(ui.verifiedOffers.length, 0);
    assert.strictEqual(ui.fallbackOffers.length, 2);
  });

  // =========================================================================
  // SCENARIO B: Apex + One External Verified Product (2 Verified Stores)
  // =========================================================================
  test('Scenario B: Apex + 1 verified external retailer renders SAME PHYSICAL PRODUCT ACROSS VERIFIED STORES and retailer details', () => {
    const mockData: PriceComparisonResponse = {
      product_id: 'prod_nike_001',
      product_name: 'Sports Dry-Fit T-Shirt',
      product_brand: 'Nike',
      product_category: 'Apparel',
      product_image_url: 'https://images.unsplash.com/photo-1503342217505-b0a15ec3261c',
      apex_price: 999.0,
      apex_mrp: 1499.0,
      currency: 'INR',
      canonical_product: {
        canonical_product_id: 'canon_nike_drifit_legend_black_m',
        brand: 'Nike',
        title: "Nike Men's Dri-FIT Legend Short-Sleeve Training T-Shirt",
        category: 'Apparel',
        style_code: '718833-010',
        gtin: '00888407255169',
        variant: 'Classic Black',
        canonical_image_url: 'https://images.unsplash.com/photo-1503342217505-b0a15ec3261c',
        verified: true,
      },
      offers: [
        {
          id: 'off_nike_official',
          store_name: 'Nike Official Store',
          store_domain: 'nike.com',
          store_type: 'OFFICIAL_BRAND',
          external_url: 'https://www.nike.com/in/t/dri-fit-legend-training-t-shirt-1ZtbXq/718833-010',
          redirect_url: '/api/v1/external-offers/redirect?target=https://www.nike.com',
          price: 1095.0,
          mrp: 1095.0,
          currency: 'INR',
          difference_from_apex: 96.0,
          price_delta_label: '₹96 higher',
          match_type: 'VARIANT_EXACT',
          match_confidence: 1.0,
          source_status: 'VERIFIED',
          source_verified: true,
          availability: 'IN_STOCK',
          observed_at: '2026-09-03T21:30:00Z',
          is_lowest: false,
          external_product_id: '718833-010',
          external_product_title: "Nike Dri-FIT Legend Men's Training T-Shirt (Black/Matte Silver)",
          external_image_url: 'https://static.nike.com/a/images/t_PDP_1280_v1/f_auto,q_auto:eco/718833-010/dri-fit-legend-mens-training-t-shirt.png',
        },
        {
          id: 'off_amz_search',
          store_name: 'Amazon India',
          store_domain: 'amazon.in',
          store_type: 'MARKETPLACE',
          external_url: 'https://www.amazon.in/s?k=Nike+Dri-FIT+Legend+718833-010',
          redirect_url: '/api/v1/external-offers/redirect?target=https://www.amazon.in',
          match_type: 'SEARCH_FALLBACK',
          match_confidence: 0.6,
          source_status: 'VERIFIED',
          source_verified: true,
          availability: 'UNKNOWN',
          observed_at: '2026-09-03T21:30:00Z',
          is_lowest: false,
          price: null,
          external_image_url: null,
        }
      ],
      lowest_verified_price: 999.0,
      lowest_store: 'Apex Store',
      lowest_verified_retailer: 'Apex Store',
      apex_difference: 0,
      apex_is_lowest: true,
      checked_sources: 2,
      checked_at: '2026-09-03T21:30:00Z',
      cache_status: 'LIVE',
      summary_text: 'Apex Store has the lowest verified price at ₹999.00 among 2 checked stores.',
    };

    const ui = getPriceComparisonUIState(mockData);

    // 1. Must show "SAME PHYSICAL PRODUCT ACROSS VERIFIED STORES"
    assert.strictEqual(ui.hasMultipleVerifiedStores, true);
    assert.strictEqual(ui.headerBadgeText, 'SAME PHYSICAL PRODUCT ACROSS VERIFIED STORES');
    assert.strictEqual(ui.headerSupportingText, undefined);
    assert.strictEqual(ui.isHeaderEmerald, true);

    // 2. Lowest-price messaging uses comparison deal banner
    assert.strictEqual(ui.lowestPriceBannerTitle, 'Lowest Verified Deal');
    assert.strictEqual(ui.lowestPriceBadgeText, 'Best Price at Apex');

    // 3. Exactly 1 verified external offer and 1 fallback
    assert.strictEqual(ui.hasExternalVerifiedOffers, true);
    assert.strictEqual(ui.verifiedOffers.length, 1);
    assert.strictEqual(ui.fallbackOffers.length, 1);

    const nikeOffer = ui.verifiedOffers[0];
    assert.strictEqual(nikeOffer.store_name, 'Nike Official Store');
    assert.strictEqual(nikeOffer.price, 1095.0);
    assert.strictEqual(nikeOffer.match_confidence, 1.0);
    assert.strictEqual(nikeOffer.external_image_url?.includes('static.nike.com'), true);
    assert.strictEqual(nikeOffer.external_url.includes('718833-010'), true);
    assert.strictEqual(nikeOffer.observed_at, '2026-09-03T21:30:00Z');
  });

  // =========================================================================
  // SCENARIO C: Multiple External Verified Products (3+ Verified Stores)
  // =========================================================================
  test('Scenario C: Multiple external verified stores render all retailer offers with separate images, prices, and timestamps', () => {
    const mockData: PriceComparisonResponse = {
      product_id: 'prod_multi_001',
      product_name: 'Pro Running Shoes',
      product_brand: 'Nike',
      product_category: 'Running',
      product_image_url: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff',
      apex_price: 3499.0,
      apex_mrp: 4499.0,
      currency: 'INR',
      canonical_product: {
        canonical_product_id: 'canon_nike_revolution_6_black',
        brand: 'Nike',
        title: "Nike Revolution 6 Men's Road Running Shoes",
        category: 'Running',
        style_code: 'DC3728-003',
        gtin: '0195244584285',
        variant: 'Black/Iron Grey',
        canonical_image_url: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff',
        verified: true,
      },
      offers: [
        {
          id: 'off_nike_direct',
          store_name: 'Nike Official Store',
          store_domain: 'nike.com',
          store_type: 'OFFICIAL_BRAND',
          external_url: 'https://www.nike.com/in/t/revolution-6-road-running-shoes-NCvPsq/DC3728-003',
          redirect_url: '/api/v1/external-offers/redirect?target=https://www.nike.com',
          price: 3695.0,
          mrp: 3695.0,
          currency: 'INR',
          difference_from_apex: 196.0,
          price_delta_label: '₹196 higher',
          match_type: 'VARIANT_EXACT',
          match_confidence: 1.0,
          source_status: 'VERIFIED',
          source_verified: true,
          availability: 'IN_STOCK',
          observed_at: '2026-09-03T21:45:00Z',
          is_lowest: false,
          external_product_id: 'DC3728-003',
          external_product_title: "Nike Revolution 6 Men's Road Running Shoes",
          external_image_url: 'https://static.nike.com/a/images/t_PDP_1280_v1/f_auto,q_auto:eco/e777ecda-a948-4444-be1f-1eb728b9d81d/revolution-6-road-running-shoes-NCvPsq.png',
        },
        {
          id: 'off_authorized_partner',
          store_name: 'Superkicks India',
          store_domain: 'superkicks.in',
          store_type: 'RETAILER',
          external_url: 'https://www.superkicks.in/products/nike-revolution-6-dc3728-003',
          redirect_url: '/api/v1/external-offers/redirect?target=https://www.superkicks.in',
          price: 3599.0,
          mrp: 4495.0,
          currency: 'INR',
          difference_from_apex: 100.0,
          price_delta_label: '₹100 higher',
          match_type: 'EXACT',
          match_confidence: 0.98,
          source_status: 'VERIFIED',
          source_verified: true,
          availability: 'IN_STOCK',
          observed_at: '2026-09-03T21:40:00Z',
          is_lowest: false,
          external_product_id: 'SK-DC3728-003',
          external_product_title: 'Nike Revolution 6 Next Nature - Black',
          external_image_url: 'https://cdn.superkicks.in/products/dc3728-003-1.jpg',
        }
      ],
      lowest_verified_price: 3499.0,
      lowest_store: 'Apex Store',
      lowest_verified_retailer: 'Apex Store',
      apex_difference: 0,
      apex_is_lowest: true,
      checked_sources: 3,
      checked_at: '2026-09-03T21:45:00Z',
      cache_status: 'LIVE',
      summary_text: 'Apex Store has the lowest verified price at ₹3,499.00 among 3 checked stores.',
    };

    const ui = getPriceComparisonUIState(mockData);

    assert.strictEqual(ui.hasMultipleVerifiedStores, true);
    assert.strictEqual(ui.headerBadgeText, 'SAME PHYSICAL PRODUCT ACROSS VERIFIED STORES');
    assert.strictEqual(ui.verifiedOffers.length, 2);

    // Verify retailer 1
    assert.strictEqual(ui.verifiedOffers[0].store_name, 'Nike Official Store');
    assert.strictEqual(ui.verifiedOffers[0].price, 3695.0);
    assert.strictEqual(ui.verifiedOffers[0].match_confidence, 1.0);

    // Verify retailer 2
    assert.strictEqual(ui.verifiedOffers[1].store_name, 'Superkicks India');
    assert.strictEqual(ui.verifiedOffers[1].price, 3599.0);
    assert.strictEqual(ui.verifiedOffers[1].match_confidence, 0.98);
  });

  // =========================================================================
  // SCENARIO D: No Verified Source (Unverified / Generic Item)
  // =========================================================================
  test('Scenario D: Generic or unverified item renders CANONICAL PRODUCT VERIFIED fallback with no external verified offers', () => {
    const mockData: PriceComparisonResponse = {
      product_id: 'prod_generic_bottle_001',
      product_name: 'Insulated Stainless Steel Water Bottle',
      product_brand: 'Apex Sports',
      product_category: 'Accessories',
      product_image_url: 'https://images.unsplash.com/photo-1602143407151-7111542de6e8',
      apex_price: 699.0,
      apex_mrp: 999.0,
      currency: 'INR',
      canonical_product: {
        canonical_product_id: 'canon_milton_thermosteel_flip_750',
        brand: 'Apex Sports',
        title: 'Insulated Stainless Steel Water Bottle',
        category: 'Accessories',
        style_code: null,
        gtin: null,
        variant: 'Silver 750ml',
        canonical_image_url: 'https://images.unsplash.com/photo-1602143407151-7111542de6e8',
        verified: false,
      },
      offers: [],
      lowest_verified_price: 699.0,
      lowest_store: 'Apex Store',
      lowest_verified_retailer: 'Apex Store',
      apex_difference: 0,
      apex_is_lowest: true,
      checked_sources: 1,
      checked_at: '2026-09-03T21:50:00Z',
      cache_status: 'LIVE',
      summary_text: 'External price comparison unavailable for this product. Apex Store price is ₹699.00.',
    };

    const ui = getPriceComparisonUIState(mockData);

    assert.strictEqual(ui.hasMultipleVerifiedStores, false);
    assert.strictEqual(ui.headerBadgeText, 'CANONICAL PRODUCT VERIFIED');
    assert.strictEqual(ui.headerSupportingText, 'No verified external offers available for this product.');
    assert.strictEqual(ui.lowestPriceBannerTitle, 'Lowest verified price among checked sources');
    assert.strictEqual(ui.lowestPriceBannerDescription, 'Apex Store is the only verified source for this product.');
    assert.strictEqual(ui.verifiedOffers.length, 0);
    assert.strictEqual(ui.fallbackOffers.length, 0);
  });

});
