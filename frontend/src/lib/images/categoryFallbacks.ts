/**
 * Category-specific fallback image system for Apex Storefront.
 * Provides deterministic, high-fidelity SVGs tailored to product category and subcategory.
 * Ensures zero external network requests and 100% reliable fallback presentation.
 */

export interface FallbackCategoryMetadata {
  key: string;
  label: string;
  icon: string;
  gradientStart: string;
  gradientEnd: string;
  accentColor: string;
  svgPath: string;
}

// Crisp SVG icon paths for each retail category
const SVG_ICONS: Record<string, { path: string; viewBox?: string }> = {
  // Athletic Footwear & Running Shoes
  shoes: {
    path: 'M2 17c0-2.5 2-4.5 4.5-4.5h2.5l3.5-5.5c1-1.5 2.5-2.5 4.5-2.5h3c1.5 0 2.5 1 2.5 2.5v2.5c0 1-.5 2-1.5 2.5l-2.5 1.5H19c2 0 3.5 1.5 3.5 3.5v2c0 .5-.5 1-1 1H3c-.5 0-1-.5-1-1v-2zm4.5-2.5c-1.4 0-2.5 1.1-2.5 2.5h14c0-1.4-1.1-2.5-2.5-2.5h-9z',
  },
  // Jeans & Denim
  jeans: {
    path: 'M6 2h12l1 18-4.5 2-2.5-9-2.5 9L5 20 6 2zm3 4h6v2H9V6zm1 4h4l.5 6-1.5-6h-2l-1.5 6 .5-6z',
  },
  // T-Shirts & Apparel Tops
  tshirt: {
    path: 'M20.38 3.46L16 2a4 4 0 01-8 0L3.62 3.46a2 2 0 00-1.34 2.23l.58 3.47a2 2 0 001.23 1.53L6 11.43V20a2 2 0 002 2h8a2 2 0 002-2v-8.57l1.91-.74a2 2 0 001.23-1.53l.58-3.47a2 2 0 00-1.34-2.23z',
  },
  // Jackets & Outerwear
  jacket: {
    path: 'M12 2l4 2 5 3-2 5-3-1v11H8V11L5 12l-2-5 5-3 4-2zm0 2.5L9.5 6 12 8.5 14.5 6 12 4.5zM11 11v9h2v-9h-2z',
  },
  // Backpacks & Bags
  bag: {
    path: 'M6 8V6a4 4 0 018 0v2h4a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V10a2 2 0 012-2h2zm2-2a2 2 0 014 0v2H8V6zm-2 6v6h12v-6H6zm3 2h6v2H9v-2z',
  },
  // Watches & Smartwatches
  watch: {
    path: 'M12 2a4 4 0 00-4 4v1.1A8 8 0 004 14a8 8 0 004 6.9V22a4 4 0 004 4 4 4 0 004-4v-1.1a8 8 0 004-6.9 8 8 0 00-4-6.9V6a4 4 0 00-4-4zm0 6a6 6 0 110 12 6 6 0 010-12zm-1 3v3.5l2.5 1.5.8-1.3-1.8-1.1V11h-1.5z',
  },
  // Sunglasses & Eyewear
  eyewear: {
    path: 'M2 12c0-2.2 1.8-4 4-4h2c1.7 0 3.1 1 3.7 2.5.6-.9 1.6-1.5 2.8-1.5h1.5c2.2 0 4 1.8 4 4v1c0 2.8-2.2 5-5 5H14c-2.2 0-4-1.8-4-4v-.5c-.5-.9-1.4-1.5-2.5-1.5H6c-2.2 0-4 1.8-4 4v-1zm4-2c-1.1 0-2 .9-2 2s.9 2 2 2h1.5c1.1 0 2-.9 2-2s-.9-2-2-2H6zm10 0c-1.1 0-2 .9-2 2s.9 2 2 2h1c1.7 0 3-1.3 3-3s-1.3-1-3-1h-1z',
  },
  // Cookware, Pots & Pans
  cookware: {
    path: 'M19 11h-1V9a2 2 0 00-2-2H8a2 2 0 00-2 2v2H5a3 3 0 00-3 3v2a3 3 0 003 3h1.1A7 7 0 0013 22h1a7 7 0 006.9-6H21a3 3 0 003-3v-2a3 3 0 00-3-3h-2zm-11-2h8v2H8V9zm11 5a1 1 0 01-1 1h-2a5 5 0 01-4.9 4H13a5 5 0 01-4.9-4H6a1 1 0 01-1-1v-2a1 1 0 011-1h12a1 1 0 011 1v2z',
  },
  // Kitchen Appliances & Blenders
  appliances: {
    path: 'M6 2h12l-1.5 12h-9L6 2zm2 14h8v6H8v-6zm3-10h2v4h-2V6zm0 12h2v2h-2v-2z',
  },
  // Bottles, Shakers & Tumblers
  bottle: {
    path: 'M9 2h6v2h-1v2.1A6 6 0 0118 11v9a2 2 0 01-2 2H8a2 2 0 01-2-2v-9a6 6 0 014-4.9V4H9V2zm2 4.9V4h2v2.9A4 4 0 0011 6.9zM8 11a4 4 0 00-2 3.5V20h12v-5.5a4 4 0 00-2-3.5H8zm2 3h4v2h-4v-2z',
  },
  // Fitness Equipment & Dumbbells
  fitness: {
    path: 'M4 8H2v8h2v-2h2v-4H4V8zm16 0h-2v2h-2v4h2v2h2V8zm-6 3H10v2h4v-2zM8 9h2v6H8V9zm6 0h2v6h-2V9z',
  },
  // Electronics, Headphones & Audio
  electronics: {
    path: 'M12 3a9 9 0 00-9 9v7a3 3 0 003 3h1a2 2 0 002-2v-5a2 2 0 00-2-2H5v-1a7 7 0 1114 0v1h-2a2 2 0 00-2 2v5a2 2 0 002 2h1a3 3 0 003-3v-7a9 9 0 00-9-9z',
  },
  // Beauty, Grooming & Skincare
  beauty: {
    path: 'M9 3h6v4H9V3zm-2 6h10v11a2 2 0 01-2 2H9a2 2 0 01-2-2V9zm3 3v6h4v-6h-4z',
  },
  // Accessories & General Gear
  accessories: {
    path: 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z',
  },
  // Generic Store Item
  generic: {
    path: 'M20 6h-4V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V8a2 2 0 00-2-2zM10 4h4v2h-4V4zm10 16H4V8h16v12z',
  },
};

/**
 * Maps category and subcategory strings deterministically to a fallback configuration.
 */
export function resolveCategoryFallback(category?: string, subcategory?: string, productName?: string): FallbackCategoryMetadata {
  const cat = (category || '').trim().toLowerCase();
  const sub = (subcategory || '').trim().toLowerCase();
  const name = (productName || '').trim().toLowerCase();

  // 1. Cookware & Kitchen
  if (
    cat.includes('kitchen') ||
    cat.includes('cookware') ||
    sub.includes('cookware') ||
    sub.includes('pan') ||
    sub.includes('pot') ||
    sub.includes('casserole') ||
    name.includes('fry pan') ||
    name.includes('induction') ||
    name.includes('cookware') ||
    name.includes('prestige')
  ) {
    if (sub.includes('appliances') || name.includes('grinder') || name.includes('juicer') || name.includes('mixer')) {
      return {
        key: 'appliances',
        label: 'Kitchen Appliances',
        icon: '🍳',
        gradientStart: '#1e293b',
        gradientEnd: '#0f172a',
        accentColor: '#f97316',
        svgPath: SVG_ICONS.appliances.path,
      };
    }
    return {
      key: 'cookware',
      label: 'Kitchen & Cookware',
      icon: '🍳',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#f59e0b',
      svgPath: SVG_ICONS.cookware.path,
    };
  }

  // 2. Jeans & Denim
  if (sub.includes('jean') || name.includes('jean') || name.includes('511') || name.includes('denim')) {
    return {
      key: 'jeans',
      label: 'Denim & Jeans',
      icon: '👖',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#38bdf8',
      svgPath: SVG_ICONS.jeans.path,
    };
  }

  // 3. Footwear / Running Shoes / Sneakers
  if (
    cat.includes('running') ||
    cat.includes('footwear') ||
    sub.includes('shoe') ||
    sub.includes('sneaker') ||
    sub.includes('cleat') ||
    sub.includes('spike') ||
    name.includes('shoe') ||
    name.includes('sneaker') ||
    name.includes('pegasus') ||
    name.includes('ultraboost')
  ) {
    return {
      key: 'shoes',
      label: 'Athletic Footwear',
      icon: '👟',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#10b981',
      svgPath: SVG_ICONS.shoes.path,
    };
  }

  // 4. Jackets & Outerwear
  if (sub.includes('jacket') || sub.includes('windbreaker') || name.includes('jacket') || name.includes('hooded') || name.includes('windbreaker')) {
    return {
      key: 'jacket',
      label: 'Jackets & Outerwear',
      icon: '🧥',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#6366f1',
      svgPath: SVG_ICONS.jacket.path,
    };
  }

  // 5. T-Shirts & Tops
  if (sub.includes('t-shirt') || sub.includes('shirt') || sub.includes('top') || name.includes('tee') || name.includes('t-shirt') || name.includes('dry-fit')) {
    return {
      key: 'tshirt',
      label: 'Apparel & Tees',
      icon: '👕',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#6366f1',
      svgPath: SVG_ICONS.tshirt.path,
    };
  }

  // 6. Watches & Wearables
  if (sub.includes('watch') || name.includes('watch') || name.includes('chronograph') || name.includes('smartwatch')) {
    return {
      key: 'watch',
      label: 'Watches & Wearables',
      icon: '⌚',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#ec4899',
      svgPath: SVG_ICONS.watch.path,
    };
  }

  // 7. Eyewear & Sunglasses
  if (sub.includes('sunglass') || sub.includes('eyewear') || name.includes('aviator') || name.includes('sunglass') || name.includes('ray-ban')) {
    return {
      key: 'eyewear',
      label: 'Eyewear & Sunglasses',
      icon: '🕶️',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#eab308',
      svgPath: SVG_ICONS.eyewear.path,
    };
  }

  // 8. Bottles, Drinkware & Tumblers
  if (sub.includes('bottle') || sub.includes('shaker') || sub.includes('mug') || sub.includes('tumbler') || name.includes('shaker') || name.includes('tumbler') || name.includes('bottle')) {
    return {
      key: 'bottle',
      label: 'Bottles & Drinkware',
      icon: '🥤',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#06b6d4',
      svgPath: SVG_ICONS.bottle.path,
    };
  }

  // 9. Bags, Backpacks & Luggage
  if (cat.includes('bag') || cat.includes('travel') || sub.includes('bag') || sub.includes('backpack') || sub.includes('luggage') || sub.includes('trolley') || name.includes('backpack') || name.includes('duffle') || name.includes('trolley')) {
    return {
      key: 'bag',
      label: 'Bags & Luggage',
      icon: '🎒',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#8b5cf6',
      svgPath: SVG_ICONS.bag.path,
    };
  }

  // 10. Fitness Equipment & Training Gear
  if (
    cat.includes('fitness') ||
    sub.includes('dumbbell') ||
    sub.includes('kettlebell') ||
    sub.includes('mat') ||
    sub.includes('band') ||
    sub.includes('rope') ||
    sub.includes('glove') ||
    name.includes('yoga') ||
    name.includes('dumbbell') ||
    name.includes('kettlebell') ||
    name.includes('resistance')
  ) {
    return {
      key: 'fitness',
      label: 'Fitness Equipment',
      icon: '🏋️',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#10b981',
      svgPath: SVG_ICONS.fitness.path,
    };
  }

  // 11. Electronics & Audio
  if (
    cat.includes('electronics') ||
    sub.includes('earbud') ||
    sub.includes('headphone') ||
    sub.includes('speaker') ||
    sub.includes('keyboard') ||
    sub.includes('mouse') ||
    sub.includes('monitor') ||
    sub.includes('power bank') ||
    name.includes('earbuds') ||
    name.includes('headphones') ||
    name.includes('speaker') ||
    name.includes('keyboard') ||
    name.includes('power bank')
  ) {
    return {
      key: 'electronics',
      label: 'Electronics & Audio',
      icon: '🎧',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#3b82f6',
      svgPath: SVG_ICONS.electronics.path,
    };
  }

  // 12. Beauty, Grooming & Skincare
  if (
    cat.includes('beauty') ||
    cat.includes('personal') ||
    sub.includes('grooming') ||
    sub.includes('skincare') ||
    sub.includes('haircare') ||
    name.includes('trimmer') ||
    name.includes('shaver') ||
    name.includes('moisturizer') ||
    name.includes('dryer')
  ) {
    return {
      key: 'beauty',
      label: 'Grooming & Skincare',
      icon: '✨',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#f43f5e',
      svgPath: SVG_ICONS.beauty.path,
    };
  }

  // 13. Apparel General (Catch-all for clothing like Shorts, Track Pants, Sports Bras)
  if (cat.includes('apparel') || cat.includes('fashion') || sub.includes('pant') || sub.includes('short') || sub.includes('bra')) {
    return {
      key: 'tshirt',
      label: 'Apparel & Activewear',
      icon: '👕',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#6366f1',
      svgPath: SVG_ICONS.tshirt.path,
    };
  }

  // 14. Accessories
  if (cat.includes('accessories') || sub.includes('sock') || name.includes('sock')) {
    return {
      key: 'accessories',
      label: 'Accessories & Gear',
      icon: '🧦',
      gradientStart: '#1e293b',
      gradientEnd: '#0f172a',
      accentColor: '#14b8a6',
      svgPath: SVG_ICONS.accessories.path,
    };
  }

  // Generic fallback
  return {
    key: 'generic',
    label: category || 'Apex Store Product',
    icon: '📦',
    gradientStart: '#1e293b',
    gradientEnd: '#0f172a',
    accentColor: '#94a3b8',
    svgPath: SVG_ICONS.generic.path,
  };
}

/**
 * Generates an ultra-lightweight, crisp SVG data URI for pure offline/zero-dependency rendering.
 */
export function generateFallbackSvgDataUri(category?: string, subcategory?: string, productName?: string): string {
  const meta = resolveCategoryFallback(category, subcategory, productName);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="${meta.gradientStart}" />
      <stop offset="100%" stop-color="${meta.gradientEnd}" />
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="${meta.accentColor}" stop-opacity="0.25" />
      <stop offset="100%" stop-color="${meta.accentColor}" stop-opacity="0.05" />
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)" />
  <circle cx="200" cy="180" r="100" fill="url(#glow)" />
  <circle cx="200" cy="180" r="80" stroke="${meta.accentColor}" stroke-opacity="0.3" stroke-width="1.5" fill="none" stroke-dasharray="4 4" />
  <g transform="translate(160, 140) scale(3.33)" fill="${meta.accentColor}">
    <path d="${meta.svgPath}" />
  </g>
  <text x="200" y="310" text-anchor="middle" fill="#f8fafc" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="700" letter-spacing="0.5">${meta.label.toUpperCase()}</text>
  <text x="200" y="332" text-anchor="middle" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="500">APEX VERIFIED CATALOG</text>
</svg>`;

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}
