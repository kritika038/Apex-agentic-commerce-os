'use client';

import React, { useState, useEffect } from 'react';
import {
  XIcon,
  SparklesIcon,
  ShieldCheckIcon,
  CheckCircle2Icon,
  TrendingDownIcon,
  ClockIcon,
  TagIcon,
  AlertTriangleIcon
} from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { apiClient, extractErrorMessage } from '@/lib/api';
import { PriceComparisonResponse, PriceHistoryResponse } from '@/lib/types/comparison';
import { getPriceComparisonUIState } from './comparisonUtils';
import { ProductImage } from '@/components/ui/ProductImage';

interface PriceComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
  productId: string | null;
  onBuyOnApex?: (productId: string) => void;
}

export function PriceComparisonModal({
  isOpen,
  onClose,
  productId,
  onBuyOnApex
}: PriceComparisonModalProps) {
  const [data, setData] = useState<PriceComparisonResponse | null>(null);
  const [history, setHistory] = useState<PriceHistoryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'comparison' | 'history'>('comparison');

  const uiState = getPriceComparisonUIState(data);

  useEffect(() => {
    if (!isOpen || !productId) {
      setData(null);
      setHistory(null);
      return;
    }

    const fetchComparison = async () => {
      setLoading(true);
      setError(null);
      try {
        const [compRes, histRes] = await Promise.all([
          apiClient.get<PriceComparisonResponse>(`/price-comparison/${productId}`),
          apiClient.get<PriceHistoryResponse>(`/price-comparison/${productId}/history`).catch(() => ({ data: null }))
        ]);
        setData(compRes.data);
        if (histRes && histRes.data) {
          setHistory(histRes.data);
        }
      } catch (err: unknown) {
        setError(extractErrorMessage(err, 'Failed to fetch external price comparison.'));
      } finally {
        setLoading(false);
      }
    };

    fetchComparison();
  }, [isOpen, productId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs">
              <SparklesIcon className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900">AI Price Check</h2>
                <Badge variant={uiState.hasMultipleVerifiedStores ? 'purple' : 'neutral'} size="sm" className="font-mono text-[10px]">
                  {uiState.hasMultipleVerifiedStores ? 'Multi-Store Intelligence' : 'Catalog Intelligence'}
                </Badge>
              </div>
              <p className="text-xs text-slate-500">
                {uiState.hasMultipleVerifiedStores
                  ? 'Lowest verified price among checked stores'
                  : 'Lowest verified price among checked sources • Apex Store'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-200/60 transition-colors"
          >
            <XIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 px-6 bg-white gap-6 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('comparison')}
            className={`py-3 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'comparison'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <TagIcon className="w-3.5 h-3.5" />
            Live Store Offers ({data ? (uiState.hasMultipleVerifiedStores ? data.checked_sources : 1) : '...'})
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`py-3 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'history'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <ClockIcon className="w-3.5 h-3.5" />
            Observed Price History
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5">
          {loading ? (
            <div className="py-16 text-center space-y-3">
              <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-sm text-slate-500 font-medium">Scanning verified retailers and official sources...</p>
              <p className="text-xs text-slate-400">Comparing Amazon India, Flipkart, Myntra, and Official Stores</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-sm flex items-start gap-3">
              <AlertTriangleIcon className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Price Check Notice</p>
                <p className="text-xs text-amber-700 mt-0.5">{error}</p>
              </div>
            </div>
          ) : data ? (
            activeTab === 'comparison' ? (
              <>
                {/* Buyhatke-style Canonical Product Header */}
                <div className="p-4 rounded-xl bg-slate-900 text-white shadow-sm space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    <span>AI Price Intelligence</span>
                    {uiState.hasMultipleVerifiedStores ? (
                      <span className="text-emerald-400 flex items-center gap-1">
                        <CheckCircle2Icon className="w-3.5 h-3.5" />
                        SAME PHYSICAL PRODUCT ACROSS VERIFIED STORES
                      </span>
                    ) : (
                      <div className="flex flex-col items-start sm:items-end">
                        <span className="text-indigo-400 flex items-center gap-1">
                          <CheckCircle2Icon className="w-3.5 h-3.5" />
                          CANONICAL PRODUCT VERIFIED
                        </span>
                        <span className="text-[10px] text-slate-400 normal-case font-normal mt-0.5">
                          No verified external offers available for this product.
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-3.5">
                    <ProductImage
                      src={data.product_image_url}
                      alt={data.product_name}
                      productName={data.product_name}
                      category={data.canonical_product?.category}
                      className="w-16 h-16 rounded-lg object-contain bg-white p-1 border border-slate-700 shrink-0"
                      containerClassName="w-16 h-16 rounded-lg shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">
                          {data.canonical_product?.brand || data.product_brand || 'Apex'}
                        </span>
                        {data.canonical_product?.style_code && (
                          <span className="text-[10px] font-mono bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">
                            Style: {data.canonical_product.style_code}
                          </span>
                        )}
                        {data.canonical_product?.gtin && (
                          <span className="text-[10px] font-mono bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">
                            GTIN: {data.canonical_product.gtin}
                          </span>
                        )}
                      </div>
                      <h3 className="text-base font-black text-white truncate mt-0.5">
                        {data.canonical_product?.title || data.product_name}
                      </h3>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Selected Variant: <span className="font-semibold text-slate-200">{data.canonical_product?.variant || 'Standard'}</span> • Apex Price: <span className="font-bold text-white">₹{data.apex_price.toLocaleString('en-IN')}</span>
                      </p>
                    </div>
                  </div>
                </div>

                {/* Lowest Price Banner */}
                <div className={`p-4 rounded-xl border flex items-center justify-between ${
                  uiState.hasMultipleVerifiedStores
                    ? (data.apex_is_lowest ? 'bg-emerald-50 border-emerald-200 text-emerald-950' : 'bg-indigo-50 border-indigo-200 text-indigo-950')
                    : 'bg-slate-50 border-slate-200 text-slate-900'
                }`}>
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1.5">
                      <TrendingDownIcon className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                        {uiState.lowestPriceBannerTitle}
                      </span>
                    </div>
                    <p className="text-lg font-black font-mono">
                      ₹{data.lowest_verified_price.toLocaleString('en-IN')}
                      <span className="text-xs font-semibold text-slate-600 ml-2">on {data.lowest_store}</span>
                    </p>
                    <p className="text-xs text-slate-600 font-medium">
                      {uiState.lowestPriceBannerDescription}
                    </p>
                  </div>
                  <Badge variant={uiState.hasMultipleVerifiedStores ? (data.apex_is_lowest ? 'success' : 'purple') : 'neutral'} size="md">
                    {uiState.lowestPriceBadgeText}
                  </Badge>
                </div>

                {/* Comparison Table / List */}
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between text-xs font-bold text-slate-500 px-1">
                    <span>STORE / PLATFORM</span>
                    <span>PRICE & ACTION</span>
                  </div>

                  {/* Apex Store Row */}
                  <div className="p-3.5 rounded-xl border-2 border-indigo-500/40 bg-indigo-50/30 flex items-center justify-between gap-3 shadow-xs">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-black text-xs">
                        AX
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-slate-900">Apex Store</span>
                          <Badge variant="purple" size="sm" className="text-[10px]">
                            Direct Checkout
                          </Badge>
                        </div>
                        <p className="text-[11px] text-slate-500">
                          Razorpay Test Mode • Autonomous Governance
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className="text-base font-black font-mono text-slate-900">
                          ₹{data.apex_price.toLocaleString('en-IN')}
                        </p>
                        <span className="text-[10px] text-emerald-700 font-semibold">
                          Verified Official Catalog
                        </span>
                      </div>
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => {
                          onBuyOnApex?.(data.product_id);
                          onClose();
                        }}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs text-xs px-3 py-1.5"
                      >
                        Buy on Apex
                      </Button>
                    </div>
                  </div>

                  {/* Partitioned Offers */}
                  {(() => {
                    const verifiedOffers = uiState.verifiedOffers;
                    const fallbackOffers = uiState.fallbackOffers;

                    return (
                      <>
                        {/* 1. Verified Exact Store Listings */}
                        {verifiedOffers.length > 0 && (
                          <div className="space-y-2 pt-2">
                            <div className="flex items-center justify-between text-xs font-bold text-slate-700 px-1">
                              <span className="flex items-center gap-1.5 text-emerald-700 font-bold uppercase tracking-wider text-[11px]">
                                <CheckCircle2Icon className="w-3.5 h-3.5" />
                                Compare prices across stores — Same physical product
                              </span>
                              <span className="text-[10px] text-slate-400 font-normal">Authentic Retailer Imagery & Direct PDPs</span>
                            </div>

                            {verifiedOffers.map((offer) => {
                              const isVariantExact = offer.match_type === 'VARIANT_EXACT';
                              const isCheaper = typeof offer.difference_from_apex === 'number' && offer.difference_from_apex < 0;

                              return (
                                <div
                                  key={offer.id}
                                  className="p-4 rounded-2xl border-2 border-emerald-200/80 bg-white hover:border-emerald-300 hover:shadow-md transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
                                >
                                  {/* Left: Prominent Product Image & Retailer Metadata */}
                                  <div className="flex items-center gap-4 min-w-0 flex-1">
                                    {offer.external_image_url ? (
                                      <div className="relative shrink-0 w-28 h-28 sm:w-32 sm:h-32 rounded-xl bg-slate-50 border border-slate-200 p-2 flex items-center justify-center shadow-2xs group">
                                        <ProductImage
                                          src={offer.external_image_url}
                                          alt={offer.external_product_title || offer.store_name}
                                          productName={offer.external_product_title || data?.product_name}
                                          category={data?.canonical_product?.category}
                                          className="w-full h-full object-contain mix-blend-multiply"
                                          containerClassName="w-full h-full bg-transparent"
                                        />
                                        {offer.store_logo_url && (
                                          <div className="absolute -bottom-1.5 -right-1.5 bg-white rounded-full p-1 border border-slate-200 shadow-xs">
                                            <img
                                              src={offer.store_logo_url}
                                              alt={offer.store_name}
                                              className="w-5 h-5 object-contain"
                                            />
                                          </div>
                                        )}
                                      </div>
                                    ) : (
                                      <div className="w-28 h-28 sm:w-32 sm:h-32 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 font-bold text-sm shrink-0">
                                        {offer.store_name.slice(0, 2).toUpperCase()}
                                      </div>
                                    )}

                                    <div className="space-y-1.5 min-w-0 flex-1">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <span className="text-base font-bold text-slate-900">{offer.store_name}</span>
                                        <Badge variant="success" size="sm" className="text-[10px]">
                                          {isVariantExact ? '✓ Same Product' : '✓ Exact Match'}
                                        </Badge>
                                        {typeof offer.match_confidence === 'number' && (
                                          <span className="text-[10px] font-mono font-semibold bg-emerald-50 text-emerald-800 px-1.5 py-0.5 rounded border border-emerald-200">
                                            {(offer.match_confidence * 100).toFixed(0)}% match
                                          </span>
                                        )}
                                        {isCheaper && (
                                          <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                                            {offer.price_delta_label || 'Cheaper than Apex'}
                                          </span>
                                        )}
                                      </div>

                                      <p className="text-xs font-semibold text-slate-800 line-clamp-2">
                                        {offer.external_product_title || data.canonical_product?.title || data.product_name}
                                      </p>

                                      <div className="flex items-center gap-2 text-[11px] text-slate-500 font-medium flex-wrap">
                                        <span className="text-emerald-700 font-semibold flex items-center gap-1">
                                          <CheckCircle2Icon className="w-3 h-3" />
                                          Same Style {data.canonical_product?.style_code || ''}
                                        </span>
                                        <span>•</span>
                                        <span>Variant: {data.canonical_product?.variant || 'Standard'}</span>
                                        {offer.observed_at && (
                                          <>
                                            <span>•</span>
                                            <span className="text-[10px] text-slate-400 font-normal">
                                              Observed: {new Date(offer.observed_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                                            </span>
                                          </>
                                        )}
                                      </div>
                                    </div>
                                  </div>

                                  {/* Right: Price & Outbound PDP Button */}
                                  <div className="flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-3 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                                    <div className="text-left sm:text-right">
                                      <div className="text-xl sm:text-2xl font-black font-mono text-slate-900">
                                        ₹{offer.price?.toLocaleString('en-IN')}
                                      </div>
                                      <p className="text-[10px] text-slate-400 font-medium">
                                        {isCheaper ? `Save ₹${Math.round(Math.abs(offer.difference_from_apex || 0))} vs Apex` : 'Observed Price'}
                                      </p>
                                    </div>

                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.preventDefault();
                                        if (offer.external_url && (offer.external_url.startsWith('https://') || offer.external_url.startsWith('http://'))) {
                                          window.open(offer.external_url, '_blank', 'noopener,noreferrer');
                                        }
                                      }}
                                      className="inline-flex items-center justify-center gap-1.5 text-xs font-bold px-4 py-2 rounded-xl border border-indigo-600 bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs transition-all cursor-pointer whitespace-nowrap"
                                    >
                                      View on {offer.store_name.split(' ')[0]} →
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}

                        {/* 2. Unverified Search / Discovery Fallbacks */}
                        {fallbackOffers.length > 0 && (
                          <div className="space-y-2 pt-3 border-t border-slate-200/80">
                            <div className="flex items-center justify-between text-xs font-bold text-slate-500 px-1">
                              <span className="text-[11px] uppercase tracking-wider text-slate-500">
                                Search & Discovery Fallbacks
                              </span>
                              <span className="text-[10px] text-slate-400 font-normal">Exact listing unverified • Live search</span>
                            </div>

                            {fallbackOffers.map((offer) => (
                              <div
                                key={offer.id}
                                className="p-3 rounded-xl border border-slate-200/80 bg-slate-50/50 flex items-center justify-between gap-3 text-slate-600"
                              >
                                <div className="flex items-center gap-3">
                                  {offer.store_logo_url ? (
                                    <img
                                      src={offer.store_logo_url}
                                      alt={offer.store_name}
                                      className="w-8 h-8 rounded-lg object-contain p-1 bg-white border border-slate-200 shrink-0"
                                    />
                                  ) : (
                                    <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-600 flex items-center justify-center font-bold text-xs shrink-0">
                                      {offer.store_name.slice(0, 2).toUpperCase()}
                                    </div>
                                  )}

                                  <div>
                                    <div className="flex items-center gap-2">
                                      <span className="text-sm font-semibold text-slate-800">{offer.store_name}</span>
                                      <Badge variant="neutral" size="sm" className="text-[9px]">
                                        Search Fallback
                                      </Badge>
                                    </div>
                                    <p className="text-[11px] text-slate-400">
                                      Exact product listing could not be independently verified
                                    </p>
                                  </div>
                                </div>

                                <div className="flex items-center gap-3">
                                  <span className="text-xs text-slate-400 font-medium">Price varies</span>
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.preventDefault();
                                      if (offer.external_url) {
                                        window.open(offer.external_url, '_blank', 'noopener,noreferrer');
                                      }
                                    }}
                                    className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-slate-700 transition-colors cursor-pointer"
                                  >
                                    Search on {offer.store_name} →
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>

                {/* Transparency Footnote */}
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80 text-[11px] text-slate-500 flex items-start gap-2">
                  <ShieldCheckIcon className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                  <p>
                    <span className="font-semibold text-slate-700">Authoritative Governance Boundary: </span>
                    External prices are informational and matched via deterministic GTIN/Model verification. External links redirect to authorized destinations only. Apex purchases execute with server-authoritative pricing and Razorpay.
                  </p>
                </div>
              </>
            ) : (
              /* Price History Tab */
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-slate-900">Historical Price Observations</h4>
                  <Badge variant="neutral" size="sm">
                    {history?.has_sufficient_data ? 'Verified 90-Day Trend' : 'Tracking Active'}
                  </Badge>
                </div>

                {history && history.history.length > 0 ? (
                  <div className="border border-slate-200 rounded-xl overflow-hidden divide-y divide-slate-200">
                    <div className="grid grid-cols-3 bg-slate-50 px-4 py-2 text-xs font-bold text-slate-600">
                      <span>Date</span>
                      <span>Source Store</span>
                      <span className="text-right">Observed Price</span>
                    </div>
                    {history.history.map((item, idx) => (
                      <div key={idx} className="grid grid-cols-3 px-4 py-2.5 text-xs text-slate-700 items-center">
                        <span className="font-mono text-slate-500">{item.date}</span>
                        <span className="font-medium text-slate-900">{item.store_name}</span>
                        <span className="font-mono font-bold text-slate-900 text-right">
                          ₹{item.price.toLocaleString('en-IN')}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-10 text-center text-slate-500 text-xs bg-slate-50 rounded-xl border border-slate-200">
                    <ClockIcon className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                    <p className="font-medium">Not enough verified price observations yet.</p>
                    <p className="text-slate-400 mt-0.5">Historical observations are recorded continuously.</p>
                  </div>
                )}
              </div>
            )
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-100 bg-slate-50/80 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <ClockIcon className="w-3.5 h-3.5 text-slate-400" />
            <span>Checked: {data ? new Date(data.checked_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Just now'}</span>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
