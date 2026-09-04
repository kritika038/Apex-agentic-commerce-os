'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { apiClient, extractErrorMessage } from '@/lib/api';
import { StorefrontHeader, UserProfile } from '@/components/storefront/StorefrontHeader';
import { CartDrawer, CartData } from '@/components/storefront/CartDrawer';
import { AuthModal, AuthConfig } from '@/components/auth/AuthModal';
import { OrderCard } from '@/components/orders/OrderCard';
import { OrderDetailsModal } from '@/components/orders/OrderDetailsModal';
import { OrderInvoiceModal } from '@/components/orders/OrderInvoiceModal';
import { OrderData, BuyAgainResult } from '@/lib/types/orders';
import { Button } from '@/components/ui/Button';
import { SearchIcon, PackageIcon, AlertTriangleIcon } from '@/components/ui/Icons';

type OrderFilter = 'ALL' | 'CONFIRMED' | 'PROCESSING' | 'FAILED';
type OrderSort = 'NEWEST' | 'OLDEST' | 'PRICE_HIGH' | 'PRICE_LOW';

export default function OrdersPage() {
  const router = useRouter();

  // State Management
  const [orders, setOrders] = useState<OrderData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Search & Sort
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<OrderFilter>('ALL');
  const [activeSort, setActiveSort] = useState<OrderSort>('NEWEST');

  // User & Auth State
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // Cart State
  const [sessionId, setSessionId] = useState<string>('');
  const [cart, setCart] = useState<CartData>({ items: [], total_amount: 0, currency: 'INR' });
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [reorderingOrderId, setReorderingOrderId] = useState<string | null>(null);

  // Modals
  const [selectedOrder, setSelectedOrder] = useState<OrderData | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [invoiceOrder, setInvoiceOrder] = useState<OrderData | null>(null);
  const [isInvoiceOpen, setIsInvoiceOpen] = useState(false);

  // Toast Notification
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // 1. Initialize Session & Auth
  useEffect(() => {
    let sId = localStorage.getItem('shopping_session_id');
    if (!sId) {
      sId = `sess_${Math.random().toString(36).substring(2, 10)}_${Date.now()}`;
      localStorage.setItem('shopping_session_id', sId);
    }
    setSessionId(sId);

    const savedProfile = localStorage.getItem('user_profile');
    if (savedProfile) {
      try {
        setUserProfile(JSON.parse(savedProfile));
      } catch {
        // Ignore parse error
      }
    }

    const fetchAuthConfig = async () => {
      try {
        const res = await apiClient.get('/auth/config');
        setAuthConfig(res.data);
      } catch (err) {
        console.error('Failed to fetch auth configuration:', err);
      }
    };
    fetchAuthConfig();
  }, []);

  // 2. Fetch User's Cart
  const fetchCart = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await apiClient.get(`/cart?session_id=${sessionId}`);
      setCart(res.data);
    } catch (err) {
      console.error('Cart fetch failed:', err);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId) {
      fetchCart();
    }
  }, [sessionId, fetchCart]);

  // 3. Fetch Customer Orders
  const fetchOrders = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get('/orders/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setOrders(res.data || []);
    } catch (err: unknown) {
      console.error('Failed to fetch orders:', err);
      setError(extractErrorMessage(err, 'Failed to load your orders. Please try again.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders, userProfile]);

  // 4. Buy Again Handler
  const handleBuyAgain = async (orderId: string) => {
    if (!sessionId) return;
    setReorderingOrderId(orderId);

    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      const res = await apiClient.post<BuyAgainResult>(
        `/orders/${orderId}/buy-again`,
        { session_id: sessionId },
        { headers }
      );

      const result = res.data;
      if (result.success) {
        setCart(result.cart);
        showToast(result.message, 'success');
        setIsCartOpen(true);
      } else {
        showToast(result.message || 'Could not reorder items.', 'error');
      }
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Could not reorder items from this order.'), 'error');
    } finally {
      setReorderingOrderId(null);
    }
  };

  // 5. Auth Success
  const handleAuthSuccess = (user: UserProfile) => {
    setUserProfile(user);
    showToast(`Welcome back, ${user.full_name}!`, 'success');
    fetchOrders();
  };

  const handleSignOut = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_profile');
    setUserProfile(null);
    setOrders([]);
    showToast('Signed out successfully.', 'info');
  };

  // 6. Filter & Search & Sort Orders
  const filteredOrders = useMemo(() => {
    let list = [...orders];

    // Status Filter
    if (activeFilter !== 'ALL') {
      list = list.filter((o) => o.status === activeFilter);
    }

    // Search Query (Matches Order Number or Product Name)
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(
        (o) =>
          o.order_number.toLowerCase().includes(q) ||
          o.items.some((it) => it.name.toLowerCase().includes(q) || (it.category && it.category.toLowerCase().includes(q)))
      );
    }

    // Sort
    list.sort((a, b) => {
      switch (activeSort) {
        case 'NEWEST':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case 'OLDEST':
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        case 'PRICE_HIGH':
          return Number(b.total_amount) - Number(a.total_amount);
        case 'PRICE_LOW':
          return Number(a.total_amount) - Number(b.total_amount);
        default:
          return 0;
      }
    });

    return list;
  }, [orders, activeFilter, searchQuery, activeSort]);

  const totalItemCount = (cart.items || []).reduce((acc, it) => acc + it.quantity, 0);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl shadow-lg border text-xs font-semibold flex items-center gap-2 animate-in slide-in-from-bottom-2 ${
            toast.type === 'success'
              ? 'bg-emerald-900 text-white border-emerald-800'
              : toast.type === 'error'
              ? 'bg-rose-900 text-white border-rose-800'
              : 'bg-slate-900 text-white border-slate-800'
          }`}
        >
          <span>{toast.message}</span>
        </div>
      )}

      {/* Global Storefront Header */}
      <StorefrontHeader
        searchQuery=""
        onSearchChange={() => {}}
        cartItemCount={totalItemCount}
        onOpenCart={() => setIsCartOpen(true)}
        onOpenAI={() => router.push('/shopping')}
        userProfile={userProfile}
        onOpenAuth={() => setIsAuthOpen(true)}
        onSignOut={handleSignOut}
      />

      {/* Main Order Content */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Breadcrumb & Navigation */}
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Link href="/shopping" className="hover:text-slate-900 transition-colors">
            Storefront
          </Link>
          <span>/</span>
          <span className="font-semibold text-slate-900">My Orders</span>
        </div>

        {/* Page Title & Subtitle */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
              My Orders
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 mt-1">
              View and manage your recent purchases and delivery updates.
            </p>
          </div>
          <Link href="/shopping">
            <Button variant="secondary" size="sm">
              Continue Shopping
            </Button>
          </Link>
        </div>

        {/* Unauthenticated Prompt */}
        {!userProfile && !loading && (
          <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center space-y-4 shadow-2xs">
            <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 mx-auto flex items-center justify-center text-xl">
              <PackageIcon size={24} />
            </div>
            <div className="max-w-md mx-auto space-y-1">
              <h3 className="text-base font-bold text-slate-900">Sign in to view your orders</h3>
              <p className="text-xs text-slate-500">
                Track previous purchases, download invoices, and reorder your favorite athletic gear.
              </p>
            </div>
            <Button variant="primary" size="md" onClick={() => setIsAuthOpen(true)}>
              Sign In to Your Account
            </Button>
          </div>
        )}

        {/* Authenticated Customer View */}
        {(userProfile || loading) && (
          <>
            {/* Search, Filter Tabs & Sort Controls */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              {/* Status Filter Chips */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                {(
                  [
                    { key: 'ALL', label: 'All Orders' },
                    { key: 'CONFIRMED', label: 'Confirmed' },
                    { key: 'PROCESSING', label: 'Processing' },
                    { key: 'FAILED', label: 'Failed' },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveFilter(tab.key)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors shrink-0 ${
                      activeFilter === tab.key
                        ? 'bg-slate-900 text-white shadow-2xs'
                        : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Search Bar & Sort Dropdown */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                <div className="relative flex-1 sm:w-60">
                  <SearchIcon size={14} className="absolute left-3 top-2.5 text-slate-400 pointer-events-none" />
                  <input
                    type="text"
                    placeholder="Search by order or product..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-white text-slate-900 border border-slate-200 rounded-xl pl-9 pr-3 py-1.5 text-xs placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="absolute right-2.5 top-2 text-xs text-slate-400 hover:text-slate-600"
                    >
                      ✕
                    </button>
                  )}
                </div>

                <select
                  value={activeSort}
                  onChange={(e) => setActiveSort(e.target.value as OrderSort)}
                  className="bg-white text-slate-700 border border-slate-200 rounded-xl px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="NEWEST">Newest First</option>
                  <option value="OLDEST">Oldest First</option>
                  <option value="PRICE_HIGH">Highest Amount</option>
                  <option value="PRICE_LOW">Lowest Amount</option>
                </select>
              </div>
            </div>

            {/* Error Banner */}
            {error && (
              <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
                <AlertTriangleIcon size={16} className="text-rose-600 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Loading Skeletons */}
            {loading && (
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4 animate-pulse">
                    <div className="flex justify-between items-center">
                      <div className="h-4 bg-slate-200 rounded w-1/4" />
                      <div className="h-4 bg-slate-200 rounded w-16" />
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="w-16 h-16 bg-slate-200 rounded-xl shrink-0" />
                      <div className="space-y-2 flex-1">
                        <div className="h-4 bg-slate-200 rounded w-1/2" />
                        <div className="h-3 bg-slate-200 rounded w-1/4" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Empty State */}
            {!loading && filteredOrders.length === 0 && (
              <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center space-y-4 shadow-2xs">
                <div className="w-14 h-14 rounded-2xl bg-slate-100 text-slate-400 mx-auto flex items-center justify-center text-2xl">
                  📦
                </div>
                <div className="max-w-md mx-auto space-y-1">
                  <h3 className="text-base font-bold text-slate-900">
                    {searchQuery || activeFilter !== 'ALL' ? 'No matching orders found' : 'No orders yet'}
                  </h3>
                  <p className="text-xs text-slate-500">
                    {searchQuery || activeFilter !== 'ALL'
                      ? 'Try clearing your search query or filters.'
                      : 'Your completed purchases will appear here with verified Razorpay payment receipts.'}
                  </p>
                </div>
                {searchQuery || activeFilter !== 'ALL' ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setSearchQuery('');
                      setActiveFilter('ALL');
                    }}
                  >
                    Reset Filters
                  </Button>
                ) : (
                  <Link href="/shopping">
                    <Button variant="primary" size="md">
                      Start Shopping
                    </Button>
                  </Link>
                )}
              </div>
            )}

            {/* Orders List */}
            {!loading && filteredOrders.length > 0 && (
              <div className="space-y-4">
                {filteredOrders.map((order) => (
                  <OrderCard
                    key={order.id}
                    order={order}
                    onViewDetails={(ord) => {
                      setSelectedOrder(ord);
                      setIsDetailsOpen(true);
                    }}
                    onBuyAgain={handleBuyAgain}
                    onViewInvoice={(ord) => {
                      setInvoiceOrder(ord);
                      setIsInvoiceOpen(true);
                    }}
                    isReordering={reorderingOrderId === order.id}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>

      {/* Order Details Modal */}
      <OrderDetailsModal
        isOpen={isDetailsOpen}
        onClose={() => {
          setIsDetailsOpen(false);
          setSelectedOrder(null);
        }}
        order={selectedOrder}
        onBuyAgain={handleBuyAgain}
        onOpenInvoice={(ord) => {
          setIsDetailsOpen(false);
          setInvoiceOrder(ord);
          setIsInvoiceOpen(true);
        }}
        isReordering={reorderingOrderId === selectedOrder?.id}
      />

      {/* Official Tax Invoice Modal */}
      <OrderInvoiceModal
        isOpen={isInvoiceOpen}
        onClose={() => {
          setIsInvoiceOpen(false);
          setInvoiceOrder(null);
        }}
        order={invoiceOrder}
      />

      {/* Cart Drawer */}
      <CartDrawer
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        cart={cart}
        onUpdateQuantity={async (productId, newQuantity) => {
          if (!sessionId) return;
          try {
            if (newQuantity <= 0) {
              const res = await apiClient.delete(`/cart/items/${productId}?session_id=${sessionId}`);
              setCart(res.data);
            } else {
              const res = await apiClient.patch(`/cart/items/${productId}?session_id=${sessionId}`, {
                quantity: newQuantity,
                session_id: sessionId,
              });
              setCart(res.data);
            }
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
    </div>
  );
}
