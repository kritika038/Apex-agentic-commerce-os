'use client';

import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { PlusIcon } from '@/components/ui/Icons';
import { ProductImage } from '@/components/ui/ProductImage';

export interface Product {
  id: string;
  name: string;
  brand?: string;
  category: string;
  subcategory?: string;
  price: number;
  mrp?: number;
  currency?: string;
  description?: string;
  stock_quantity?: number;
  image_url?: string;
  rating?: number;
  review_count?: number;
  lowest_market_price?: number | null;
  external_stores_count?: number;
  why_this_rationale?: string[];
  ranking_score?: number;
}

export interface ProductCardProps {
  product: Product;
  onAddToCart: (product: Product) => void;
  onOpenPriceCheck?: (product: Product) => void;
  isAdding?: boolean;
}

export function ProductCard({ product, onAddToCart, onOpenPriceCheck, isAdding = false }: ProductCardProps) {
  const isOutOfStock = (product.stock_quantity ?? 0) <= 0;

  const discountPercent =
    product.mrp && product.mrp > product.price
      ? Math.round(((product.mrp - product.price) / product.mrp) * 100)
      : null;

  return (
    <div className="group bg-white rounded-2xl border border-slate-200 overflow-hidden flex flex-col justify-between hover:shadow-md hover:border-slate-300 transition-all duration-200">
      {/* Product Image Box */}
      <Link href={`/shopping/${product.id}`} className="block relative aspect-square w-full bg-slate-50 overflow-hidden border-b border-slate-100 flex items-center justify-center cursor-pointer">
        <ProductImage
          src={product.image_url}
          alt={product.name}
          productId={product.id}
          productName={product.name}
          category={product.category}
          subcategory={product.subcategory}
          className="w-full h-full object-cover object-center group-hover:scale-105 transition-transform duration-300"
          containerClassName="w-full h-full"
        />

        {/* Top Badges */}
        <div className="absolute top-2.5 left-2.5 flex flex-col gap-1 items-start">
          <span className="px-2 py-0.5 rounded-md bg-white/95 backdrop-blur-xs text-[10px] font-bold uppercase tracking-wider text-slate-700 shadow-2xs border border-slate-200/60">
            {product.brand || product.category}
          </span>
          {discountPercent && (
            <span className="px-1.5 py-0.5 rounded-md bg-emerald-600 text-white text-[9px] font-bold shadow-2xs">
              {discountPercent}% OFF
            </span>
          )}
        </div>

        <div className="absolute top-2.5 right-2.5">
          <Badge variant={isOutOfStock ? 'error' : 'success'} size="xs" dot={!isOutOfStock}>
            {isOutOfStock ? 'Out of Stock' : `${product.stock_quantity ?? 10} in stock`}
          </Badge>
        </div>
      </Link>

      {/* Product Content Details */}
      <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
        <div className="space-y-1">
          {/* Rating */}
          <div className="flex items-center gap-1.5 text-xs text-amber-500 font-bold">
            <span>★ {product.rating ?? 4.5}</span>
            <span className="text-slate-400 font-normal">({product.review_count ?? 120})</span>
          </div>

          <Link href={`/shopping/${product.id}`} className="block">
            <h3 className="font-bold text-sm text-slate-900 leading-snug line-clamp-1 group-hover:text-indigo-600 transition-colors">
              {product.name}
            </h3>
          </Link>
          {product.description && (
            <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
              {product.description}
            </p>
          )}
        </div>

        {/* Price & External Price Teaser */}
        <div className="space-y-2 pt-2 border-t border-slate-100">
          <div className="flex items-baseline justify-between">
            <div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-base sm:text-lg font-black font-mono text-slate-900">
                  ₹{Number(product.price).toLocaleString('en-IN')}
                </span>
                {product.mrp && product.mrp > product.price && (
                  <span className="text-xs font-mono text-slate-400 line-through">
                    ₹{Number(product.mrp).toLocaleString('en-IN')}
                  </span>
                )}
              </div>
            </div>

            {/* Quick Price Check Button */}
            {onOpenPriceCheck && (
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onOpenPriceCheck(product);
                }}
                className="inline-flex items-center gap-1 text-[11px] font-bold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 px-2 py-1 rounded-lg border border-indigo-200 transition-colors cursor-pointer"
              >
                <span>AI Price Check</span>
              </button>
            )}
          </div>

          {/* Add to Cart Button */}
          <Button
            onClick={() => onAddToCart(product)}
            disabled={isOutOfStock || isAdding}
            isLoading={isAdding}
            variant={isOutOfStock ? 'outline' : 'primary'}
            size="sm"
            className="w-full rounded-xl font-semibold bg-slate-900 hover:bg-slate-800 text-white"
            leftIcon={!isOutOfStock && !isAdding ? <PlusIcon size={14} /> : undefined}
          >
            {isOutOfStock ? 'Out of Stock' : 'Add to Cart'}
          </Button>
        </div>
      </div>
    </div>
  );
}
