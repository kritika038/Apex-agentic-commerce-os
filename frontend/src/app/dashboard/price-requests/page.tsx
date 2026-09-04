'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { apiClient, extractErrorMessage } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';
import { ProductImage } from '@/components/ui/ProductImage';
import { Button } from '@/components/ui/Button';
import {
  SparklesIcon,
  CheckIcon,
  SearchIcon,
  AlertTriangleIcon,
} from '@/components/ui/Icons';

export interface NegotiatedOfferRecord {
  id: string;
  offer_code: string;
  negotiation_id?: string;
  merchant_id: string;
  customer_id: string;
  buyer_user_id?: string;
  product_id: string;
  product_name?: string;
  product_image_url?: string;
  category?: string;
  is_actionable: boolean;
  quantity: number;
  list_unit_price: number;
  list_total: number;
  requested_unit_price: number;
  requested_total: number;
  offered_unit_price: number;
  offered_total: number;
  discount_amount: number;
  discount_percent: number;
  final_total: number;
  currency: string;
  status: string;
  reason?: string;
  expires_at: string;
  created_at: string;
  is_active: boolean;
  requires_human_approval: boolean;
  customer_accepted: boolean;
  customer_accepted_at?: string;
  customer_rejected_at?: string;
  payment_order_id?: string;
  payment_status?: string;
  order_id?: string;
  audit_hash?: string;
}

type TabFilter = 'ALL' | 'PENDING' | 'APPROVED' | 'COUNTERED' | 'DECLINED' | 'CONFIRMED';
type SortOption = 'NEWEST' | 'OLDEST' | 'DISCOUNT_HIGH' | 'AMOUNT_HIGH';

export default function MerchantPriceRequestsPage() {
  const [offers, setOffers] = useState<NegotiatedOfferRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Sorting
  const [activeTab, setActiveTab] = useState<TabFilter>('PENDING');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSort, setActiveSort] = useState<SortOption>('NEWEST');

  // Action states
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Counter Modal State
  const [counterModalOffer, setCounterModalOffer] = useState<NegotiatedOfferRecord | null>(null);
  const [counterUnitPrice, setCounterUnitPrice] = useState<number>(0);
  const [counterReason, setCounterReason] = useState<string>('');

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // 1. Fetch Merchant Price Requests
  const fetchMerchantRequests = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get<NegotiatedOfferRecord[]>('/negotiation/merchant-requests');
      setOffers(res.data || []);
    } catch (err: unknown) {
      console.error('Failed to fetch merchant price requests', err);
      setError(extractErrorMessage(err, 'Failed to load merchant price requests.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMerchantRequests();
  }, [fetchMerchantRequests]);

  // 2. Decision Handlers
  const handleApprove = async (offer: NegotiatedOfferRecord) => {
    setActionLoadingId(offer.id);
    try {
      const res = await apiClient.post<NegotiatedOfferRecord>(`/negotiation/${offer.id}/merchant/approve`, {
        merchant_id: offer.merchant_id,
        reason: 'Approved by merchant admin from Price Requests Inbox.',
      });
      showToast(`Request ${offer.offer_code} approved successfully!`, 'success');
      setOffers((prev) => prev.map((o) => (o.id === offer.id ? { ...o, ...res.data } : o)));
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Failed to approve price request.'), 'error');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleOpenCounterModal = (offer: NegotiatedOfferRecord) => {
    setCounterModalOffer(offer);
    // Pre-fill counter unit price halfway between requested and list price
    const midPrice = Math.round((offer.list_unit_price + offer.requested_unit_price) / 2);
    setCounterUnitPrice(midPrice);
    setCounterReason(`We can offer ₹${midPrice.toLocaleString('en-IN')}/unit for this order.`);
  };

  const handleSubmitCounter = async () => {
    if (!counterModalOffer) return;
    if (counterUnitPrice <= 0 || counterUnitPrice > counterModalOffer.list_unit_price) {
      showToast('Please enter a valid counter price less than list price.', 'error');
      return;
    }

    setActionLoadingId(counterModalOffer.id);
    try {
      const counterTotal = counterUnitPrice * counterModalOffer.quantity;
      const res = await apiClient.post<NegotiatedOfferRecord>(`/negotiation/${counterModalOffer.id}/merchant/counter`, {
        merchant_id: counterModalOffer.merchant_id,
        counter_unit_price: counterUnitPrice,
        counter_total: counterTotal,
        reason: counterReason || 'Merchant counter offer.',
      });
      showToast(`Counter offer of ₹${counterTotal.toLocaleString('en-IN')} sent to customer!`, 'success');
      setOffers((prev) => prev.map((o) => (o.id === counterModalOffer.id ? { ...o, ...res.data } : o)));
      setCounterModalOffer(null);
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Failed to send counter offer.'), 'error');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDecline = async (offer: NegotiatedOfferRecord) => {
    if (!confirm(`Are you sure you want to decline customer price request ${offer.offer_code}?`)) {
      return;
    }
    setActionLoadingId(offer.id);
    try {
      const res = await apiClient.post<NegotiatedOfferRecord>(`/negotiation/${offer.id}/merchant/reject`, {
        merchant_id: offer.merchant_id,
        reason: 'Price request declined by merchant admin.',
      });
      showToast(`Request ${offer.offer_code} declined.`, 'info');
      setOffers((prev) => prev.map((o) => (o.id === offer.id ? { ...o, ...res.data } : o)));
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Failed to decline request.'), 'error');
    } finally {
      setActionLoadingId(null);
    }
  };

  // 3. Tab Counters
  const tabCounts = useMemo(() => {
    let pending = 0;
    let approved = 0;
    let countered = 0;
    let declined = 0;
    let confirmed = 0;

    offers.forEach((o) => {
      const isExp = o.status === 'EXPIRED' || (o.expires_at && new Date(o.expires_at).getTime() < Date.now());
      if (
        !isExp &&
        (o.status === 'HUMAN_APPROVAL_REQUIRED' ||
          o.status === 'WAITING_FOR_MERCHANT' ||
          o.status === 'OFFER_REQUESTED' ||
          o.status === 'NEGOTIATION_STARTED' ||
          o.status === 'MERCHANT_POLICY_EVALUATING' ||
          o.status === 'PENDING')
      ) {
        pending++;
      } else if (
        o.status === 'MERCHANT_APPROVED' ||
        o.status === 'AUTO_ACCEPTED' ||
        o.status === 'CUSTOMER_OFFER_PRESENTED'
      ) {
        approved++;
      } else if (o.status === 'COUNTER_OFFERED' || o.status === 'MERCHANT_COUNTERED') {
        countered++;
      } else if (
        o.status === 'REJECTED' ||
        o.status === 'MERCHANT_REJECTED' ||
        o.status === 'CUSTOMER_REJECTED'
      ) {
        declined++;
      } else if (o.status === 'ORDER_CONFIRMED' || o.payment_status === 'CAPTURED') {
        confirmed++;
      }
    });

    return {
      all: offers.length,
      pending,
      approved,
      countered,
      declined,
      confirmed,
    };
  }, [offers]);

  // 4. Filter & Sort Offers
  const filteredOffers = useMemo(() => {
    let list = [...offers];

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (o) =>
          o.product_name?.toLowerCase().includes(q) ||
          o.offer_code?.toLowerCase().includes(q) ||
          o.customer_id?.toLowerCase().includes(q) ||
          o.category?.toLowerCase().includes(q) ||
          o.status.toLowerCase().includes(q)
      );
    }

    // Tab filter
    if (activeTab === 'PENDING') {
      list = list.filter((o) => {
        const isExp = o.status === 'EXPIRED' || (o.expires_at && new Date(o.expires_at).getTime() < Date.now());
        return (
          !isExp &&
          (o.status === 'HUMAN_APPROVAL_REQUIRED' ||
            o.status === 'WAITING_FOR_MERCHANT' ||
            o.status === 'OFFER_REQUESTED' ||
            o.status === 'NEGOTIATION_STARTED' ||
            o.status === 'MERCHANT_POLICY_EVALUATING' ||
            o.status === 'PENDING')
        );
      });
    } else if (activeTab === 'APPROVED') {
      list = list.filter(
        (o) =>
          o.status === 'MERCHANT_APPROVED' ||
          o.status === 'AUTO_ACCEPTED' ||
          o.status === 'CUSTOMER_OFFER_PRESENTED'
      );
    } else if (activeTab === 'COUNTERED') {
      list = list.filter((o) => o.status === 'COUNTER_OFFERED' || o.status === 'MERCHANT_COUNTERED');
    } else if (activeTab === 'DECLINED') {
      list = list.filter(
        (o) =>
          o.status === 'REJECTED' ||
          o.status === 'MERCHANT_REJECTED' ||
          o.status === 'CUSTOMER_REJECTED'
      );
    } else if (activeTab === 'CONFIRMED') {
      list = list.filter((o) => o.status === 'ORDER_CONFIRMED' || o.payment_status === 'CAPTURED');
    }

    // Sort: Counter-offers first, then Pending, then by selected sort option
    list.sort((a, b) => {
      const isExpA = a.status === 'EXPIRED' || (a.expires_at && new Date(a.expires_at).getTime() < Date.now());
      const isExpB = b.status === 'EXPIRED' || (b.expires_at && new Date(b.expires_at).getTime() < Date.now());

      const getRank = (o: NegotiatedOfferRecord, exp: boolean) => {
        if (!exp && (o.status === 'COUNTER_OFFERED' || o.status === 'MERCHANT_COUNTERED')) return 1;
        if (
          !exp &&
          (o.status === 'HUMAN_APPROVAL_REQUIRED' ||
            o.status === 'WAITING_FOR_MERCHANT' ||
            o.status === 'OFFER_REQUESTED' ||
            o.status === 'NEGOTIATION_STARTED' ||
            o.status === 'MERCHANT_POLICY_EVALUATING' ||
            o.status === 'PENDING')
        )
          return 2;
        return 3;
      };

      const rankA = getRank(a, !!isExpA);
      const rankB = getRank(b, !!isExpB);

      if (rankA !== rankB) {
        return rankA - rankB;
      }

      if (activeSort === 'NEWEST') {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
      if (activeSort === 'OLDEST') {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      if (activeSort === 'DISCOUNT_HIGH') {
        return Number(b.discount_percent) - Number(a.discount_percent);
      }
      if (activeSort === 'AMOUNT_HIGH') {
        return Number(b.final_total) - Number(a.final_total);
      }
      return 0;
    });

    return list;
  }, [offers, searchQuery, activeTab, activeSort]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <DashboardNav />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header Breadcrumbs & Controls */}
        <div className="mb-6">
          <div className="flex items-center gap-2 text-xs text-slate-500 mb-2">
            <Link href="/dashboard" className="hover:text-slate-900 transition-colors">
              Merchant Console
            </Link>
            <span>/</span>
            <span className="text-slate-900 font-semibold">Customer Price Requests</span>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-2xl bg-amber-500 text-white shadow-sm flex items-center justify-center">
                <SparklesIcon size={22} />
              </div>
              <div>
                <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
                  Customer Price Requests
                </h1>
                <p className="text-xs text-slate-500 mt-0.5">
                  Review real-time buyer price requests, policy escalations, and send counter-offers.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <Link
                href="/dashboard/policies"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
              >
                <span>⚙️ Negotiation Policy Rules</span>
              </Link>
              <button
                onClick={fetchMerchantRequests}
                disabled={loading}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs"
              >
                <span className={loading ? 'animate-spin' : ''}>🔄</span>
                <span>Refresh</span>
              </button>
            </div>
          </div>
        </div>

        {/* Filter Tabs & Search Controls */}
        <div className="bg-white border border-slate-200 rounded-2xl p-4 mb-6 shadow-2xs space-y-4">
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none border-b border-slate-100">
            <button
              onClick={() => setActiveTab('PENDING')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
                activeTab === 'PENDING'
                  ? 'bg-amber-500 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <span>🟠 Needs Your Decision</span>
              {tabCounts.pending > 0 && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    activeTab === 'PENDING' ? 'bg-amber-700 text-white' : 'bg-amber-100 text-amber-800 animate-pulse font-extrabold'
                  }`}
                >
                  {tabCounts.pending}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('ALL')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
                activeTab === 'ALL'
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <span>All Requests</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  activeTab === 'ALL' ? 'bg-slate-700 text-white' : 'bg-slate-200 text-slate-700'
                }`}
              >
                {tabCounts.all}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('APPROVED')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
                activeTab === 'APPROVED'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <span>🟢 Approved</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  activeTab === 'APPROVED' ? 'bg-emerald-800 text-white' : 'bg-slate-200 text-slate-700'
                }`}
              >
                {tabCounts.approved}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('COUNTERED')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
                activeTab === 'COUNTERED'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <span>🟡 Counter-Offered</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  activeTab === 'COUNTERED' ? 'bg-indigo-800 text-white' : 'bg-slate-200 text-slate-700'
                }`}
              >
                {tabCounts.countered}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('CONFIRMED')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
                activeTab === 'CONFIRMED'
                  ? 'bg-teal-600 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <span>✓ Confirmed Orders</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  activeTab === 'CONFIRMED' ? 'bg-teal-800 text-white' : 'bg-slate-200 text-slate-700'
                }`}
              >
                {tabCounts.confirmed}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('DECLINED')}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
                activeTab === 'DECLINED'
                  ? 'bg-rose-600 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <span>🔴 Declined</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  activeTab === 'DECLINED' ? 'bg-rose-800 text-white' : 'bg-slate-200 text-slate-700'
                }`}
              >
                {tabCounts.declined}
              </span>
            </button>
          </div>

          {/* Search & Sort Controls */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-md">
              <SearchIcon size={14} className="absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                placeholder="Search by product, buyer email, offer code..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-8 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-2.5 text-xs text-slate-400 hover:text-slate-600"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 font-medium">Sort:</span>
              <select
                value={activeSort}
                onChange={(e) => setActiveSort(e.target.value as SortOption)}
                className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 font-semibold focus:outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500/20"
              >
                <option value="NEWEST">Newest First</option>
                <option value="OLDEST">Oldest First</option>
                <option value="DISCOUNT_HIGH">Highest Discount Requested</option>
                <option value="AMOUNT_HIGH">Highest Order Total</option>
              </select>
            </div>
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((n) => (
              <div key={n} className="bg-white border border-slate-200 rounded-2xl p-6 animate-pulse">
                <div className="flex gap-4">
                  <div className="w-24 h-24 bg-slate-200 rounded-xl shrink-0" />
                  <div className="flex-1 space-y-3">
                    <div className="h-4 bg-slate-200 rounded w-1/3" />
                    <div className="h-3 bg-slate-200 rounded w-1/2" />
                    <div className="h-8 bg-slate-200 rounded w-1/4" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-rose-700 text-xs">
            <AlertTriangleIcon size={24} className="mx-auto mb-2 text-rose-500" />
            <p className="font-bold">{error}</p>
            <button
              onClick={fetchMerchantRequests}
              className="mt-3 px-4 py-1.5 bg-rose-600 text-white font-semibold rounded-xl text-xs hover:bg-rose-700"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && filteredOffers.length === 0 && (
          <div className="bg-white border border-slate-200 rounded-3xl p-12 text-center shadow-2xs max-w-md mx-auto my-8">
            <div className="w-14 h-14 bg-amber-50 rounded-2xl flex items-center justify-center text-amber-600 mx-auto mb-4">
              <SparklesIcon size={24} />
            </div>
            <h3 className="text-base font-bold text-slate-900 mb-1">No Price Requests in this View</h3>
            <p className="text-xs text-slate-500 mb-6">
              {activeTab === 'PENDING'
                ? 'All pending customer price requests have been handled.'
                : 'No price requests matched the selected filter.'}
            </p>
            <button
              onClick={() => {
                setActiveTab('ALL');
                setSearchQuery('');
              }}
              className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-xl hover:bg-indigo-600 transition-colors"
            >
              View All Price Requests
            </button>
          </div>
        )}

        {/* Merchant Offer Cards List */}
        {!loading && !error && filteredOffers.length > 0 && (
          <div className="space-y-4">
            {filteredOffers.map((offer) => {
              const isOfferExpired =
                offer.status === 'EXPIRED' ||
                (offer.expires_at ? new Date(offer.expires_at).getTime() < Date.now() : false);

              const isPending =
                !isOfferExpired &&
                (offer.status === 'HUMAN_APPROVAL_REQUIRED' ||
                  offer.status === 'WAITING_FOR_MERCHANT' ||
                  offer.status === 'OFFER_REQUESTED' ||
                  offer.status === 'NEGOTIATION_STARTED' ||
                  offer.status === 'MERCHANT_POLICY_EVALUATING' ||
                  offer.status === 'PENDING');

              const requestedDiscountPct =
                offer.list_total > 0 && offer.requested_total > 0
                  ? Math.max(0, ((offer.list_total - offer.requested_total) / offer.list_total) * 100)
                  : 0;

              return (
                <div
                  key={offer.id}
                  className={`bg-white border rounded-2xl p-5 sm:p-6 transition-all shadow-2xs hover:shadow-md ${
                    isPending ? 'border-amber-300 ring-1 ring-amber-500/10' : 'border-slate-200'
                  }`}
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
                    {/* Left Section: Product Thumbnail & Customer Info */}
                    <div className="flex items-start gap-4">
                      <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-xl overflow-hidden bg-slate-100 border border-slate-200/80 shrink-0">
                        <ProductImage
                          src={offer.product_image_url}
                          alt={offer.product_name || 'Product'}
                          category={offer.category}
                          productName={offer.product_name}
                          className="w-full h-full object-cover"
                        />
                      </div>

                      <div className="space-y-1.5 flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[11px] font-mono font-bold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                            {offer.offer_code}
                          </span>
                          {isPending ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300 animate-pulse">
                              <span>🟠</span>
                              <span>NEEDS YOUR DECISION</span>
                            </span>
                          ) : isOfferExpired ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300">
                              <span>⏱️</span>
                              <span>EXPIRED</span>
                            </span>
                          ) : offer.status === 'MERCHANT_APPROVED' || offer.status === 'AUTO_ACCEPTED' ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                              <span>🟢</span>
                              <span>APPROVED</span>
                            </span>
                          ) : offer.status === 'COUNTER_OFFERED' || offer.status === 'MERCHANT_COUNTERED' ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-300">
                              <span>🟡</span>
                              <span>COUNTER SENT</span>
                            </span>
                          ) : offer.status === 'ORDER_CONFIRMED' || offer.payment_status === 'CAPTURED' ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-teal-100 text-teal-800 border border-teal-300">
                              <span>✓</span>
                              <span>PURCHASED / CONFIRMED</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
                              <span>🔴</span>
                              <span>DECLINED</span>
                            </span>
                          )}

                          {offer.category && (
                            <span className="text-[10px] font-semibold text-slate-500 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded-full uppercase tracking-wider">
                              {offer.category}
                            </span>
                          )}
                        </div>

                        <h3 className="text-sm sm:text-base font-bold text-slate-900 line-clamp-1">
                          {offer.product_name || `Product #${offer.product_id.substring(0, 8)}`}
                        </h3>

                        <div className="text-xs text-slate-500 flex flex-wrap items-center gap-x-4 gap-y-1">
                          <span>
                            Buyer: <strong className="text-slate-800 font-mono">{offer.customer_id}</strong>
                          </span>
                          <span>
                            Qty: <strong className="text-slate-800">{offer.quantity} unit{offer.quantity > 1 ? 's' : ''}</strong>
                          </span>
                          <span>
                            Received: {new Date(offer.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>

                        {/* Price Proposal Comparison Pills */}
                        <div className="pt-1 flex flex-wrap items-center gap-2 text-xs">
                          <div className="bg-slate-100 text-slate-700 px-2.5 py-1 rounded-lg">
                            <span className="text-[10px] text-slate-500 block">List Total</span>
                            <span className="font-bold">₹{Number(offer.list_total).toLocaleString('en-IN')}</span>
                            <span className="text-[10px] text-slate-400 ml-1">(₹{Number(offer.list_unit_price).toLocaleString('en-IN')}/unit)</span>
                          </div>

                          <div className="bg-amber-50 border border-amber-200 text-amber-900 px-2.5 py-1 rounded-lg">
                            <span className="text-[10px] text-amber-600 block">Customer Requested Total</span>
                            <span className="font-bold">₹{Number(offer.requested_total).toLocaleString('en-IN')}</span>
                            <span className="text-[10px] text-amber-700 ml-1 font-semibold">
                              ({requestedDiscountPct.toFixed(1)}% OFF)
                            </span>
                          </div>

                          {offer.status === 'COUNTER_OFFERED' || offer.status === 'MERCHANT_COUNTERED' ? (
                            <div className="bg-indigo-50 border border-indigo-200 text-indigo-900 px-2.5 py-1 rounded-lg">
                              <span className="text-[10px] text-indigo-600 block">Offered Counter Total</span>
                              <span className="font-bold">₹{Number(offer.final_total).toLocaleString('en-IN')}</span>
                              <span className="text-[10px] text-indigo-700 ml-1 font-semibold">
                                ({Number(offer.discount_percent).toFixed(1)}% OFF)
                              </span>
                            </div>
                          ) : null}
                        </div>

                        {/* Reason / Context */}
                        {offer.reason && (
                          <div className="mt-2 text-xs bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-700 flex items-start gap-2">
                            <span className="text-amber-600 shrink-0 font-bold">💬 Note:</span>
                            <p className="italic">{offer.reason}</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right Section: Decision Actions */}
                    <div className="flex flex-col sm:flex-row lg:flex-col items-start sm:items-center lg:items-end justify-between lg:justify-center gap-4 pt-4 lg:pt-0 border-t lg:border-t-0 border-slate-100 shrink-0">
                      {isPending ? (
                        <div className="flex flex-wrap items-center gap-2">
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleApprove(offer)}
                            disabled={actionLoadingId === offer.id}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs"
                          >
                            {actionLoadingId === offer.id ? 'Approving...' : '✓ Approve Request'}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleOpenCounterModal(offer)}
                            disabled={actionLoadingId === offer.id}
                            className="border-indigo-200 text-indigo-700 hover:bg-indigo-50 font-bold text-xs"
                          >
                            ⇄ Counter Offer
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDecline(offer)}
                            disabled={actionLoadingId === offer.id}
                            className="border-rose-200 text-rose-600 hover:bg-rose-50 font-bold text-xs"
                          >
                            ✕ Decline
                          </Button>
                        </div>
                      ) : (
                        <div className="text-xs text-slate-400 font-medium">
                          {isOfferExpired ? (
                            <span className="text-slate-500 font-semibold">Offer expired</span>
                          ) : offer.status === 'ORDER_CONFIRMED' || offer.payment_status === 'CAPTURED' ? (
                            <span className="text-teal-700 font-semibold">Order placed & paid</span>
                          ) : offer.status === 'MERCHANT_APPROVED' || offer.status === 'AUTO_ACCEPTED' ? (
                            <span className="text-emerald-700 font-semibold">Approved (Awaiting customer checkout)</span>
                          ) : offer.status === 'COUNTER_OFFERED' || offer.status === 'MERCHANT_COUNTERED' ? (
                            <span className="text-indigo-700 font-semibold">Counter sent (Awaiting customer acceptance)</span>
                          ) : (
                            <span>Request closed</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Counter Offer Modal */}
      {counterModalOffer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
          <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-lg w-full shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150 space-y-5">
            <div>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-extrabold text-slate-900">
                  Send Counter Offer
                </h3>
                <button
                  onClick={() => setCounterModalOffer(null)}
                  className="text-slate-400 hover:text-slate-600 text-lg font-bold"
                >
                  ✕
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Proposal for {counterModalOffer.product_name} ({counterModalOffer.quantity} unit{counterModalOffer.quantity > 1 ? 's' : ''})
              </p>
            </div>

            <div className="space-y-4">
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 text-xs space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-500">List Unit Price:</span>
                  <span className="font-bold text-slate-800">₹{counterModalOffer.list_unit_price.toLocaleString('en-IN')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-amber-600 font-semibold">Buyer Requested Unit Price:</span>
                  <span className="font-bold text-amber-900">₹{counterModalOffer.requested_unit_price.toLocaleString('en-IN')}</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-800 mb-1">
                  Counter Unit Price (₹)
                </label>
                <input
                  type="number"
                  value={counterUnitPrice}
                  onChange={(e) => setCounterUnitPrice(Number(e.target.value))}
                  min={1}
                  max={counterModalOffer.list_unit_price}
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-sm font-bold text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Counter Total: <strong className="text-slate-900">₹{(counterUnitPrice * counterModalOffer.quantity).toLocaleString('en-IN')}</strong> (Save ₹{((counterModalOffer.list_unit_price - counterUnitPrice) * counterModalOffer.quantity).toLocaleString('en-IN')})
                </p>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-800 mb-1">
                  Note to Customer (Optional)
                </label>
                <textarea
                  value={counterReason}
                  onChange={(e) => setCounterReason(e.target.value)}
                  rows={3}
                  className="w-full px-3.5 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
                  placeholder="Explain why this price is offered or add terms..."
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCounterModalOffer(null)}
                className="text-xs font-semibold"
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSubmitCounter}
                disabled={actionLoadingId === counterModalOffer.id}
                className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs"
              >
                {actionLoadingId === counterModalOffer.id ? 'Sending...' : 'Send Counter Offer'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 animate-in fade-in slide-in-from-bottom-5 duration-200">
          <div
            className={`px-4 py-3 rounded-2xl shadow-xl text-xs font-semibold flex items-center gap-2.5 border ${
              toast.type === 'success'
                ? 'bg-emerald-600 text-white border-emerald-500'
                : toast.type === 'error'
                ? 'bg-rose-600 text-white border-rose-500'
                : 'bg-slate-900 text-white border-slate-800'
            }`}
          >
            {toast.type === 'success' && <CheckIcon size={16} />}
            {toast.type === 'error' && <AlertTriangleIcon size={16} />}
            <span>{toast.message}</span>
          </div>
        </div>
      )}
    </div>
  );
}
