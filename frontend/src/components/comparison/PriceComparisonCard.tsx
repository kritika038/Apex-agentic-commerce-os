'use client';

import React, { useState, useEffect } from 'react';
import {
  SparklesIcon,
  ExternalLinkIcon
} from '@/components/ui/Icons';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { apiClient, API_BASE_URL } from '@/lib/api';
import { PriceComparisonResponse } from '@/lib/types/comparison';
import { getPriceComparisonUIState } from './comparisonUtils';

interface PriceComparisonCardProps {
  productId: string;
  onOpenFullModal?: () => void;
}

export function PriceComparisonCard({ productId, onOpenFullModal }: PriceComparisonCardProps) {
  const [data, setData] = useState<PriceComparisonResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const uiState = getPriceComparisonUIState(data);

  useEffect(() => {
    if (!productId) return;
    let isMounted = true;
    apiClient
      .get<PriceComparisonResponse>(`/price-comparison/${productId}`)
      .then((res) => {
        if (isMounted) setData(res.data);
      })
      .catch(() => {})
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [productId]);

  if (loading) {
    return (
      <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 animate-pulse space-y-2">
        <div className="h-4 bg-slate-200 rounded w-1/3" />
        <div className="h-8 bg-slate-200 rounded w-full" />
      </div>
    );
  }

  if (!data || data.offers.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-indigo-100 bg-indigo-50/20 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-indigo-600 text-white flex items-center justify-center shadow-2xs">
            <SparklesIcon className="w-3.5 h-3.5" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-900">
              {uiState.hasMultipleVerifiedStores ? 'AI Price Comparison' : 'AI Price Intelligence'}
            </h4>
            <p className="text-[11px] text-slate-500">
              {uiState.hasMultipleVerifiedStores
                ? `Compared across ${data.checked_sources} verified sources`
                : 'Canonical product verified • Apex Store'}
            </p>
          </div>
        </div>
        {onOpenFullModal && (
          <Button variant="outline" size="sm" onClick={onOpenFullModal} className="text-xs h-7 px-2.5">
            Full Breakdown
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
        {/* Apex Store */}
        <div className="p-2.5 rounded-lg bg-white border border-indigo-200 shadow-2xs">
          <div className="flex items-center justify-between text-[10px] text-slate-500 font-bold mb-1">
            <span>Apex Store</span>
            <Badge variant="purple" size="sm" className="text-[8px] py-0 px-1">
              Direct
            </Badge>
          </div>
          <p className="text-sm font-black font-mono text-slate-900">
            ₹{data.apex_price.toLocaleString('en-IN')}
          </p>
          <span className="text-[10px] text-emerald-700 font-medium">Free Delivery</span>
        </div>

        {/* Top External Offers */}
        {data.offers.slice(0, 3).map((offer) => (
          <button
            key={offer.id}
            type="button"
            onClick={(e) => {
              e.preventDefault();
              if (data?.product_id) {
                apiClient.post('/virtual-tryon/analytics', {
                  product_id: data.product_id,
                  event_type: 'EXTERNAL_OFFER_CLICK',
                  category: data.product_category,
                  latency_ms: 50
                }).catch(() => {});
              }
              if (offer.external_url && (offer.external_url.startsWith('https://') || offer.external_url.startsWith('http://'))) {
                window.open(offer.external_url, '_blank', 'noopener,noreferrer');
              } else {
                const backendUrl = `${API_BASE_URL}/external-offers/${offer.id}/redirect`;
                window.open(backendUrl, '_blank', 'noopener,noreferrer');
              }
            }}
            className="p-2.5 rounded-lg bg-white border border-slate-200 hover:border-slate-300 transition-colors shadow-2xs block text-left group cursor-pointer"
          >
            <div className="flex items-center justify-between text-[10px] text-slate-500 font-bold mb-1">
              <span className="truncate">{offer.store_name}</span>
              <ExternalLinkIcon className="w-3 h-3 text-slate-400 group-hover:text-indigo-600 transition-colors shrink-0" />
            </div>
            <p className="text-sm font-bold font-mono text-slate-900">
              {typeof offer.price === 'number' ? `₹${offer.price.toLocaleString('en-IN')}` : 'Price varies'}
            </p>
            <div className="flex items-center justify-between pt-1">
              <span
                className={`text-[10px] font-semibold ${
                  typeof offer.difference_from_apex === 'number' && offer.difference_from_apex < 0 ? 'text-emerald-700' : 'text-slate-500'
                }`}
              >
                {offer.price_delta_label || (typeof offer.price === 'number' ? 'Verified price' : 'Similar listing')}
              </span>
              <span className="text-[9px] font-bold text-indigo-600 group-hover:underline">
                {offer.action_label || (offer.link_type === 'SEARCH_FALLBACK' ? `Search →` : 'View product →')}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
