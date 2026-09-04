'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { apiClient, extractErrorMessage } from '@/lib/api';
import { StorefrontHeader, UserProfile } from '@/components/storefront/StorefrontHeader';
import { CartDrawer, CartData } from '@/components/storefront/CartDrawer';
import { AuthModal, AuthConfig } from '@/components/auth/AuthModal';
import { OrderInvoiceModal } from '@/components/orders/OrderInvoiceModal';
import { OrderData, BuyAgainResult } from '@/lib/types/orders';
import { ProductImage } from '@/components/ui/ProductImage';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  CheckCircleIcon,
  MapPinIcon,
  ReceiptIcon,
  RotateCcwIcon,
  ClockIcon,
  ShieldCheckIcon,
} from '@/components/ui/Icons';

export default function OrderTrackingPage() {
  const params = useParams();
  const router = useRouter();
  const orderId = params?.id as string;

  const [order, setOrder] = useState<OrderData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // User & Auth State
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // Cart State
  const [sessionId, setSessionId] = useState<string>('');
  const [cart, setCart] = useState<CartData>({ items: [], total_amount: 0, currency: 'INR' });
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isInvoiceOpen, setIsInvoiceOpen] = useState(false);

  // Modals for Cancel / Return
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [cancelReason, setCancelReason] = useState('Ordered wrong item');
  const [showReturnDialog, setShowReturnDialog] = useState(false);
  const [returnReason, setReturnReason] = useState('Size did not fit');

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
        // Ignore
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

  // 3. Fetch Order by ID
  const fetchOrder = useCallback(async () => {
    if (!orderId) return;
    const token = localStorage.getItem('access_token');
    if (!token) {
      setLoading(false);
      setError('Please sign in to view this order.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get(`/orders/${orderId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setOrder(res.data);
    } catch (err: unknown) {
      console.error('Failed to fetch order details:', err);
      setError(extractErrorMessage(err, 'Failed to load order tracking details.'));
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  // 4. Buy Again Handler
  const handleBuyAgain = async () => {
    if (!sessionId || !order) return;
    setActionLoading(true);
    setActionMessage(null);
    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await apiClient.post<BuyAgainResult>(
        `/orders/${order.id}/buy-again`,
        { session_id: sessionId },
        { headers }
      );
      if (res.data.cart) {
        setCart(res.data.cart);
      }
      setActionMessage({ text: res.data.message, type: 'success' });
      setIsCartOpen(true);
    } catch (err: unknown) {
      setActionMessage({
        text: extractErrorMessage(err, 'Could not re-order items.'),
        type: 'error',
      });
    } finally {
      setActionLoading(false);
    }
  };

  // 5. Cancel Order Handler
  const handleCancelOrder = async () => {
    if (!order) return;
    setActionLoading(true);
    setActionMessage(null);
    try {
      const token = localStorage.getItem('access_token');
      const res = await apiClient.post(
        `/orders/${order.id}/cancel`,
        { reason: cancelReason },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setShowCancelDialog(false);
      setActionMessage({ text: res.data.message, type: 'success' });
      fetchOrder();
    } catch (err: unknown) {
      setActionMessage({
        text: extractErrorMessage(err, 'Failed to cancel order.'),
        type: 'error',
      });
    } finally {
      setActionLoading(false);
    }
  };

  // 6. Return Request Handler
  const handleReturnOrder = async () => {
    if (!order) return;
    setActionLoading(true);
    setActionMessage(null);
    try {
      const token = localStorage.getItem('access_token');
      const res = await apiClient.post(
        `/orders/${order.id}/return`,
        { reason: returnReason, quantity: 1 },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setShowReturnDialog(false);
      setActionMessage({ text: res.data.message, type: 'success' });
      fetchOrder();
    } catch (err: unknown) {
      setActionMessage({
        text: extractErrorMessage(err, 'Failed to submit return request.'),
        type: 'error',
      });
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 pb-16">
      <StorefrontHeader
        cartItemCount={cart.items.reduce((sum, item) => sum + item.quantity, 0)}
        onOpenCart={() => setIsCartOpen(true)}
        onOpenAI={() => router.push('/shopping')}
        onOpenAuth={() => setIsAuthOpen(true)}
        onSignOut={() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('user_profile');
          setUserProfile(null);
          router.push('/');
        }}
        searchQuery=""
        onSearchChange={() => {}}
        userProfile={userProfile}
      />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 space-y-6">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
            <Link href="/shopping" className="hover:text-slate-900 transition-colors">
              Storefront
            </Link>
            <span>/</span>
            <Link href="/orders" className="hover:text-slate-900 transition-colors">
              My Orders
            </Link>
            <span>/</span>
            <span className="text-slate-900 font-bold">
              {order ? `#${order.order_number}` : 'Order Tracking'}
            </span>
          </div>

          <Link href="/orders">
            <Button variant="secondary" size="sm">
              ← Back to Orders
            </Button>
          </Link>
        </div>

        {/* Action Toast Alert */}
        {actionMessage && (
          <div
            className={`p-4 rounded-xl text-xs font-semibold flex items-center justify-between ${
              actionMessage.type === 'success'
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                : 'bg-rose-50 text-rose-800 border border-rose-200'
            }`}
          >
            <span>{actionMessage.text}</span>
            <button onClick={() => setActionMessage(null)} className="text-slate-400 hover:text-slate-600">
              ✕
            </button>
          </div>
        )}

        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center gap-3">
            <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs text-slate-500 font-semibold">Loading real-time order tracking...</span>
          </div>
        ) : error || !order ? (
          <div className="p-8 rounded-2xl bg-white border border-slate-200 text-center space-y-4 shadow-sm">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 border border-rose-200 text-rose-600 mx-auto flex items-center justify-center text-xl">
              ⚠️
            </div>
            <h3 className="text-base font-bold text-slate-900">{error || 'Order Not Found'}</h3>
            <div className="flex justify-center gap-3 pt-2">
              <Link href="/orders">
                <Button variant="primary" size="sm">
                  View All Orders
                </Button>
              </Link>
              <Link href="/shopping">
                <Button variant="secondary" size="sm">
                  Go to Storefront
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Order Tracking Header Card */}
            <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-xl font-extrabold text-slate-900">
                      Order #{order.order_number}
                    </h1>
                    <Badge
                      variant={
                        order.status === 'CONFIRMED'
                          ? 'success'
                          : order.status === 'PROCESSING'
                          ? 'warning'
                          : order.status === 'CANCELLED'
                          ? 'error'
                          : 'neutral'
                      }
                      size="sm"
                    >
                      {order.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Placed on {new Date(order.created_at).toLocaleDateString('en-IN', {
                      day: 'numeric',
                      month: 'long',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setIsInvoiceOpen(true)}
                    leftIcon={<ReceiptIcon size={14} />}
                  >
                    Print Invoice
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleBuyAgain}
                    isLoading={actionLoading}
                    leftIcon={<RotateCcwIcon size={14} />}
                  >
                    Buy Again
                  </Button>
                </div>
              </div>

              {/* Real-time Order Tracking Stepper */}
              <div className="pt-4 border-t border-slate-100">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-1.5">
                  <ClockIcon size={13} className="text-indigo-600" />
                  <span>Real-Time Shipment Progress</span>
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                  {[
                    { key: 'placed', title: '1. Order Placed', desc: 'Verified & Confirmed', done: true },
                    { key: 'pay', title: '2. Payment Captured', desc: 'Razorpay Verified', done: order.payment.status === 'VERIFIED' || order.status === 'CONFIRMED' },
                    { key: 'pack', title: '3. Packed & Dispatched', desc: 'Warehouse Logistics', done: order.status === 'CONFIRMED' },
                    { key: 'deliver', title: '4. Delivered', desc: 'Expected in 2-3 Days', done: order.status === 'DELIVERED' },
                  ].map((step, idx) => (
                    <div
                      key={idx}
                      className={`p-3.5 rounded-xl border transition-all ${
                        step.done
                          ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                          : 'bg-slate-50 border-slate-200 text-slate-400'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {step.done ? (
                          <CheckCircleIcon size={14} className="text-emerald-600" />
                        ) : (
                          <span className="w-3.5 h-3.5 rounded-full border border-slate-300" />
                        )}
                        <span className="text-xs font-bold">{step.title}</span>
                      </div>
                      <span className="text-[11px] opacity-80 pl-5">{step.desc}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Products & Delivery Information */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Products List */}
              <div className="md:col-span-2 space-y-4">
                <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Order Items ({order.items.length})
                  </h3>

                  <div className="divide-y divide-slate-100">
                    {order.items.map((item, idx) => (
                      <div key={idx} className="py-3 flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <div className="w-14 h-14 rounded-xl bg-slate-100 border border-slate-200 overflow-hidden flex items-center justify-center shrink-0">
                            <ProductImage
                              src={item.image_url}
                              alt={item.name}
                              productName={item.name}
                              category={item.category}
                              className="w-full h-full object-cover"
                              containerClassName="w-full h-full"
                            />
                          </div>
                          <div>
                            <h4 className="text-xs font-bold text-slate-900">{item.name}</h4>
                            <span className="text-[11px] text-slate-500">{item.category}</span>
                            <div className="text-[11px] text-slate-600 mt-0.5">
                              Qty: <span className="font-semibold">{item.quantity}</span> × ₹
                              {Number(item.unit_price).toLocaleString('en-IN')}
                            </div>
                          </div>
                        </div>

                        <span className="text-xs font-bold font-mono text-slate-900">
                          ₹{Number(item.subtotal).toLocaleString('en-IN')}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Customer Order Management Actions */}
                  <div className="pt-4 border-t border-slate-100 flex flex-wrap gap-2 justify-end">
                    {order.status !== 'CANCELLED' && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setShowCancelDialog(true)}
                        className="text-rose-600 hover:bg-rose-50 border-rose-200"
                      >
                        Cancel Order
                      </Button>
                    )}

                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setShowReturnDialog(true)}
                    >
                      Request Return
                    </Button>
                  </div>
                </div>
              </div>

              {/* Delivery & Financial Summary Sidebar */}
              <div className="space-y-4">
                {/* Delivery Address */}
                <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm text-xs space-y-2">
                  <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider text-slate-500 text-[11px]">
                    <MapPinIcon size={13} className="text-indigo-600" />
                    <span>Delivery Address</span>
                  </div>
                  {order.delivery_address ? (
                    <div className="space-y-0.5 text-slate-800">
                      <div className="font-bold text-slate-900">{order.delivery_address.full_name}</div>
                      <div>{order.delivery_address.address_line1}</div>
                      {order.delivery_address.address_line2 && <div>{order.delivery_address.address_line2}</div>}
                      <div>
                        {order.delivery_address.city}, {order.delivery_address.state} -{' '}
                        {order.delivery_address.pin_code}
                      </div>
                      <div className="pt-1 text-slate-600">Ph: +91 {order.delivery_address.phone}</div>
                    </div>
                  ) : (
                    <p className="text-slate-400">Address recorded on customer profile</p>
                  )}
                </div>

                {/* Financial Breakdown */}
                <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-sm text-xs space-y-2.5">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    Payment Breakdown
                  </div>

                  <div className="flex justify-between text-slate-600">
                    <span>Subtotal:</span>
                    <span className="font-mono">₹{Number(order.price_summary.subtotal).toLocaleString('en-IN')}</span>
                  </div>

                  {Number(order.price_summary.coupon_discount) > 0 && (
                    <div className="flex justify-between text-emerald-700">
                      <span>Coupon Discount:</span>
                      <span className="font-mono">-₹{Number(order.price_summary.coupon_discount).toLocaleString('en-IN')}</span>
                    </div>
                  )}

                  {Number(order.price_summary.coin_discount) > 0 && (
                    <div className="flex justify-between text-amber-700">
                      <span>Apex Coins:</span>
                      <span className="font-mono">-₹{Number(order.price_summary.coin_discount).toLocaleString('en-IN')}</span>
                    </div>
                  )}

                  <div className="flex justify-between text-slate-600">
                    <span>Shipping Fee:</span>
                    <span className="font-semibold text-emerald-700">FREE</span>
                  </div>

                  <div className="pt-2 border-t border-slate-100 flex justify-between text-sm font-bold text-slate-900">
                    <span>Total Paid:</span>
                    <span className="font-mono text-indigo-700">
                      ₹{Number(order.total_amount).toLocaleString('en-IN')}
                    </span>
                  </div>

                  <div className="pt-2 text-[10px] text-slate-400 flex items-center gap-1">
                    <ShieldCheckIcon size={12} className="text-emerald-600" />
                    <span>Razorpay Verified • Test Mode</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Cancel Order Dialog */}
      {showCancelDialog && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full border border-slate-200 shadow-xl space-y-4">
            <h3 className="text-base font-bold text-slate-900">Cancel Order #{order?.order_number}</h3>
            <p className="text-xs text-slate-500">
              Are you sure you want to cancel this order? Reserved stock will be restored and payment refunded.
            </p>

            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">Reason for Cancellation</label>
              <select
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                className="w-full text-xs p-2.5 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white"
              >
                <option value="Ordered wrong item">Ordered wrong item</option>
                <option value="Found better price">Found better price elsewhere</option>
                <option value="Change of delivery address">Change of delivery address</option>
                <option value="Delay in processing">Delay in processing</option>
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" size="sm" onClick={() => setShowCancelDialog(false)}>
                Nevermind
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleCancelOrder}
                isLoading={actionLoading}
                className="bg-rose-600 hover:bg-rose-700 text-white"
              >
                Confirm Cancellation
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Return Order Dialog */}
      {showReturnDialog && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full border border-slate-200 shadow-xl space-y-4">
            <h3 className="text-base font-bold text-slate-900">Request Return for #{order?.order_number}</h3>
            <p className="text-xs text-slate-500">
              Please specify the reason for your return. Our courier partner will schedule pickup within 24-48 business hours.
            </p>

            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">Reason for Return</label>
              <select
                value={returnReason}
                onChange={(e) => setReturnReason(e.target.value)}
                className="w-full text-xs p-2.5 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white"
              >
                <option value="Size did not fit">Size did not fit</option>
                <option value="Item defective or damaged">Item defective or damaged</option>
                <option value="Not as described">Product not as described</option>
                <option value="No longer needed">No longer needed</option>
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" size="sm" onClick={() => setShowReturnDialog(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleReturnOrder}
                isLoading={actionLoading}
              >
                Submit Return Request
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Modals */}
      <CartDrawer
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        cart={cart}
        onUpdateQuantity={async (productId, quantity) => {
          if (quantity <= 0) {
            await apiClient.delete(`/cart/items/${productId}?session_id=${sessionId}`);
          } else {
            await apiClient.post(`/cart/items?session_id=${sessionId}`, {
              product_id: productId,
              quantity
            });
          }
          await fetchCart();
        }}
        onRemoveItem={async (productId) => {
          await apiClient.delete(`/cart/items/${productId}?session_id=${sessionId}`);
          await fetchCart();
        }}
        onClearCart={async () => {
          await apiClient.delete(`/cart?session_id=${sessionId}`);
          await fetchCart();
        }}
        onCheckout={() => {
          setIsCartOpen(false);
          router.push('/shopping');
        }}
        updatingCartItemId={null}
      />

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        authConfig={authConfig}
        onSuccess={(profile) => {
          setUserProfile(profile);
          fetchOrder();
        }}
      />

      {order && (
        <OrderInvoiceModal
          isOpen={isInvoiceOpen}
          onClose={() => setIsInvoiceOpen(false)}
          order={order}
        />
      )}
    </div>
  );
}
