'use client';

import React, { useState, useEffect } from 'react';
import {
  ShoppingBagIcon,
  XIcon,
  PlusIcon,
  MinusIcon,
  TrashIcon,
  ArrowRightIcon,
  TagIcon,
  GiftIcon,
  CoinsIcon,
  AwardIcon,
  CheckCircleIcon,
} from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';
import { Product } from './ProductCard';
import { ProductImage } from '@/components/ui/ProductImage';
import { apiClient, extractErrorMessage } from '@/lib/api';
import { CartPricingBreakdown, CouponData, VoucherData } from '@/lib/types/rewards';

export interface CartItemData {
  product_id: string;
  name?: string;
  quantity: number;
  unit_price: number;
  subtotal: number;
  image_url?: string;
  category?: string;
}

export interface CartData {
  id?: string;
  session_id?: string;
  items: CartItemData[];
  total_amount: number;
  currency?: string;
}

export interface CartDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  cart: CartData;
  onUpdateQuantity: (productId: string, newQuantity: number) => void;
  onRemoveItem: (productId: string) => void;
  onClearCart: () => void;
  onCheckout: () => void;
  updatingCartItemId: string | null;
  catalogProducts?: Product[];
  appliedCoupon?: string | null;
  onApplyCoupon?: (code: string | null) => void;
  appliedVoucher?: string | null;
  onApplyVoucher?: (code: string | null) => void;
  useCoins?: boolean;
  onToggleCoins?: (use: boolean) => void;
  pricingBreakdown?: CartPricingBreakdown | null;
}

export function CartDrawer({
  isOpen,
  onClose,
  cart,
  onUpdateQuantity,
  onRemoveItem,
  onClearCart,
  onCheckout,
  updatingCartItemId,
  catalogProducts = [],
  appliedCoupon = null,
  onApplyCoupon,
  appliedVoucher = null,
  onApplyVoucher,
  useCoins = false,
  onToggleCoins,
  pricingBreakdown = null,
}: CartDrawerProps) {
  const [promoInput, setPromoInput] = useState('');
  const [promoLoading, setPromoLoading] = useState(false);
  const [promoError, setPromoError] = useState<string | null>(null);
  const [availableCoupons, setAvailableCoupons] = useState<CouponData[]>([]);
  const [availableVouchers, setAvailableVouchers] = useState<VoucherData[]>([]);
  const [showVouchers, setShowVouchers] = useState(false);

  // Fetch available public coupons & user rewards
  useEffect(() => {
    if (!isOpen) return;

    const fetchRewardsMeta = async () => {
      try {
        const cRes = await apiClient.get('/rewards/coupons');
        setAvailableCoupons(cRes.data || []);
      } catch {
        // Non-fatal
      }

      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const rRes = await apiClient.get('/rewards/me', {
            headers: { Authorization: `Bearer ${token}` },
          });
          setAvailableVouchers(rRes.data?.available_vouchers || []);
        } catch {
          // Non-fatal
        }
      }
    };

    fetchRewardsMeta();
  }, [isOpen]);

  const handleApplyPromo = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!promoInput.trim() || !cart.session_id) return;

    setPromoLoading(true);
    setPromoError(null);
    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};

      await apiClient.post(
        '/rewards/calculate-pricing',
        {
          session_id: cart.session_id,
          coupon_code: promoInput.trim().toUpperCase(),
          voucher_code: appliedVoucher,
          use_coins: useCoins,
        },
        { headers }
      );

      if (onApplyCoupon) {
        onApplyCoupon(promoInput.trim().toUpperCase());
      }
      setPromoInput('');
    } catch (err: unknown) {
      setPromoError(extractErrorMessage(err, 'Invalid promo code.'));
    } finally {
      setPromoLoading(false);
    }
  };

  const handleRemovePromo = () => {
    if (onApplyCoupon) {
      onApplyCoupon(null);
    }
    setPromoError(null);
  };

  const handleSelectVoucher = (code: string) => {
    if (appliedVoucher === code) {
      if (onApplyVoucher) onApplyVoucher(null);
    } else {
      if (onApplyVoucher) onApplyVoucher(code);
    }
  };

  if (!isOpen) return null;

  const totalItemCount = cart.items.reduce((sum, item) => sum + item.quantity, 0);

  // Authoritative Pricing display
  const subtotal = pricingBreakdown?.subtotal ?? Number(cart.total_amount);
  const couponDiscount = pricingBreakdown?.coupon_discount ?? 0;
  const voucherDiscount = pricingBreakdown?.voucher_discount ?? 0;
  const coinDiscount = pricingBreakdown?.coin_discount ?? 0;
  const finalTotal = pricingBreakdown?.total ?? Number(cart.total_amount);
  const pointsToEarn = pricingBreakdown?.points_to_earn ?? Math.floor(finalTotal / 100);
  const coinBalance = pricingBreakdown?.available_coin_balance ?? 0;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Drawer Container */}
      <div className="relative w-full max-w-md bg-white border-l border-slate-200 h-full shadow-2xl flex flex-col justify-between z-10 animate-in slide-in-from-right duration-250 text-slate-900">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-white">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-slate-100 flex items-center justify-center text-slate-700">
              <ShoppingBagIcon size={16} />
            </div>
            <div>
              <h3 className="font-bold text-base text-slate-900 leading-none">
                Your Shopping Cart
              </h3>
              <p className="text-xs text-slate-500 font-normal mt-0.5">
                {totalItemCount} {totalItemCount === 1 ? 'item' : 'items'} in cart
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            aria-label="Close cart"
          >
            <XIcon size={16} />
          </button>
        </div>

        {/* Item List & Rewards Container */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50">
          {cart.items.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-white border border-slate-200 flex items-center justify-center text-2xl text-slate-400 shadow-xs">
                🛒
              </div>
              <div className="space-y-1">
                <h4 className="font-bold text-sm text-slate-900">Your cart is empty</h4>
                <p className="text-xs text-slate-500 max-w-xs">
                  Discover verified athletic gear in the store or ask the AI Shopping Assistant for tailored picks.
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Product Items */}
              <div className="space-y-3">
                {cart.items.map((item) => {
                  const catalogProduct = catalogProducts.find((p) => p.id === item.product_id);
                  const isUpdating = updatingCartItemId === item.product_id;

                  return (
                    <div
                      key={item.product_id}
                      className="bg-white p-3.5 rounded-2xl border border-slate-200 shadow-2xs flex items-center gap-3.5 transition-all"
                    >
                      {/* Thumbnail */}
                      <div className="w-16 h-16 rounded-xl bg-slate-100 border border-slate-100 overflow-hidden shrink-0 flex items-center justify-center">
                        <ProductImage
                          src={item.image_url || catalogProduct?.image_url}
                          alt={item.name || catalogProduct?.name || 'Product'}
                          productId={item.product_id}
                          productName={item.name || catalogProduct?.name}
                          category={item.category || catalogProduct?.category}
                          subcategory={catalogProduct?.subcategory}
                          className="w-full h-full object-cover"
                          containerClassName="w-full h-full"
                        />
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <h4 className="text-xs font-bold text-slate-900 truncate">
                          {item.name || catalogProduct?.name || 'Athletic Product'}
                        </h4>
                        <span className="text-[11px] text-slate-400 font-medium">
                          {item.category || catalogProduct?.category || 'Gear'}
                        </span>
                        <div className="text-xs font-mono font-bold text-slate-900 mt-1">
                          ₹{Number(item.unit_price).toLocaleString('en-IN')}
                        </div>
                      </div>

                      {/* Quantity Controls */}
                      <div className="flex items-center gap-1 bg-slate-50 p-1 rounded-xl border border-slate-200/80 shrink-0">
                        <button
                          onClick={() => onUpdateQuantity(item.product_id, item.quantity - 1)}
                          disabled={isUpdating}
                          className="w-6 h-6 rounded-lg bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 flex items-center justify-center transition-colors disabled:opacity-50"
                          title="Decrease quantity"
                          aria-label="Decrease quantity"
                        >
                          <MinusIcon size={12} />
                        </button>

                        <span className="w-6 text-center text-xs font-bold text-slate-900">
                          {item.quantity}
                        </span>

                        <button
                          onClick={() => onUpdateQuantity(item.product_id, item.quantity + 1)}
                          disabled={isUpdating}
                          className="w-6 h-6 rounded-lg bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 flex items-center justify-center transition-colors disabled:opacity-50"
                          title="Increase quantity"
                          aria-label="Increase quantity"
                        >
                          <PlusIcon size={12} />
                        </button>
                      </div>

                      {/* Trash Delete */}
                      <button
                        onClick={() => onRemoveItem(item.product_id)}
                        disabled={isUpdating}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                        title="Remove item"
                        aria-label="Remove item"
                      >
                        <TrashIcon size={15} />
                      </button>
                    </div>
                  );
                })}
              </div>

              {/* PART A: Coupons & Promo Codes */}
              <div className="bg-white p-3.5 rounded-2xl border border-slate-200 shadow-2xs space-y-2.5">
                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                  <TagIcon size={14} className="text-indigo-600" />
                  <span>Promo Code & Coupons</span>
                </div>

                {appliedCoupon ? (
                  <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 px-3 py-2 rounded-xl text-xs">
                    <div className="flex items-center gap-2 text-emerald-800">
                      <CheckCircleIcon size={14} className="text-emerald-600" />
                      <span>
                        <strong className="font-mono">{appliedCoupon}</strong> applied · ₹
                        {couponDiscount.toLocaleString('en-IN')} off
                      </span>
                    </div>
                    <button
                      onClick={handleRemovePromo}
                      className="text-xs font-bold text-rose-600 hover:text-rose-800"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <form onSubmit={handleApplyPromo} className="space-y-1.5">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder="Enter promo code (e.g. SAVE500)"
                        value={promoInput}
                        onChange={(e) => {
                          setPromoInput(e.target.value);
                          setPromoError(null);
                        }}
                        className="flex-1 uppercase font-mono bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs placeholder:normal-case placeholder:font-sans placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-1 focus:ring-indigo-500"
                      />
                      <Button
                        type="submit"
                        variant="secondary"
                        size="sm"
                        disabled={!promoInput.trim() || promoLoading}
                      >
                        {promoLoading ? 'Checking...' : 'Apply'}
                      </Button>
                    </div>
                    {promoError && (
                      <p className="text-[11px] font-medium text-rose-600">{promoError}</p>
                    )}
                  </form>
                )}

                {/* Available Store Coupons Chips */}
                {!appliedCoupon && availableCoupons.length > 0 && (
                  <div className="pt-1 flex flex-wrap gap-1.5">
                    {availableCoupons.map((c) => (
                      <button
                        key={c.code}
                        onClick={() => {
                          setPromoInput(c.code);
                          if (onApplyCoupon) onApplyCoupon(c.code);
                        }}
                        className="text-[10px] font-semibold bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 text-slate-700 px-2.5 py-1 rounded-lg border border-slate-200 transition-colors"
                      >
                        {c.code} · ₹{c.discount_value} OFF
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* PART B: Vouchers */}
              {availableVouchers.length > 0 && (
                <div className="bg-white p-3.5 rounded-2xl border border-slate-200 shadow-2xs space-y-2">
                  <button
                    onClick={() => setShowVouchers(!showVouchers)}
                    className="w-full flex items-center justify-between text-xs font-bold text-slate-800"
                  >
                    <div className="flex items-center gap-1.5">
                      <GiftIcon size={14} className="text-amber-600" />
                      <span>Your Vouchers ({availableVouchers.length})</span>
                    </div>
                    <span className="text-xs text-indigo-600 font-semibold">
                      {showVouchers ? 'Hide' : 'View'}
                    </span>
                  </button>

                  {appliedVoucher && (
                    <div className="flex items-center justify-between bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-xl text-xs">
                      <span className="text-amber-900 font-medium">
                        Voucher <strong>{appliedVoucher}</strong> applied · -₹
                        {voucherDiscount.toLocaleString('en-IN')}
                      </span>
                      <button
                        onClick={() => onApplyVoucher && onApplyVoucher(null)}
                        className="text-xs font-bold text-rose-600 hover:text-rose-800"
                      >
                        Remove
                      </button>
                    </div>
                  )}

                  {showVouchers && (
                    <div className="space-y-1.5 pt-1">
                      {availableVouchers.map((v) => (
                        <div
                          key={v.id}
                          className="flex items-center justify-between p-2 rounded-xl bg-slate-50 border border-slate-200 text-xs"
                        >
                          <div>
                            <div className="font-bold text-slate-900">{v.title}</div>
                            <div className="text-[10px] text-slate-500">{v.description}</div>
                          </div>
                          <Button
                            variant={appliedVoucher === v.code ? 'secondary' : 'primary'}
                            size="sm"
                            onClick={() => handleSelectVoucher(v.code)}
                          >
                            {appliedVoucher === v.code ? 'Applied' : 'Apply'}
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* PART C: Apex Coins */}
              {coinBalance > 0 && (
                <div className="bg-white p-3.5 rounded-2xl border border-slate-200 shadow-2xs flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
                      <CoinsIcon size={16} />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-900 flex items-center gap-1">
                        <span>Use Apex Coins</span>
                        <span className="text-[10px] font-normal text-slate-500">
                          ({coinBalance.toLocaleString('en-IN')} available)
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-500">10 coins = ₹1 · Instant savings</p>
                    </div>
                  </div>

                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={useCoins}
                      onChange={(e) => onToggleCoins && onToggleCoins(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600" />
                  </label>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer with Breakdown & Proceed to Checkout */}
        {cart.items.length > 0 && (
          <div className="p-5 bg-white border-t border-slate-200 space-y-4">
            {/* Loyalty Point Earning Preview */}
            {pointsToEarn > 0 && (
              <div className="flex items-center gap-2 text-[11px] text-indigo-700 bg-indigo-50 border border-indigo-200/80 px-3 py-2 rounded-xl">
                <AwardIcon size={15} className="text-indigo-600 shrink-0" />
                <span>
                  You will earn <strong>+{pointsToEarn} Apex Points</strong> on this order
                </span>
              </div>
            )}

            {/* Authoritative Price Breakdown */}
            <div className="space-y-1.5 text-xs">
              <div className="flex items-center justify-between text-slate-500">
                <span>Subtotal</span>
                <span className="font-semibold text-slate-900 font-mono">
                  ₹{subtotal.toLocaleString('en-IN')}
                </span>
              </div>

              {couponDiscount > 0 && (
                <div className="flex items-center justify-between text-emerald-700 font-medium">
                  <span>Coupon Discount ({appliedCoupon})</span>
                  <span className="font-mono">-₹{couponDiscount.toLocaleString('en-IN')}</span>
                </div>
              )}

              {voucherDiscount > 0 && (
                <div className="flex items-center justify-between text-amber-700 font-medium">
                  <span>Voucher Discount</span>
                  <span className="font-mono">-₹{voucherDiscount.toLocaleString('en-IN')}</span>
                </div>
              )}

              {coinDiscount > 0 && (
                <div className="flex items-center justify-between text-indigo-700 font-medium">
                  <span>Apex Coins ({pricingBreakdown?.coins_used} coins)</span>
                  <span className="font-mono">-₹{coinDiscount.toLocaleString('en-IN')}</span>
                </div>
              )}

              <div className="flex items-center justify-between text-slate-500">
                <span>Delivery Charges</span>
                <span className="text-emerald-600 font-medium">FREE</span>
              </div>

              <div className="flex items-center justify-between text-sm sm:text-base font-extrabold text-slate-900 pt-2 border-t border-slate-100">
                <span>Payable Total</span>
                <span className="font-mono text-indigo-700">₹{finalTotal.toLocaleString('en-IN')}</span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="space-y-2">
              <Button
                onClick={onCheckout}
                variant="primary"
                size="lg"
                className="w-full font-bold shadow-md hover:shadow-lg"
                rightIcon={<ArrowRightIcon size={16} />}
              >
                Proceed to Checkout
              </Button>

              <button
                onClick={onClearCart}
                className="w-full py-1.5 text-center text-xs text-slate-400 hover:text-slate-600 transition-colors"
              >
                Clear Cart
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
