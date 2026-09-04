'use client';

import React from 'react';
import { Product, ProductCard } from './ProductCard';
import { ProductCardSkeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';
import { AlertTriangleIcon } from '@/components/ui/Icons';

export interface ProductGridProps {
  products: Product[];
  isLoading: boolean;
  onAddToCart: (product: Product) => void;
  onOpenPriceCheck?: (product: Product) => void;
  addingProductId: string | null;
  onResetFilters?: () => void;
  sortBy: 'featured' | 'price-low' | 'price-high' | 'stock';
  onSortChange: (sort: 'featured' | 'price-low' | 'price-high' | 'stock') => void;
  inStockOnly: boolean;
  onToggleInStock: (checked: boolean) => void;
  totalCount: number;
  apiError?: string | null;
  onRetry?: () => void;
}

export function ProductGrid({
  products,
  isLoading,
  onAddToCart,
  onOpenPriceCheck,
  addingProductId,
  onResetFilters,
  sortBy,
  onSortChange,
  inStockOnly,
  onToggleInStock,
  totalCount,
  apiError = null,
  onRetry,
}: ProductGridProps) {
  return (
    <section className="space-y-6">
      {/* Filtering & Sorting Controls Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 py-2 border-b border-slate-200">
        <div className="text-xs sm:text-sm text-slate-500 font-medium">
          Showing <span className="font-bold text-slate-900">{products.length}</span> of{' '}
          <span className="font-bold text-slate-900">{totalCount}</span> verified products
        </div>

        <div className="flex items-center gap-4 w-full sm:w-auto justify-between sm:justify-end">
          {/* In Stock Only Toggle */}
          <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-slate-700 select-none">
            <input
              type="checkbox"
              checked={inStockOnly}
              onChange={(e) => onToggleInStock(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span>In Stock Only</span>
          </label>

          {/* Sort Dropdown */}
          <div className="flex items-center gap-1.5 text-xs text-slate-700">
            <span className="text-slate-400 font-medium hidden sm:inline">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) =>
                onSortChange(
                  e.target.value as 'featured' | 'price-low' | 'price-high' | 'stock'
                )
              }
              className="bg-white border border-slate-200 text-slate-900 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer"
            >
              <option value="featured">Featured</option>
              <option value="price-low">Price: Low to High</option>
              <option value="price-high">Price: High to Low</option>
              <option value="stock">Availability</option>
            </select>
          </div>
        </div>
      </div>

      {/* Grid Display */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <ProductCardSkeleton key={i} />
          ))}
        </div>
      ) : apiError ? (
        <div className="rounded-2xl bg-white border border-rose-200 p-12 text-center max-w-md mx-auto space-y-4 shadow-xs">
          <div className="w-12 h-12 rounded-2xl bg-rose-50 mx-auto flex items-center justify-center text-rose-600">
            <AlertTriangleIcon size={24} />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-900">Unable to load the catalog</h3>
            <p className="text-xs text-slate-500">{apiError}</p>
          </div>
          {onRetry && (
            <Button onClick={onRetry} variant="primary" size="sm">
              Retry Loading Catalog
            </Button>
          )}
        </div>
      ) : products.length === 0 ? (
        <div className="rounded-2xl bg-white border border-slate-200 p-12 text-center max-w-md mx-auto space-y-4 shadow-xs">
          <div className="w-12 h-12 rounded-2xl bg-slate-100 mx-auto flex items-center justify-center text-xl text-slate-400">
            🔍
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-slate-900">No products match your criteria</h3>
            <p className="text-xs text-slate-500">
              Try adjusting your search query, selecting another category, or resetting filters.
            </p>
          </div>
          {onResetFilters && (
            <Button onClick={onResetFilters} variant="secondary" size="sm">
              Reset Filters
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onAddToCart={onAddToCart}
              onOpenPriceCheck={onOpenPriceCheck}
              isAdding={addingProductId === product.id}
            />
          ))}
        </div>
      )}
    </section>
  );
}
