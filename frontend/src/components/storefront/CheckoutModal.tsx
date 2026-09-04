'use client';

import React, { useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  ShieldCheckIcon,
  CreditCardIcon,
  AlertTriangleIcon,
  MapPinIcon,
} from '@/components/ui/Icons';
import { CartData } from './CartDrawer';
import { Product } from './ProductCard';
import { CartPricingBreakdown } from '@/lib/types/rewards';

export interface DeliveryAddressData {
  full_name: string;
  phone: string;
  email: string;
  address_line1: string;
  address_line2?: string;
  landmark?: string;
  city: string;
  state: string;
  pin_code: string;
  country: string;
}

export interface PaymentReceipt {
  payment_id: string;
  order_id: string;
  amount: number;
  currency: string;
  status: string;
  signature_verified: boolean;
  authorized_at?: string;
  trace_id?: string;
  delivery_address?: DeliveryAddressData;
  created_at?: string;
}

export interface PaymentConfig {
  configured: boolean;
  key_id?: string | null;
  mode: string;
  provider: string;
  currency: string;
}

export interface CheckoutApprovalDetails {
  approvalId?: string;
  amount: number;
  threshold: number;
  reason?: string;
}

export interface CheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  cart: CartData;
  catalogProducts: Product[];
  checkoutStep:
    | 'address'
    | 'review'
    | 'approval_required'
    | 'policy_blocked'
    | 'processing'
    | 'verifying'
    | 'success'
    | 'failed';
  setCheckoutStep: (
    step: 'address' | 'review' | 'approval_required' | 'policy_blocked' | 'processing' | 'verifying' | 'success' | 'failed'
  ) => void;
  deliveryAddress: DeliveryAddressData;
  setDeliveryAddress: React.Dispatch<React.SetStateAction<DeliveryAddressData>>;
  onStartPayment: (forceApprove?: boolean) => void;
  paymentConfig: PaymentConfig | null;
  receipt: PaymentReceipt | null;
  errorMessage: string | null;
  pricingBreakdown?: CartPricingBreakdown | null;
  onReset: () => void;
  approvalDetails?: CheckoutApprovalDetails | null;
}

const INDIAN_STATES = [
  'Andhra Pradesh',
  'Arunachal Pradesh',
  'Assam',
  'Bihar',
  'Chhattisgarh',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal Pradesh',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Madhya Pradesh',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil Nadu',
  'Telangana',
  'Tripura',
  'Uttar Pradesh',
  'Uttarakhand',
  'West Bengal',
  'Andaman and Nicobar Islands',
  'Chandigarh',
  'Dadra and Nagar Haveli and Daman and Diu',
  'Delhi',
  'Jammu and Kashmir',
  'Ladakh',
  'Lakshadweep',
  'Puducherry',
];

export function CheckoutModal({
  isOpen,
  onClose,
  cart,
  catalogProducts,
  checkoutStep,
  setCheckoutStep,
  deliveryAddress,
  setDeliveryAddress,
  onStartPayment,
  paymentConfig,
  receipt,
  errorMessage,
  pricingBreakdown = null,
  onReset,
  approvalDetails = null,
}: CheckoutModalProps) {
  const isConfigured = Boolean(paymentConfig?.configured);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validateAddress = (): boolean => {
    const errs: Record<string, string> = {};

    if (!deliveryAddress.full_name.trim()) {
      errs.full_name = 'Please enter your full name.';
    } else if (deliveryAddress.full_name.trim().length < 2) {
      errs.full_name = 'Full name must be at least 2 characters.';
    }

    const cleanPhone = deliveryAddress.phone.replace(/\D/g, '');
    if (!cleanPhone) {
      errs.phone = 'Please enter your mobile number.';
    } else if (cleanPhone.length !== 10) {
      errs.phone = 'Mobile number must be 10 digits.';
    }

    if (!deliveryAddress.email.trim()) {
      errs.email = 'Please enter your email address.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(deliveryAddress.email)) {
      errs.email = 'Please enter a valid email address.';
    }

    if (!deliveryAddress.address_line1.trim()) {
      errs.address_line1 = 'Please enter your street address / flat number.';
    } else if (deliveryAddress.address_line1.trim().length < 3) {
      errs.address_line1 = 'Address must be at least 3 characters.';
    }

    if (!deliveryAddress.city.trim()) {
      errs.city = 'Please enter your city.';
    }

    if (!deliveryAddress.state.trim()) {
      errs.state = 'Please select your state.';
    }

    const cleanPin = deliveryAddress.pin_code.replace(/\D/g, '');
    if (!cleanPin) {
      errs.pin_code = 'Please enter your PIN code.';
    } else if (cleanPin.length !== 6) {
      errs.pin_code = 'PIN code must be 6 digits.';
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleAddressContinue = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateAddress()) {
      // Persist delivery address in localStorage
      if (typeof window !== 'undefined') {
        localStorage.setItem('checkout_delivery_address', JSON.stringify(deliveryAddress));
      }
      setCheckoutStep('review');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="lg"
      title={
        <div className="space-y-0.5">
          <div className="text-base font-bold text-slate-900">
            {checkoutStep === 'address'
              ? 'Delivery Address'
              : checkoutStep === 'review'
              ? 'Review Order'
              : checkoutStep === 'approval_required'
              ? 'Approval Required'
              : checkoutStep === 'policy_blocked'
              ? 'Purchase Blocked by Policy'
              : checkoutStep === 'success'
              ? 'Order Confirmed'
              : checkoutStep === 'failed'
              ? 'Payment Failed'
              : 'Secure Checkout'}
          </div>
          <p className="text-xs text-slate-500 font-normal">
            {checkoutStep === 'address'
              ? 'Step 1 of 2: Enter your delivery details for shipping.'
              : checkoutStep === 'review'
              ? 'Step 2 of 2: Authoritative server price and inventory verification.'
              : checkoutStep === 'approval_required'
              ? 'Transaction exceeds autonomous threshold and requires explicit approval.'
              : checkoutStep === 'policy_blocked'
              ? 'Order was halted before payment due to deterministic governance policies.'
              : checkoutStep === 'success'
              ? 'Your transaction has been cryptographically verified and captured.'
              : 'Grounded in deterministic backend policy and authorization snapshots.'}
          </p>
        </div>
      }
    >
      <div className="space-y-5 text-slate-900">
        {/* Step 1: Delivery Address Form */}
        {checkoutStep === 'address' && (
          <form onSubmit={handleAddressContinue} className="space-y-4">
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600 flex items-center gap-2">
              <MapPinIcon size={16} className="text-indigo-600 shrink-0" />
              <span>We deliver across all PIN codes in India with verified express dispatch.</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {/* Full Name */}
              <div className="sm:col-span-2 space-y-1">
                <label className="text-xs font-semibold text-slate-700 block">
                  Full Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={deliveryAddress.full_name}
                  onChange={(e) => {
                    setDeliveryAddress((p) => ({ ...p, full_name: e.target.value }));
                    if (errors.full_name) setErrors((prev) => ({ ...prev, full_name: '' }));
                  }}
                  placeholder="e.g. Kritika Bansal"
                  className={`w-full px-3.5 py-2 text-xs rounded-xl border bg-white text-slate-900 focus:outline-none focus:ring-2 transition-all ${
                    errors.full_name
                      ? 'border-rose-300 focus:ring-rose-200'
                      : 'border-slate-200 focus:ring-slate-200 focus:border-slate-400'
                  }`}
                />
                {errors.full_name && <p className="text-[11px] text-rose-500">{errors.full_name}</p>}
              </div>

              {/* Mobile Number */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 block">
                  Mobile Number <span className="text-rose-500">*</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-xs text-slate-400 font-medium select-none">
                    +91
                  </span>
                  <input
                    type="tel"
                    maxLength={10}
                    value={deliveryAddress.phone}
                    onChange={(e) => {
                      const val = e.target.value.replace(/\D/g, '');
                      setDeliveryAddress((p) => ({ ...p, phone: val }));
                      if (errors.phone) setErrors((prev) => ({ ...prev, phone: '' }));
                    }}
                    placeholder="9876543210"
                    className={`w-full pl-12 pr-3.5 py-2 text-xs rounded-xl border bg-white text-slate-900 focus:outline-none focus:ring-2 transition-all ${
                      errors.phone
                        ? 'border-rose-300 focus:ring-rose-200'
                        : 'border-slate-200 focus:ring-slate-200 focus:border-slate-400'
                    }`}
                  />
                </div>
                {errors.phone && <p className="text-[11px] text-rose-500">{errors.phone}</p>}
              </div>

              {/* Email Address */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 block">
                  Email Address <span className="text-rose-500">*</span>
                </label>
                <input
                  type="email"
                  value={deliveryAddress.email}
                  onChange={(e) => {
                    setDeliveryAddress((p) => ({ ...p, email: e.target.value }));
                    if (errors.email) setErrors((prev) => ({ ...prev, email: '' }));
                  }}
                  placeholder="kritika@example.com"
                  className={`w-full px-3.5 py-2 text-xs rounded-xl border bg-white text-slate-900 focus:outline-none focus:ring-2 transition-all ${
                    errors.email
                      ? 'border-rose-300 focus:ring-rose-200'
                      : 'border-slate-200 focus:ring-slate-200 focus:border-slate-400'
                  }`}
                />
                {errors.email && <p className="text-[11px] text-rose-500">{errors.email}</p>}
              </div>

              {/* Address Line 1 */}
              <div className="sm:col-span-2 space-y-1">
                <label className="text-xs font-semibold text-slate-700 block">
                  Flat / House No. / Building / Street <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={deliveryAddress.address_line1}
                  onChange={(e) => {
                    setDeliveryAddress((p) => ({ ...p, address_line1: e.target.value }));
                    if (errors.address_line1) setErrors((prev) => ({ ...prev, address_line1: '' }));
                  }}
                  placeholder="e.g. Flat 402, Lotus Heights, MG Road"
                  className={`w-full px-3.5 py-2 text-xs rounded-xl border bg-white text-slate-900 focus:outline-none focus:ring-2 transition-all ${
                    errors.address_line1
                      ? 'border-rose-300 focus:ring-rose-200'
                      : 'border-slate-200 focus:ring-slate-200 focus:border-slate-400'
                  }`}
                />
                {errors.address_line1 && (
                  <p className="text-[11px] text-rose-500">{errors.address_line1}</p>
                )}
              </div>

              {/* Address Line 2 */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 block">
                  Apartment / Area / Sector (Optional)
                </label>
                <input
                  type="text"
                  value={deliveryAddress.address_line2 || ''}
                  onChange={(e) =>
                    setDeliveryAddress((p) => ({ ...p, address_line2: e.target.value }))
                  }
                  placeholder="e.g. Indiranagar"
                  className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-200 focus:border-slate-400 transition-all"
                />
              </div>

              {/* Landmark */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 block">
                  Landmark (Optional)
                </label>
                <input
                  type="text"
                  value={deliveryAddress.landmark || ''}
                  onChange={(e) =>
                    setDeliveryAddress((p) => ({ ...p, landmark: e.target.value }))
                  }
                  placeholder="e.g. Near Metro Station"
                  className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-200 focus:border-slate-400 transition-all"
                />
              </div>

              {/* City */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 block">
                  City <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={deliveryAddress.city}
                  onChange={(e) => {
                    setDeliveryAddress((p) => ({ ...p, city: e.target.value }));
                    if (errors.city) setErrors((prev) => ({ ...prev, city: '' }));
                  }}
                  placeholder="e.g. Bengaluru"
                  className={`w-full px-3.5 py-2 text-xs rounded-xl border bg-white text-slate-900 focus:outline-none focus:ring-2 transition-all ${
                    errors.city
                      ? 'border-rose-300 focus:ring-rose-200'
                      : 'border-slate-200 focus:ring-slate-200 focus:border-slate-400'
                  }`}
                />
                {errors.city && <p className="text-[11px] text-rose-500">{errors.city}</p>}
              </div>

              {/* State */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 block">
                  State <span className="text-rose-500">*</span>
                </label>
                <select
                  value={deliveryAddress.state}
                  onChange={(e) => {
                    setDeliveryAddress((p) => ({ ...p, state: e.target.value }));
                    if (errors.state) setErrors((prev) => ({ ...prev, state: '' }));
                  }}
                  className={`w-full px-3.5 py-2 text-xs rounded-xl border bg-white text-slate-900 focus:outline-none focus:ring-2 transition-all ${
                    errors.state
                      ? 'border-rose-300 focus:ring-rose-200'
                      : 'border-slate-200 focus:ring-slate-200 focus:border-slate-400'
                  }`}
                >
                  <option value="">Select State</option>
                  {INDIAN_STATES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                {errors.state && <p className="text-[11px] text-rose-500">{errors.state}</p>}
              </div>

              {/* PIN Code */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 block">
                  PIN Code <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  maxLength={6}
                  value={deliveryAddress.pin_code}
                  onChange={(e) => {
                    const val = e.target.value.replace(/\D/g, '');
                    setDeliveryAddress((p) => ({ ...p, pin_code: val }));
                    if (errors.pin_code) setErrors((prev) => ({ ...prev, pin_code: '' }));
                  }}
                  placeholder="560001"
                  className={`w-full px-3.5 py-2 text-xs rounded-xl border bg-white text-slate-900 focus:outline-none focus:ring-2 transition-all ${
                    errors.pin_code
                      ? 'border-rose-300 focus:ring-rose-200'
                      : 'border-slate-200 focus:ring-slate-200 focus:border-slate-400'
                  }`}
                />
                {errors.pin_code && <p className="text-[11px] text-rose-500">{errors.pin_code}</p>}
              </div>

              {/* Country */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 block">Country</label>
                <input
                  type="text"
                  disabled
                  value="India"
                  className="w-full px-3.5 py-2 text-xs rounded-xl border border-slate-200 bg-slate-100 text-slate-500 cursor-not-allowed"
                />
              </div>
            </div>

            <div className="pt-3">
              <Button type="submit" variant="primary" size="lg" className="w-full font-bold">
                Continue to Order Review →
              </Button>
            </div>
          </form>
        )}

        {/* Step 2: Review & Order Summary */}
        {checkoutStep === 'review' && (
          <div className="space-y-4">
            {/* Delivery Address Summary Card */}
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                  <MapPinIcon size={14} className="text-indigo-600" />
                  Deliver To
                </span>
                <button
                  type="button"
                  onClick={() => setCheckoutStep('address')}
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  Edit Address
                </button>
              </div>

              <div className="text-xs text-slate-700 space-y-0.5">
                <p className="font-bold text-slate-900">{deliveryAddress.full_name}</p>
                <p>
                  {deliveryAddress.address_line1}
                  {deliveryAddress.address_line2 ? `, ${deliveryAddress.address_line2}` : ''}
                </p>
                {deliveryAddress.landmark && <p className="text-slate-500">Landmark: {deliveryAddress.landmark}</p>}
                <p>
                  {deliveryAddress.city}, {deliveryAddress.state} - {deliveryAddress.pin_code}
                </p>
                <p className="text-slate-500 pt-1">
                  Contact: +91 {deliveryAddress.phone} | {deliveryAddress.email}
                </p>
              </div>
            </div>

            {/* Order Items Table */}
            <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3 shadow-xs">
              <span className="text-xs font-bold text-slate-900 uppercase tracking-wider block">
                Order Items ({cart.items.reduce((s, i) => s + i.quantity, 0)})
              </span>
              <div className="divide-y divide-slate-100">
                {cart.items.map((item) => {
                  const product = catalogProducts.find((p) => p.id === item.product_id);
                  const name = item.name || product?.name || 'Item';
                  return (
                    <div key={item.product_id} className="py-2.5 flex items-center justify-between text-xs">
                      <div className="space-y-0.5 min-w-0 pr-4">
                        <span className="font-semibold text-slate-900 truncate block">{name}</span>
                        <span className="text-slate-500">
                          Qty: {item.quantity} × ₹{Number(item.unit_price).toLocaleString('en-IN')}
                        </span>
                      </div>
                      <span className="font-bold text-slate-900 shrink-0">
                        ₹{Number(item.subtotal || item.unit_price * item.quantity).toLocaleString('en-IN')}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className="pt-3 border-t border-slate-200 space-y-1.5 text-xs text-slate-600">
                <div className="flex justify-between">
                  <span>Subtotal</span>
                  <span className="font-medium text-slate-900 font-mono">
                    ₹{Number(pricingBreakdown?.subtotal ?? cart.total_amount).toLocaleString('en-IN')}
                  </span>
                </div>

                {pricingBreakdown && pricingBreakdown.coupon_discount > 0 && (
                  <div className="flex justify-between text-emerald-700 font-medium">
                    <span>Coupon Discount ({pricingBreakdown.coupon_code})</span>
                    <span className="font-mono">-₹{pricingBreakdown.coupon_discount.toLocaleString('en-IN')}</span>
                  </div>
                )}

                {pricingBreakdown && pricingBreakdown.voucher_discount > 0 && (
                  <div className="flex justify-between text-amber-700 font-medium">
                    <span>Voucher Discount</span>
                    <span className="font-mono">-₹{pricingBreakdown.voucher_discount.toLocaleString('en-IN')}</span>
                  </div>
                )}

                {pricingBreakdown && pricingBreakdown.coin_discount > 0 && (
                  <div className="flex justify-between text-indigo-700 font-medium">
                    <span>Apex Coins ({pricingBreakdown.coins_used} coins)</span>
                    <span className="font-mono">-₹{pricingBreakdown.coin_discount.toLocaleString('en-IN')}</span>
                  </div>
                )}

                <div className="flex justify-between">
                  <span>Standard Shipping</span>
                  <span className="font-semibold text-emerald-600">FREE</span>
                </div>

                <div className="pt-2 border-t border-slate-200 flex items-center justify-between text-sm font-extrabold text-slate-900">
                  <span>Total Payable</span>
                  <span className="font-mono text-indigo-700">
                    ₹{Number(pricingBreakdown?.total ?? cart.total_amount).toLocaleString('en-IN')}
                  </span>
                </div>

                {pricingBreakdown && pricingBreakdown.points_to_earn > 0 && (
                  <div className="text-[11px] text-indigo-600 font-semibold pt-1">
                    ✓ You will earn +{pricingBreakdown.points_to_earn} Apex Points upon completion
                  </div>
                )}
              </div>
            </div>

            {/* Verification Checkpoints */}
            <div className="bg-emerald-50/60 border border-emerald-200 rounded-2xl p-3.5 space-y-2 text-xs text-emerald-900">
              <div className="font-bold flex items-center gap-1.5 text-emerald-800">
                <ShieldCheckIcon size={16} />
                <span>Deterministic Pre-Payment Governance Checks:</span>
              </div>
              <ul className="space-y-1 text-[11px] text-emerald-700 pl-5 list-disc">
                <li>Authoritative database catalog price lock active</li>
                <li>Live database stock inventory verified for delivery</li>
                <li>Immutable order delivery snapshot generated</li>
              </ul>
            </div>

            {/* Gateway Credential Alert if not configured */}
            {!isConfigured && (
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start gap-2.5">
                <AlertTriangleIcon size={16} className="text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold block">Online payment is currently unavailable</span>
                  <span className="text-slate-600 text-[11px] leading-relaxed">
                    Razorpay payment is not configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to backend/.env.
                  </span>
                </div>
              </div>
            )}

            {/* Action Trigger */}
            <div className="pt-2 space-y-2">
              <Button
                onClick={() => onStartPayment(false)}
                disabled={cart.items.length === 0}
                variant="primary"
                size="lg"
                className="w-full font-bold shadow-md hover:shadow-lg"
                leftIcon={<CreditCardIcon size={16} />}
              >
                Pay securely with Razorpay
              </Button>

              <Button
                type="button"
                onClick={() => setCheckoutStep('address')}
                variant="secondary"
                size="sm"
                className="w-full"
              >
                ← Back to Delivery Address
              </Button>
            </div>
          </div>
        )}

        {/* Step: Additional Approval Required (High-Value Transaction Governance) */}
        {checkoutStep === 'approval_required' && (
          <div className="space-y-4">
            <div className="p-5 rounded-2xl bg-amber-50/80 border border-amber-200 text-left space-y-2.5">
              <div className="flex items-center gap-2 text-amber-900 font-extrabold text-sm">
                <AlertTriangleIcon size={18} className="text-amber-600 shrink-0" />
                <span>Additional approval required</span>
              </div>
              <p className="text-xs text-amber-900 leading-relaxed">
                Your order total is{' '}
                <strong>
                  ₹{Number(approvalDetails?.amount ?? pricingBreakdown?.total ?? cart.total_amount).toLocaleString('en-IN')}
                </strong>
                , which is above the autonomous payment limit of{' '}
                <strong>
                  ₹{Number(approvalDetails?.threshold ?? 5000).toLocaleString('en-IN')}
                </strong>
                .
              </p>
              <p className="text-[11px] text-amber-700 leading-relaxed">
                To proceed with secure Razorpay checkout, please explicitly authorize this high-value transaction.
              </p>
            </div>

            <div className="flex gap-2.5 pt-2">
              <Button
                onClick={() => onStartPayment(true)}
                variant="primary"
                size="md"
                className="flex-1 font-bold shadow-md hover:shadow-lg"
                leftIcon={<CreditCardIcon size={16} />}
              >
                Approve Payment →
              </Button>
              <Button
                onClick={() => setCheckoutStep('review')}
                variant="secondary"
                size="md"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Step: Processing / Loading */}
        {(checkoutStep === 'processing' || checkoutStep === 'verifying') && (
          <div className="py-8 text-center space-y-4">
            <div className="w-12 h-12 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
            <div className="space-y-1">
              <h4 className="font-bold text-sm text-slate-900">
                {checkoutStep === 'processing'
                  ? 'Formulating Intent & Initializing Razorpay...'
                  : 'Verifying Cryptographic Payment Signature...'}
              </h4>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Executing deterministic authorization snapshot and HMAC-SHA256 signature verification.
              </p>
            </div>
          </div>
        )}

        {/* Step: Success Confirmed Order Receipt */}
        {checkoutStep === 'success' && receipt && (
          <div className="space-y-4">
            <div className="p-5 rounded-2xl bg-emerald-50 border border-emerald-200 text-center space-y-2">
              <div className="w-12 h-12 rounded-full bg-emerald-100 border border-emerald-300 text-emerald-700 mx-auto flex items-center justify-center text-xl font-bold">
                ✓
              </div>
              <h4 className="font-extrabold text-base text-emerald-950">Order Confirmed & Payment Captured</h4>
              <p className="text-xs text-emerald-700">
                Payment verified securely by Razorpay • Inventory confirmed by server
              </p>
            </div>

            {/* Order Reference Details */}
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-2.5 text-xs text-slate-700">
              <div className="flex justify-between items-center pb-2 border-b border-slate-200">
                <span className="text-slate-500 font-medium">Order ID:</span>
                <span className="font-bold text-slate-900 font-mono">{receipt.order_id}</span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-slate-200">
                <span className="text-slate-500 font-medium">Payment ID:</span>
                <span className="font-bold text-slate-900 font-mono">{receipt.payment_id}</span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-slate-200">
                <span className="text-slate-500 font-medium">Total Paid:</span>
                <span className="font-bold text-emerald-600 text-sm">
                  ₹{Number(receipt.amount).toLocaleString('en-IN')} {receipt.currency}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 font-medium">Payment Status:</span>
                <Badge variant="success" size="xs">
                  PAID / VERIFIED (HMAC_SHA256)
                </Badge>
              </div>
            </div>

            {/* Immutable Delivery Address Snapshot */}
            {receipt.delivery_address && (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-1.5 text-xs text-slate-700 shadow-xs">
                <span className="font-bold text-slate-900 uppercase tracking-wider text-[11px] block">
                  Delivery Address Snapshot
                </span>
                <p className="font-semibold text-slate-900">{receipt.delivery_address.full_name}</p>
                <p>
                  {receipt.delivery_address.address_line1}
                  {receipt.delivery_address.address_line2 ? `, ${receipt.delivery_address.address_line2}` : ''}
                </p>
                {receipt.delivery_address.landmark && (
                  <p className="text-slate-500">Landmark: {receipt.delivery_address.landmark}</p>
                )}
                <p>
                  {receipt.delivery_address.city}, {receipt.delivery_address.state} -{' '}
                  {receipt.delivery_address.pin_code}
                </p>
                <p className="text-slate-500">Contact: +91 {receipt.delivery_address.phone}</p>
              </div>
            )}

            <Button onClick={onClose} variant="primary" size="md" className="w-full font-bold">
              Continue Shopping
            </Button>
          </div>
        )}

        {/* Step: Purchase Blocked by Policy */}
        {checkoutStep === 'policy_blocked' && (
          <div className="space-y-4">
            <div className="p-5 rounded-2xl bg-amber-50/90 border border-amber-200 text-left space-y-2.5">
              <div className="flex items-center gap-2 text-amber-950 font-extrabold text-sm">
                <AlertTriangleIcon size={18} className="text-amber-600 shrink-0" />
                <span>Purchase Blocked by Policy</span>
              </div>
              <p className="text-xs text-amber-900 leading-relaxed font-medium">
                {errorMessage || 'This purchase violates merchant or governance safety policies.'}
              </p>
              <div className="text-[11px] text-amber-800 bg-amber-100/60 p-2.5 rounded-xl border border-amber-200/80 font-mono leading-relaxed">
                Deterministic Policy Engine: Order was safely halted before payment processing. No charge or card attempt was made.
              </div>
            </div>

            <div className="flex gap-2.5 pt-2">
              <Button
                onClick={() => setCheckoutStep('review')}
                variant="primary"
                size="md"
                className="flex-1 font-bold"
              >
                Review Cart
              </Button>
              <Button onClick={onClose} variant="secondary" size="md">
                Close
              </Button>
            </div>
          </div>
        )}

        {/* Step: Failed (Real Gateway Payment Failure) */}
        {checkoutStep === 'failed' && (
          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-900 space-y-1.5">
              <span className="font-bold block">Payment could not be completed</span>
              <p className="text-slate-600 text-[11px]">
                {errorMessage || 'An error occurred during payment processing.'}
              </p>
            </div>

            <div className="flex gap-2">
              <Button onClick={onReset} variant="primary" size="md" className="flex-1">
                Try Again
              </Button>
              <Button onClick={onClose} variant="secondary" size="md">
                Close
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
