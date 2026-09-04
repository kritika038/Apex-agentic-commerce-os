import { test, describe } from 'node:test';
import assert from 'node:assert';
import { resolveCategoryFallback, generateFallbackSvgDataUri } from '../../../lib/images/categoryFallbacks.ts';

describe('Product Image Fallback & Integrity Tests', () => {

  test('1. Cookware and kitchen items resolve to cookware category fallback', () => {
    const meta1 = resolveCategoryFallback('Home & Kitchen', 'Cookware', 'Prestige Omega Deluxe Induction Fry Pan 24cm');
    assert.strictEqual(meta1.key, 'cookware');
    assert.strictEqual(meta1.icon, '🍳');
    assert.strictEqual(meta1.label, 'Kitchen & Cookware');

    const meta2 = resolveCategoryFallback('Home & Kitchen', 'Kitchen Appliances', 'Philips Juicer Mixer Grinder');
    assert.strictEqual(meta2.key, 'appliances');
    assert.strictEqual(meta2.label, 'Kitchen Appliances');
  });

  test('2. Jeans and denim items resolve to denim category fallback', () => {
    const meta = resolveCategoryFallback('Fashion', 'Jeans', "Levi's 511 Slim Fit Stretch Denim Jeans");
    assert.strictEqual(meta.key, 'jeans');
    assert.strictEqual(meta.icon, '👖');
    assert.strictEqual(meta.label, 'Denim & Jeans');
  });

  test('3. Running shoes and athletic sneakers resolve to shoes category fallback', () => {
    const meta1 = resolveCategoryFallback('Running', 'Running Shoes', 'Nike Air Zoom Pegasus 40');
    assert.strictEqual(meta1.key, 'shoes');
    assert.strictEqual(meta1.icon, '👟');

    const meta2 = resolveCategoryFallback('Sports & Fitness', 'Training Shoes', 'Puma Fuse 2.0');
    assert.strictEqual(meta2.key, 'shoes');
  });

  test('4. Watches and smartwatches resolve to watch category fallback', () => {
    const meta1 = resolveCategoryFallback('Fashion', 'Watches', 'Fossil Grant Chronograph Leather Watch');
    assert.strictEqual(meta1.key, 'watch');
    assert.strictEqual(meta1.icon, '⌚');

    const meta2 = resolveCategoryFallback('Electronics', 'Smart Watches', 'Apple Watch SE');
    assert.strictEqual(meta2.key, 'watch');
  });

  test('5. Sunglasses and eyewear resolve to eyewear category fallback', () => {
    const meta = resolveCategoryFallback('Fashion', 'Sunglasses', 'Ray-Ban Aviator Classic Polarized Sunglasses');
    assert.strictEqual(meta.key, 'eyewear');
    assert.strictEqual(meta.icon, '🕶️');
  });

  test('6. Audio and electronics resolve to electronics category fallback', () => {
    const meta = resolveCategoryFallback('Electronics', 'Earbuds', 'Sony WF-1000XM5');
    assert.strictEqual(meta.key, 'electronics');
    assert.strictEqual(meta.icon, '🎧');
  });

  test('7. Bags, luggage, and backpacks resolve to bag category fallback', () => {
    const meta = resolveCategoryFallback('Travel', 'Luggage', 'American Tourister Cabin Trolley');
    assert.strictEqual(meta.key, 'bag');
    assert.strictEqual(meta.icon, '🎒');
  });

  test('8. Fitness gear resolves to fitness category fallback', () => {
    const meta = resolveCategoryFallback('Sports & Fitness', 'Dumbbells', 'Decathlon Hex Dumbbells');
    assert.strictEqual(meta.key, 'fitness');
    assert.strictEqual(meta.icon, '🏋️');
  });

  test('9. Generated SVG Data URI is valid, non-empty, and decodable', () => {
    const uri = generateFallbackSvgDataUri('Fashion', 'Jeans', "Levi's 511");
    assert.strictEqual(uri.startsWith('data:image/svg+xml;utf8,'), true);
    const decoded = decodeURIComponent(uri.replace('data:image/svg+xml;utf8,', ''));
    assert.strictEqual(decoded.includes('<svg'), true);
    assert.strictEqual(decoded.includes('DENIM &amp; JEANS') || decoded.includes('DENIM & JEANS'), true);
    assert.strictEqual(decoded.includes('APEX VERIFIED CATALOG'), true);
  });

  test('10. Neutral fallback applies gracefully when category is unknown or undefined', () => {
    const meta = resolveCategoryFallback(undefined, undefined, undefined);
    assert.strictEqual(meta.key, 'generic');
    assert.strictEqual(meta.icon, '📦');
  });
});
