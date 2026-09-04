'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { apiClient, extractErrorMessage } from '@/lib/api';
import { loadRazorpayScript, RazorpayCheckoutOptions } from '@/lib/razorpay';
import { StorefrontHeader, UserProfile } from '@/components/storefront/StorefrontHeader';
import { CartDrawer, CartData } from '@/components/storefront/CartDrawer';
import { AuthModal, AuthConfig } from '@/components/auth/AuthModal';
import { ProductImage } from '@/components/ui/ProductImage';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  SparklesIcon,
  ShieldCheckIcon,
  ClockIcon,
  CheckIcon,
  SearchIcon,
  ShoppingBagIcon,
  AlertTriangleIcon,
} from '@/components/ui/Icons';

export interface NegotiatedOfferRecord {
  id: string;
  offer_code: string;
  negotiation_id?: string;
  merchant_id: string;
  customer_id: string;
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

interface CheckoutNegotiationResponse {
  offer_id: string;
  negotiation_id: string;
  razorpay_order_id: string;
  amount: number;
  amount_paise: number;
  currency: string;
  key_id?: string;
  razorpay_key_id?: string;
  status: string;
}

type TabFilter = 'ALL' | 'ACTION_REQUIRED' | 'IN_REVIEW' | 'CONFIRMED' | 'CLOSED';
type SortOption = 'NEWEST' | 'OLDEST' | 'SAVINGS_HIGH' | 'EXPIRING_SOON';

export default function PriceRequestsPage() {
  const router = useRouter();

  // State Management
  const [offers, setOffers] = useState<NegotiatedOfferRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Search & Sort
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<TabFilter>('ALL');
  const [activeSort, setActiveSort] = useState<SortOption>('NEWEST');

  // User & Auth State
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // Cart State
  const [sessionId, setSessionId] = useState<string>('');
  const [cart, setCart] = useState<CartData>({ items: [], total_amount: 0, currency: 'INR' });
  const [isCartOpen, setIsCartOpen] = useState(false);

  // Action states
  const [processingOfferId, setProcessingOfferId] = useState<string | null>(null);
  const [payingOfferId, setPayingOfferId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // 1. Initialize Auth & Session
  useEffect(() => {
    let sId = localStorage.getItem('shopping_session_id');
    if (!sId) {
      sId = 'sess_' + Math.random().toString(36).substring(2, 9);
      localStorage.setItem('shopping_session_id', sId);
    }
    setSessionId(sId);

    const savedUser = localStorage.getItem('user_profile');
    if (savedUser) {
      try {
        setUserProfile(JSON.parse(savedUser));
      } catch (e) {
        console.error('Failed to parse user profile', e);
      }
    }

    // Fetch Auth Config
    apiClient
      .get<AuthConfig>('/auth/config')
      .then((res) => setAuthConfig(res.data))
      .catch((err) => console.warn('Failed to load auth config', err));
  }, []);

  // 2. Fetch User's Negotiated Price Requests
  const fetchPriceRequests = useCallback(async () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    if (!token) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get<NegotiatedOfferRecord[]>('/negotiation/my-requests');
      setOffers(res.data || []);
    } catch (err: unknown) {
      console.error('Failed to fetch price requests', err);
      setError(extractErrorMessage(err, 'Failed to load your price requests.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPriceRequests();
  }, [fetchPriceRequests, userProfile]);

  // 3. Handle Actions on Offers (Accept / Reject / Pay)
  const handleAcceptOffer = async (offer: NegotiatedOfferRecord) => {
    setProcessingOfferId(offer.id);
    try {
      const res = await apiClient.post<NegotiatedOfferRecord>(`/negotiation/${offer.id}/accept`, {
        customer_id: userProfile?.email || offer.customer_id,
        reason: 'Accepted by customer via Price Requests dashboard',
      });
      showToast('Counter-offer accepted! You can now proceed to checkout.', 'success');
      setOffers((prev) => prev.map((o) => (o.id === offer.id ? { ...o, ...res.data } : o)));
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Failed to accept counter-offer.'), 'error');
    } finally {
      setProcessingOfferId(null);
    }
  };

  const handleRejectOffer = async (offer: NegotiatedOfferRecord) => {
    setProcessingOfferId(offer.id);
    try {
      const res = await apiClient.post<NegotiatedOfferRecord>(`/negotiation/${offer.id}/reject`, {
        customer_id: userProfile?.email || offer.customer_id,
        reason: 'Declined by customer via Price Requests dashboard',
      });
      showToast('Price request closed.', 'info');
      setOffers((prev) => prev.map((o) => (o.id === offer.id ? { ...o, ...res.data } : o)));
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Failed to decline offer.'), 'error');
    } finally {
      setProcessingOfferId(null);
    }
  };

  const handleCheckoutAndPay = async (offer: NegotiatedOfferRecord) => {
    setPayingOfferId(offer.id);
    try {
      // 1. Create locked payment order on server
      const res = await apiClient.post<CheckoutNegotiationResponse>(`/negotiation/${offer.id}/checkout`, {
        customer_id: userProfile?.email || offer.customer_id,
        payment_method: 'upi',
      });

      const checkoutRes = res.data;
      if (!checkoutRes || !checkoutRes.razorpay_order_id) {
        throw new Error('Failed to create server payment order.');
      }

      // 2. Load Razorpay SDK
      const isLoaded = await loadRazorpayScript();
      if (!isLoaded || !window.Razorpay) {
        showToast('Online payment checkout failed to load. Please try again.', 'error');
        setPayingOfferId(null);
        return;
      }

      // 3. Resolve key
      const keyId = checkoutRes.razorpay_key_id || checkoutRes.key_id || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;
      if (!keyId) {
        showToast('Payment key not configured.', 'error');
        setPayingOfferId(null);
        return;
      }

      // 4. Open Razorpay Modal
      const options: RazorpayCheckoutOptions = {
        key: keyId,
        amount: checkoutRes.amount_paise,
        currency: checkoutRes.currency || 'INR',
        name: 'Apex Sports',
        description: `Negotiated Order • ${offer.offer_code}`,
        order_id: checkoutRes.razorpay_order_id,
        handler: async (paymentResponse) => {
          try {
            const verifyRes = await apiClient.post('/payments/verify-signature', {
              razorpay_order_id: paymentResponse.razorpay_order_id,
              razorpay_payment_id: paymentResponse.razorpay_payment_id,
              razorpay_signature: paymentResponse.razorpay_signature,
            });

            if (verifyRes.data?.status === 'CAPTURED' || verifyRes.data?.status === 'SUCCESS' || verifyRes.data?.order_id) {
              showToast('🎉 Payment verified! Your order has been placed.', 'success');
              fetchPriceRequests();
            } else {
              showToast('Payment confirmation pending.', 'info');
              fetchPriceRequests();
            }
          } catch (err: unknown) {
            console.error('Signature verification error:', err);
            showToast(extractErrorMessage(err, 'Payment verification failed.'), 'error');
            fetchPriceRequests();
          } finally {
            setPayingOfferId(null);
          }
        },
        prefill: {
          name: userProfile?.full_name || 'Valued Customer',
          email: userProfile?.email || offer.customer_id,
          contact: '9999999999',
        },
        theme: {
          color: '#4f46e5',
        },
        modal: {
          ondismiss: () => {
            setPayingOfferId(null);
          },
        },
      };

      const rzp = new window.Razorpay(options);
      rzp.on('payment.failed', (failedRes: { error?: { description?: string } }) => {
        showToast(`Payment failed: ${failedRes?.error?.description || 'Payment error'}`, 'error');
        setPayingOfferId(null);
      });
      rzp.open();
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Failed to launch checkout.'), 'error');
      setPayingOfferId(null);
    }
  };

  // 4. Tab Counters
  const tabCounts = useMemo(() => {
    let actionRequired = 0;
    let inReview = 0;
    let confirmed = 0;
    let closed = 0;

    offers.forEach((o) => {
      if (o.is_actionable) {
        actionRequired++;
      } else if (
        o.status === 'HUMAN_APPROVAL_REQUIRED' ||
        o.status === 'WAITING_FOR_MERCHANT' ||
        o.status === 'PENDING'
      ) {
        inReview++;
      } else if (o.status === 'ORDER_CONFIRMED' || o.payment_status === 'CAPTURED') {
        confirmed++;
      } else {
        closed++;
      }
    });

    return {
      all: offers.length,
      actionRequired,
      inReview,
      confirmed,
      closed,
    };
  }, [offers]);

  // 5. Filter & Sort Offers
  const filteredOffers = useMemo(() => {
    let list = [...offers];

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (o) =>
          o.product_name?.toLowerCase().includes(q) ||
          o.offer_code?.toLowerCase().includes(q) ||
          o.category?.toLowerCase().includes(q) ||
          o.status.toLowerCase().includes(q)
      );
    }

    // Tab filter
    if (activeTab === 'ACTION_REQUIRED') {
      list = list.filter((o) => o.is_actionable);
    } else if (activeTab === 'IN_REVIEW') {
      list = list.filter(
        (o) =>
          !o.is_actionable &&
          (o.status === 'HUMAN_APPROVAL_REQUIRED' ||
            o.status === 'WAITING_FOR_MERCHANT' ||
            o.status === 'PENDING')
      );
    } else if (activeTab === 'CONFIRMED') {
      list = list.filter((o) => o.status === 'ORDER_CONFIRMED' || o.payment_status === 'CAPTURED');
    } else if (activeTab === 'CLOSED') {
      list = list.filter(
        (o) =>
          !o.is_actionable &&
          o.status !== 'ORDER_CONFIRMED' &&
          o.payment_status !== 'CAPTURED' &&
          o.status !== 'HUMAN_APPROVAL_REQUIRED' &&
          o.status !== 'WAITING_FOR_MERCHANT' &&
          o.status !== 'PENDING'
      );
    }

    // Sorting
    list.sort((a, b) => {
      if (activeSort === 'NEWEST') {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
      if (activeSort === 'OLDEST') {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      if (activeSort === 'SAVINGS_HIGH') {
        return Number(b.discount_amount) - Number(a.discount_amount);
      }
      if (activeSort === 'EXPIRING_SOON') {
        return new Date(a.expires_at).getTime() - new Date(b.expires_at).getTime();
      }
      return 0;
    });

    return list;
  }, [offers, searchQuery, activeTab, activeSort]);

  // Auth Handler
  const handleAuthSuccess = (user: UserProfile, token: string) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('user_profile', JSON.stringify(user));
    setUserProfile(user);
    setIsAuthOpen(false);
  };

  const handleSignOut = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_profile');
    setUserProfile(null);
    setOffers([]);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Storefront Header */}
      <StorefrontHeader
        cartItemCount={cart.items.reduce((sum, item) => sum + item.quantity, 0)}
        onOpenCart={() => setIsCartOpen(true)}
        onOpenAI={() => {}}
        onOpenAuth={() => setIsAuthOpen(true)}
        onSignOut={handleSignOut}
        searchQuery=""
        onSearchChange={() => {}}
        userProfile={userProfile}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Top Header & Breadcrumbs */}
        <div className="mb-6">
          <div className="flex items-center gap-2 text-xs text-slate-500 mb-2">
            <Link href="/" className="hover:text-slate-900 transition-colors">
              Home
            </Link>
            <span>/</span>
            <span className="text-slate-900 font-semibold">Price Requests</span>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-indigo-600 text-white shadow-sm">
                  <SparklesIcon size={20} />
                </div>
                <div>
                  <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
                    My Price Requests
                  </h1>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Track AI negotiations, merchant approved offers, and 1-click discounted checkouts.
                  </p>
                </div>
              </div>
            </div>

            {/* Quick Actions / Refresh */}
            {userProfile && (
              <button
                onClick={fetchPriceRequests}
                disabled={loading}
                className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs"
              >
                <span className={loading ? 'animate-spin' : ''}>🔄</span>
                <span>Refresh Requests</span>
              </button>
            )}
          </div>
        </div>

        {/* Unauthenticated Banner */}
        {!userProfile && !loading && (
          <div className="bg-white border border-slate-200 rounded-3xl p-8 sm:p-12 text-center shadow-sm max-w-xl mx-auto my-12">
            <div className="w-16 h-16 bg-indigo-50 rounded-2xl flex items-center justify-center text-indigo-600 mx-auto mb-4">
              <SparklesIcon size={32} />
            </div>
            <h2 className="text-xl font-bold text-slate-900 mb-2">Sign in to view Price Requests</h2>
            <p className="text-xs text-slate-600 mb-6 leading-relaxed">
              When you ask for a better price on any product, your personalized offers, merchant approvals, and private discounts are saved to your account.
            </p>
            <Button
              variant="primary"
              onClick={() => setIsAuthOpen(true)}
              className="px-6 py-2.5 shadow-md hover:shadow-lg font-bold"
            >
              Sign In to Your Account
            </Button>
          </div>
        )}

        {/* Authenticated Dashboard */}
        {userProfile && (
          <>
            {/* Filter Tabs & Search Controls */}
            <div className="bg-white border border-slate-200 rounded-2xl p-4 mb-6 shadow-2xs space-y-4">
              {/* Filter Tabs */}
              <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none border-b border-slate-100">
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
                  onClick={() => setActiveTab('ACTION_REQUIRED')}
                  className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
                    activeTab === 'ACTION_REQUIRED'
                      ? 'bg-amber-500 text-white shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <span>⚡ Action Required</span>
                  {tabCounts.actionRequired > 0 && (
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                        activeTab === 'ACTION_REQUIRED'
                          ? 'bg-amber-700 text-white'
                          : 'bg-amber-100 text-amber-800 animate-pulse'
                      }`}
                    >
                      {tabCounts.actionRequired}
                    </span>
                  )}
                </button>

                <button
                  onClick={() => setActiveTab('IN_REVIEW')}
                  className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
                    activeTab === 'IN_REVIEW'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <span>⏳ In Review</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      activeTab === 'IN_REVIEW' ? 'bg-indigo-800 text-white' : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    {tabCounts.inReview}
                  </span>
                </button>

                <button
                  onClick={() => setActiveTab('CONFIRMED')}
                  className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
                    activeTab === 'CONFIRMED'
                      ? 'bg-emerald-600 text-white shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <span>✅ Confirmed & Paid</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      activeTab === 'CONFIRMED' ? 'bg-emerald-800 text-white' : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    {tabCounts.confirmed}
                  </span>
                </button>

                <button
                  onClick={() => setActiveTab('CLOSED')}
                  className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 ${
                    activeTab === 'CLOSED'
                      ? 'bg-slate-700 text-white shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <span>Closed / Expired</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      activeTab === 'CLOSED' ? 'bg-slate-800 text-white' : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    {tabCounts.closed}
                  </span>
                </button>
              </div>

              {/* Search & Sort Row */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                <div className="relative flex-1 max-w-md">
                  <SearchIcon size={14} className="absolute left-3.5 top-3 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search by product, offer code, category..."
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
                    <option value="SAVINGS_HIGH">Highest Savings</option>
                    <option value="EXPIRING_SOON">Expiring Soon</option>
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

            {/* Error Message */}
            {error && (
              <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-center text-rose-700 text-xs">
                <AlertTriangleIcon size={24} className="mx-auto mb-2 text-rose-500" />
                <p className="font-bold">{error}</p>
                <button
                  onClick={fetchPriceRequests}
                  className="mt-3 px-4 py-1.5 bg-rose-600 text-white font-semibold rounded-xl text-xs hover:bg-rose-700"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Empty State */}
            {!loading && !error && filteredOffers.length === 0 && (
              <div className="bg-white border border-slate-200 rounded-3xl p-12 text-center shadow-2xs max-w-md mx-auto my-8">
                <div className="w-14 h-14 bg-indigo-50 rounded-2xl flex items-center justify-center text-indigo-600 mx-auto mb-4">
                  <ShoppingBagIcon size={24} />
                </div>
                <h3 className="text-base font-bold text-slate-900 mb-1">No Price Requests Found</h3>
                <p className="text-xs text-slate-500 mb-6">
                  {searchQuery
                    ? 'No requests matched your search query.'
                    : activeTab !== 'ALL'
                    ? `No requests under "${activeTab.replace('_', ' ')}".`
                    : 'You have not submitted any lower-price requests yet. Browse products and click "Ask for Better Price" to negotiate!'}
                </p>
                <Link
                  href="/shopping"
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-slate-900 hover:bg-indigo-600 text-white font-bold text-xs rounded-xl shadow-xs transition-colors"
                >
                  Explore Storefront →
                </Link>
              </div>
            )}

            {/* Offer List */}
            {!loading && !error && filteredOffers.length > 0 && (
              <div className="space-y-4">
                {filteredOffers.map((offer) => (
                  <PriceRequestCard
                    key={offer.id}
                    offer={offer}
                    isProcessing={processingOfferId === offer.id}
                    isPaying={payingOfferId === offer.id}
                    onAccept={() => handleAcceptOffer(offer)}
                    onReject={() => handleRejectOffer(offer)}
                    onPay={() => handleCheckoutAndPay(offer)}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>

      {/* Cart Drawer */}
      <CartDrawer
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        cart={cart}
        onUpdateQuantity={async (productId, newQuantity) => {
          if (!sessionId) return;
          try {
            const res = await apiClient.put(`/cart/items/${productId}?session_id=${sessionId}`, {
              quantity: newQuantity,
            });
            setCart(res.data);
          } catch (err) {
            showToast(extractErrorMessage(err, 'Failed to update item quantity.'), 'error');
          }
        }}
        onRemoveItem={async (productId) => {
          if (!sessionId) return;
          try {
            const res = await apiClient.delete(`/cart/items/${productId}?session_id=${sessionId}`);
            setCart(res.data);
            showToast('Item removed from cart.', 'info');
          } catch (err) {
            showToast(extractErrorMessage(err, 'Failed to remove item.'), 'error');
          }
        }}
        onClearCart={async () => {
          if (!sessionId) return;
          try {
            await apiClient.delete(`/cart?session_id=${sessionId}`);
            setCart({ items: [], total_amount: 0, currency: 'INR' });
            showToast('Cart cleared.', 'info');
          } catch (err) {
            showToast(extractErrorMessage(err, 'Failed to clear cart.'), 'error');
          }
        }}
        onCheckout={() => {
          setIsCartOpen(false);
          router.push('/shopping');
        }}
        updatingCartItemId={null}
      />

      {/* Auth Modal */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        authConfig={authConfig}
        onSuccess={handleAuthSuccess}
      />

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

// ----------------------------------------------------------------------
// Dedicated Price Request Card Component
// ----------------------------------------------------------------------

interface PriceRequestCardProps {
  offer: NegotiatedOfferRecord;
  isProcessing: boolean;
  isPaying: boolean;
  onAccept: () => void;
  onReject: () => void;
  onPay: () => void;
}

function PriceRequestCard({
  offer,
  isProcessing,
  isPaying,
  onAccept,
  onReject,
  onPay,
}: PriceRequestCardProps) {
  // Live Countdown calculation
  const [secondsRemaining, setSecondsRemaining] = useState<number>(() => {
    if (!offer.expires_at) return 0;
    const exp = new Date(offer.expires_at).getTime();
    const now = new Date().getTime();
    return Math.max(0, Math.floor((exp - now) / 1000));
  });

  const isExpired = secondsRemaining <= 0 && offer.status !== 'ORDER_CONFIRMED';

  useEffect(() => {
    if (!offer.expires_at || offer.status === 'ORDER_CONFIRMED') return;
    const timer = setInterval(() => {
      const exp = new Date(offer.expires_at).getTime();
      const now = new Date().getTime();
      const diff = Math.max(0, Math.floor((exp - now) / 1000));
      setSecondsRemaining(diff);
    }, 1000);
    return () => clearInterval(timer);
  }, [offer.expires_at, offer.status]);

  const formatCountdown = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const s = secs % 60;
    return `${mins}m ${s < 10 ? '0' : ''}${s}s`;
  };

  // Status mapping
  const renderStatusBadge = () => {
    if (offer.status === 'ORDER_CONFIRMED' || offer.payment_status === 'CAPTURED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
          <span>✓</span>
          <span>PURCHASED</span>
        </span>
      );
    }
    if (isExpired || offer.status === 'EXPIRED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-600 border border-slate-300">
          <span>⚪</span>
          <span>OFFER EXPIRED</span>
        </span>
      );
    }
    if (offer.status === 'REJECTED' || offer.status === 'CUSTOMER_REJECTED' || offer.status === 'MERCHANT_REJECTED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
          <span>🔴</span>
          <span>REQUEST DECLINED</span>
        </span>
      );
    }
    if (offer.status === 'COUNTER_OFFERED' || offer.status === 'MERCHANT_COUNTERED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300 animate-pulse">
          <span>🟡</span>
          <span>COUNTER OFFER</span>
        </span>
      );
    }
    if (offer.status === 'MERCHANT_APPROVED' || offer.status === 'AUTO_ACCEPTED' || offer.status === 'CUSTOMER_OFFER_PRESENTED') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
          <span>🟢</span>
          <span>PRICE APPROVED</span>
        </span>
      );
    }
    if (offer.status === 'CUSTOMER_ACCEPTED' || offer.status === 'PAYMENT_PENDING') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-300">
          <span>💳</span>
          <span>PAYMENT PENDING</span>
        </span>
      );
    }
    if (offer.status === 'HUMAN_APPROVAL_REQUIRED' || offer.status === 'WAITING_FOR_MERCHANT' || offer.status === 'PENDING') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-900 border border-amber-300">
          <span>🟠</span>
          <span>WAITING FOR MERCHANT</span>
        </span>
      );
    }
    return (
      <Badge variant="neutral" size="sm">
        {offer.status}
      </Badge>
    );
  };

  const isCounterOffer =
    offer.status === 'COUNTER_OFFERED' || offer.status === 'MERCHANT_COUNTERED';
  const isApproved =
    offer.status === 'MERCHANT_APPROVED' ||
    offer.status === 'AUTO_ACCEPTED' ||
    offer.status === 'CUSTOMER_OFFER_PRESENTED';
  const isAcceptedOrPendingPayment =
    offer.status === 'CUSTOMER_ACCEPTED' || offer.status === 'PAYMENT_PENDING';
  const isConfirmed =
    offer.status === 'ORDER_CONFIRMED' || offer.payment_status === 'CAPTURED';

  const requestedDiscountPct = offer.list_total > 0 && offer.requested_total > 0
    ? Math.max(0, ((offer.list_total - offer.requested_total) / offer.list_total) * 100)
    : 0;

  return (
    <div
      className={`bg-white border rounded-2xl p-5 sm:p-6 transition-all shadow-2xs hover:shadow-md ${
        offer.is_actionable && !isExpired
          ? 'border-indigo-300 ring-1 ring-indigo-500/10'
          : 'border-slate-200'
      }`}
    >
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        {/* Left Section: Image + Product Info */}
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
              {renderStatusBadge()}
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
              <span>Qty: <strong className="text-slate-800">{offer.quantity} unit{offer.quantity > 1 ? 's' : ''}</strong></span>
              <span>Requested on: {new Date(offer.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
              {offer.is_actionable && !isExpired && (
                <span className="flex items-center gap-1 font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-md">
                  <ClockIcon size={12} />
                  <span>Expires in {formatCountdown(secondsRemaining)}</span>
                </span>
              )}
            </div>

            {/* Negotiation Comparison Pills */}
            <div className="pt-1 flex flex-wrap items-center gap-2 text-xs">
              <div className="bg-slate-100 text-slate-700 px-2.5 py-1 rounded-lg">
                <span className="text-[10px] text-slate-500 block">List Total</span>
                <span className="font-bold">₹{Number(offer.list_total).toLocaleString('en-IN')}</span>
              </div>
              <div className="bg-amber-50 border border-amber-200 text-amber-900 px-2.5 py-1 rounded-lg">
                <span className="text-[10px] text-amber-600 block">Your Request</span>
                <span className="font-bold">₹{Number(offer.requested_total).toLocaleString('en-IN')}</span>
                {requestedDiscountPct > 0 && (
                  <span className="text-[10px] text-amber-700 ml-1 font-semibold">({requestedDiscountPct.toFixed(0)}% off)</span>
                )}
              </div>
              {isCounterOffer && (
                <div className="bg-indigo-50 border border-indigo-200 text-indigo-900 px-2.5 py-1 rounded-lg">
                  <span className="text-[10px] text-indigo-600 block">Merchant Counter Offer</span>
                  <span className="font-bold">₹{Number(offer.final_total).toLocaleString('en-IN')}</span>
                  <span className="text-[10px] text-indigo-700 ml-1 font-semibold">({Number(offer.discount_percent).toFixed(0)}% off)</span>
                </div>
              )}
            </div>

            {/* Merchant / Agent Reason Note */}
            {offer.reason && (
              <div className="mt-2 text-xs bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-700 flex items-start gap-2">
                <span className="text-indigo-600 shrink-0 font-bold">💬 Note:</span>
                <p className="italic">{offer.reason}</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Section: Pricing Summary & Contextual Action Buttons */}
        <div className="flex flex-col sm:flex-row lg:flex-col items-start sm:items-center lg:items-end justify-between lg:justify-center gap-4 pt-4 lg:pt-0 border-t lg:border-t-0 border-slate-100 shrink-0">
          {/* Price Breakdown */}
          <div className="text-left lg:text-right space-y-1">
            <div className="flex items-baseline gap-2 lg:justify-end">
              <span className="text-xs text-slate-400 line-through">
                ₹{Number(offer.list_total).toLocaleString('en-IN')}
              </span>
              <span className="text-lg sm:text-xl font-extrabold text-slate-900">
                ₹{Number(offer.final_total).toLocaleString('en-IN')}
              </span>
            </div>

            <div className="flex items-center gap-1.5 lg:justify-end">
              <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md">
                Save ₹{Number(offer.discount_amount).toLocaleString('en-IN')} ({Number(offer.discount_percent).toFixed(1)}% OFF)
              </span>
            </div>

            <p className="text-[10px] text-slate-400">
              ₹{Number(offer.offered_unit_price).toLocaleString('en-IN')} / unit • Incl. all taxes
            </p>
          </div>

          {/* Contextual Actions */}
          <div className="flex flex-wrap items-center gap-2">
            {/* 1. Counter Offer Pending Approval by Customer */}
            {isCounterOffer && !isExpired && (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={onAccept}
                  disabled={isProcessing}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs"
                >
                  {isProcessing ? 'Accepting...' : 'ACCEPT COUNTER OFFER'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onReject}
                  disabled={isProcessing}
                  className="text-rose-600 border-rose-200 hover:bg-rose-50 font-bold text-xs"
                >
                  DECLINE
                </Button>
              </>
            )}

            {/* 2. Approved / Accepted -> 1-Click Razorpay Checkout */}
            {(isApproved || isAcceptedOrPendingPayment) && !isExpired && (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={onPay}
                  disabled={isPaying}
                  leftIcon={<ShieldCheckIcon size={14} />}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-xs"
                >
                  {isPaying ? 'Launching Payment...' : `PROCEED TO CHECKOUT • ₹${Number(offer.final_total).toLocaleString('en-IN')}`}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onReject}
                  disabled={isPaying}
                  className="text-slate-500 border-slate-200 hover:bg-slate-50 text-xs"
                >
                  Cancel
                </Button>
              </>
            )}

            {/* 3. Confirmed & Paid */}
            {isConfirmed && (
              <Link
                href="/orders"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-slate-900 hover:bg-indigo-600 text-white text-xs font-bold transition-colors shadow-xs"
              >
                <span>View Order →</span>
              </Link>
            )}

            {/* 4. In Review */}
            {(offer.status === 'HUMAN_APPROVAL_REQUIRED' || offer.status === 'WAITING_FOR_MERCHANT' || offer.status === 'PENDING') && (
              <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-xl font-semibold flex items-center gap-1.5">
                <ClockIcon size={12} />
                <span>Waiting for merchant review</span>
              </div>
            )}

            {/* 5. Closed / Expired -> Shop Product */}
            {(isExpired || offer.status === 'REJECTED' || offer.status === 'CUSTOMER_REJECTED' || offer.status === 'MERCHANT_REJECTED' || offer.status === 'EXPIRED') && (
              <Link
                href={`/shopping?product_id=${offer.product_id}`}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-colors"
              >
                <span>Shop Product</span>
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
