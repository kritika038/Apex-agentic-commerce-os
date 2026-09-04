'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { resolveCategoryFallback, generateFallbackSvgDataUri } from '@/lib/images/categoryFallbacks';

// Global in-memory set to prevent duplicate console spam across component re-renders
const loggedFallbacks = new Set<string>();

export interface ProductImageProps extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'src'> {
  src?: string | null;
  alt: string;
  category?: string;
  subcategory?: string;
  productId?: string;
  productName?: string;
  containerClassName?: string;
  showCategoryBadge?: boolean;
  priority?: boolean;
  aspectRatio?: 'square' | 'video' | 'auto';
}

export function ProductImage({
  src,
  alt,
  category,
  subcategory,
  productId,
  productName,
  className = '',
  containerClassName = '',
  showCategoryBadge = false,
  priority = false,
  aspectRatio = 'square',
  ...props
}: ProductImageProps) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [hasError, setHasError] = useState(false);

  // Compute deterministic fallback based on category, subcategory and product identity
  const fallbackUri = useMemo(() => {
    return generateFallbackSvgDataUri(category, subcategory, productName || alt);
  }, [category, subcategory, productName, alt]);

  const fallbackMeta = useMemo(() => {
    return resolveCategoryFallback(category, subcategory, productName || alt);
  }, [category, subcategory, productName, alt]);

  // Determine actual image source
  const validOriginalSrc = typeof src === 'string' && src.trim().length > 0 && (src.startsWith('http://') || src.startsWith('https://') || src.startsWith('/') || src.startsWith('data:'));
  
  const effectiveSrc = useMemo(() => {
    if (hasError || !validOriginalSrc) {
      return fallbackUri;
    }
    return src!;
  }, [hasError, validOriginalSrc, src, fallbackUri]);

  // Reset error state when incoming original src changes
  useEffect(() => {
    setHasError(false);
    setIsLoaded(false);
  }, [src]);

  const handleError = () => {
    if (!hasError) {
      setHasError(true);
      setIsLoaded(true);

      // Deduplicated diagnostic logging in development mode
      if (process.env.NODE_ENV !== 'production') {
        const logKey = `${productId || 'unknown'}_${src || 'empty'}`;
        if (!loggedFallbacks.has(logKey)) {
          loggedFallbacks.add(logKey);
          console.warn('[PRODUCT_IMAGE_FALLBACK]', {
            product_id: productId || 'unknown',
            product_name: productName || alt,
            original_url: src || null,
            fallback_category: fallbackMeta.key,
            fallback_label: fallbackMeta.label,
            timestamp: new Date().toISOString(),
          });
        }
      }
    }
  };

  const handleLoad = () => {
    setIsLoaded(true);
  };

  const aspectClass =
    aspectRatio === 'square'
      ? 'aspect-square'
      : aspectRatio === 'video'
      ? 'aspect-video'
      : '';

  return (
    <div
      className={`relative overflow-hidden flex items-center justify-center bg-slate-100 ${aspectClass} ${containerClassName}`}
    >
      {/* Loading Skeleton */}
      {!isLoaded && (
        <div className="absolute inset-0 bg-slate-200/80 animate-pulse flex items-center justify-center z-10">
          <div className="w-8 h-8 rounded-full border-2 border-slate-300 border-t-indigo-500 animate-spin opacity-40" />
        </div>
      )}

      {/* Product Image Element */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={effectiveSrc}
        alt={alt}
        loading={priority ? 'eager' : 'lazy'}
        decoding="async"
        onLoad={handleLoad}
        onError={handleError}
        className={`w-full h-full object-cover object-center transition-opacity duration-300 ${
          isLoaded ? 'opacity-100' : 'opacity-0'
        } ${className}`}
        {...props}
      />

      {/* Optional Category Fallback Badge if fallback is active */}
      {showCategoryBadge && hasError && (
        <div className="absolute bottom-2 left-2 z-20">
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-900/80 text-white backdrop-blur-xs border border-slate-700/60 shadow-xs">
            {fallbackMeta.label}
          </span>
        </div>
      )}
    </div>
  );
}
export default ProductImage;
