'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { apiClient, extractErrorMessage } from '@/lib/api';
import { StorefrontHeader } from '@/components/storefront/StorefrontHeader';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import {
  UserIcon,
  PackageIcon,
  CoinsIcon,
  ShoppingBagIcon,
  ShieldCheckIcon,
  CheckCircle2Icon,
  AlertTriangleIcon,
  SparklesIcon,
} from '@/components/ui/Icons';
import { UserProfile } from '@/lib/types/user';

interface ActiveCoupon {
  code: string;
  description?: string;
  discount_type: string;
  discount_value: number;
  min_order_amount: number;
}

interface CustomerProfileData {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_google_user?: boolean;
  phone?: string | null;
  created_at?: string;
  orders_count: number;
  total_spent: number;
  apex_coins_balance: number;
  reward_points_balance: number;
  lifetime_coins_earned: number;
  saved_addresses: Array<{
    address_line1?: string;
    city?: string;
    state?: string;
    pin_code?: string;
    phone?: string;
  }>;
  default_address?: {
    address_line1?: string;
    city?: string;
    state?: string;
    pin_code?: string;
    phone?: string;
  } | null;
  active_coupons?: ActiveCoupon[];
  preferences?: {
    preferred_category?: string;
    preferred_shoe_size?: string;
    notifications_enabled?: boolean;
    ai_shopping_copilot?: boolean;
  };
  recent_orders: Array<{
    id: string;
    status: string;
    amount: number;
    currency: string;
    created_at?: string;
  }>;
}

export default function CustomerProfilePage() {
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [profileData, setProfileData] = useState<CustomerProfileData | null>(null);
  const [editName, setEditName] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedCoupon, setCopiedCoupon] = useState<string | null>(null);

  // Sync auth state
  useEffect(() => {
    const cached = localStorage.getItem('user_profile');
    if (cached) {
      try {
        const u = JSON.parse(cached);
        setUserProfile(u);
        setEditName(u.full_name || '');
      } catch (e) {
        console.error('Failed to parse cached user profile', e);
      }
    }
  }, []);

  const loadProfile = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiClient.get('/auth/profile');
      setProfileData(res.data);
      if (res.data.full_name) {
        setEditName(res.data.full_name);
      }
    } catch (err: unknown) {
      setErrorMsg(extractErrorMessage(err, 'Failed to load customer profile. Please sign in.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleUpdateName = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editName.trim()) return;
    setIsSaving(true);
    setSuccessMsg(null);
    setErrorMsg(null);
    try {
      const res = await apiClient.put('/auth/profile', { full_name: editName.trim() });
      setSuccessMsg('Profile name updated successfully.');
      if (userProfile) {
        const updated = { ...userProfile, full_name: res.data.full_name };
        setUserProfile(updated);
        localStorage.setItem('user_profile', JSON.stringify(updated));
      }
    } catch (err: unknown) {
      setErrorMsg(extractErrorMessage(err, 'Failed to update profile name.'));
    } finally {
      setIsSaving(false);
    }
  };

  const copyCouponCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCoupon(code);
    setTimeout(() => setCopiedCoupon(null), 2000);
  };

  const initial = (profileData?.full_name || userProfile?.full_name || userProfile?.email || 'U')
    .charAt(0)
    .toUpperCase();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      <StorefrontHeader
        onOpenCart={() => {}}
        onOpenAuth={() => {}}
        onOpenAI={() => {}}
        cartItemCount={0}
        userProfile={userProfile}
        onSignOut={() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('user_profile');
          window.location.href = '/';
        }}
        searchQuery=""
        onSearchChange={() => {}}
      />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Breadcrumb & Quick Actions */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Link href="/shopping" className="hover:text-slate-900 transition-colors">
              Storefront
            </Link>
            <span>/</span>
            <span className="text-slate-900 font-semibold">My Profile</span>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/orders"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-2xs transition-all"
            >
              <PackageIcon size={14} className="text-slate-500" />
              <span>My Orders</span>
            </Link>
            <Link
              href="/rewards"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-amber-200 bg-amber-50 hover:bg-amber-100 text-amber-900 text-xs font-semibold shadow-2xs transition-all"
            >
              <CoinsIcon size={14} className="text-amber-600" />
              <span>Rewards & Coins</span>
            </Link>
          </div>
        </div>

        {isLoading && (
          <div className="p-8 text-center text-xs text-slate-500 bg-white rounded-3xl border border-slate-200">
            Loading your customer profile & rewards...
          </div>
        )}

        {errorMsg && !profileData && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <AlertTriangleIcon size={16} className="text-rose-500 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <Link
              href="/shopping"
              className="px-3 py-1.5 rounded-xl bg-slate-900 text-white font-semibold text-xs hover:bg-slate-800 transition-colors"
            >
              Sign In
            </Link>
          </div>
        )}

        {/* Profile Identity Card */}
        <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm relative overflow-hidden">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-indigo-600 text-white flex items-center justify-center text-2xl font-bold shadow-md shrink-0 overflow-hidden">
                {userProfile?.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={userProfile.avatar_url}
                    alt={profileData?.full_name || 'Avatar'}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  initial
                )}
              </div>
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-xl font-extrabold text-slate-900">
                    {profileData?.full_name || userProfile?.full_name || 'Customer Account'}
                  </h1>
                  <Badge variant="info" size="xs">
                    🛍️ Customer
                  </Badge>
                  {profileData?.is_google_user ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[10px] font-semibold border border-slate-200">
                      <span>Google Verified</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[10px] font-semibold border border-slate-200">
                      <span>Password Account</span>
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 font-mono">
                  {profileData?.email || userProfile?.email || 'customer@example.com'}
                </p>
                <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-400 pt-0.5">
                  <span>
                    Phone: <strong className="text-slate-600">{profileData?.phone || 'Not added yet'}</strong>
                  </span>
                  <span>•</span>
                  <span>
                    Member since{' '}
                    <strong className="text-slate-600">
                      {profileData?.created_at
                        ? new Date(profileData.created_at).toLocaleDateString(undefined, {
                            month: 'short',
                            year: 'numeric',
                          })
                        : 'Recent'}
                    </strong>
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Link
                href="/shopping"
                className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-slate-900 hover:bg-indigo-600 text-white text-xs font-bold transition-all shadow-xs"
              >
                <ShoppingBagIcon size={14} />
                <span>Start Shopping</span>
              </Link>
            </div>
          </div>
        </div>

        {/* Real Commerce Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">Total Orders</span>
              <PackageIcon size={16} className="text-indigo-600" />
            </div>
            <p className="text-2xl font-black text-slate-900">
              {profileData?.orders_count ?? 0}
            </p>
            <p className="text-[11px] text-slate-400">Lifetime orders placed</p>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500">Total Spent</span>
              <ShieldCheckIcon size={16} className="text-emerald-600" />
            </div>
            <p className="text-2xl font-black text-slate-900">
              ₹{(profileData?.total_spent ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </p>
            <p className="text-[11px] text-slate-400">Captured transactions</p>
          </div>

          <div className="p-5 rounded-2xl bg-amber-50/50 border border-amber-200/80 shadow-2xs space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-amber-800">Apex Coins</span>
              <CoinsIcon size={16} className="text-amber-600" />
            </div>
            <p className="text-2xl font-black text-amber-900">
              {profileData?.apex_coins_balance ?? 0} <span className="text-xs font-bold">Coins</span>
            </p>
            <p className="text-[11px] text-amber-700">₹1 = 1 Coin at checkout</p>
          </div>

          <div className="p-5 rounded-2xl bg-purple-50/50 border border-purple-200/80 shadow-2xs space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-purple-800">Reward Points</span>
              <SparklesIcon size={16} className="text-purple-600" />
            </div>
            <p className="text-2xl font-black text-purple-900">
              {profileData?.reward_points_balance ?? 0} <span className="text-xs font-bold">Pts</span>
            </p>
            <Link
              href="/rewards"
              className="text-[11px] font-semibold text-purple-700 hover:text-purple-900 underline block"
            >
              Redeem for discounts →
            </Link>
          </div>
        </div>

        {/* 2-Column Section: Profile Details & Addresses / Orders */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Account Settings & Preferences */}
          <div className="space-y-6">
            <div id="settings" className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <UserIcon size={16} className="text-indigo-600" />
                <span>Account Settings</span>
              </h2>

              {successMsg && (
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                  <CheckCircle2Icon size={14} className="text-emerald-600 shrink-0" />
                  <span>{successMsg}</span>
                </div>
              )}

              {errorMsg && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
                  <AlertTriangleIcon size={14} className="text-rose-600 shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <form onSubmit={handleUpdateName} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Full Name
                  </label>
                  <Input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="Your Name"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Email Address
                  </label>
                  <Input
                    value={profileData?.email || userProfile?.email || ''}
                    disabled
                    className="bg-slate-100 cursor-not-allowed opacity-80"
                  />
                  <p className="text-[10px] text-slate-400 mt-1">
                    Email is locked to your authenticated security identity.
                  </p>
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isSaving}
                  className="w-full"
                >
                  Save Changes
                </Button>
              </form>
            </div>

            {/* Customer Preferences Card */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-3">
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <span>⚙️ Shopping Preferences</span>
              </h2>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between py-1.5 border-b border-slate-100">
                  <span className="text-slate-500">Favorite Sport</span>
                  <span className="font-semibold text-slate-800">
                    {profileData?.preferences?.preferred_category || 'Running & Athletics'}
                  </span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-slate-100">
                  <span className="text-slate-500">Shoe Size</span>
                  <span className="font-semibold text-slate-800">
                    {profileData?.preferences?.preferred_shoe_size || 'UK 9 / US 10'}
                  </span>
                </div>
                <div className="flex justify-between py-1.5 border-b border-slate-100">
                  <span className="text-slate-500">AI Shopping Copilot</span>
                  <span className="font-semibold text-emerald-600">Enabled</span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-slate-500">Order Updates</span>
                  <span className="font-semibold text-emerald-600">SMS & In-App</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Saved Addresses, Vouchers & Recent Orders */}
          <div className="lg:col-span-2 space-y-6">
            {/* Saved Addresses */}
            <div id="addresses" className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <span>📍 Saved Delivery Addresses</span>
                </h2>
                {profileData?.saved_addresses && profileData.saved_addresses.length > 0 && (
                  <span className="text-xs text-slate-500">
                    {profileData.saved_addresses.length} saved
                  </span>
                )}
              </div>

              {profileData?.saved_addresses && profileData.saved_addresses.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {profileData.saved_addresses.map((addr, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-2xl border text-xs space-y-2 relative transition-all ${
                        idx === 0
                          ? 'bg-indigo-50/50 border-indigo-200 shadow-2xs'
                          : 'bg-slate-50 border-slate-200/80'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900">
                          {idx === 0 ? 'Primary Delivery Address' : `Address #${idx + 1}`}
                        </span>
                        {idx === 0 && (
                          <span className="px-2 py-0.5 rounded-full bg-indigo-600 text-white text-[10px] font-bold">
                            Default
                          </span>
                        )}
                      </div>
                      <p className="text-slate-700 font-medium">
                        {addr.address_line1 || 'Address Line'}
                      </p>
                      <p className="text-slate-500">
                        {addr.city}, {addr.state} - {addr.pin_code}
                      </p>
                      {addr.phone && (
                        <p className="text-slate-500 text-[11px]">
                          Contact: <span className="font-mono text-slate-700">{addr.phone}</span>
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-6 rounded-2xl bg-slate-50 border border-dashed border-slate-200 text-center text-xs text-slate-500 space-y-1">
                  <p className="font-medium text-slate-700">No saved addresses yet</p>
                  <p className="text-[11px] text-slate-400">
                    Your delivery addresses will be saved automatically when you complete your first order.
                  </p>
                </div>
              )}
            </div>

            {/* Active Coupons & Vouchers Card */}
            {profileData?.active_coupons && profileData.active_coupons.length > 0 && (
              <div className="p-6 rounded-3xl bg-gradient-to-br from-indigo-900 to-slate-900 text-white shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-bold flex items-center gap-2 text-white">
                    <CoinsIcon size={16} className="text-amber-400" />
                    <span>Your Active Vouchers & Coupons</span>
                  </h2>
                  <Link
                    href="/rewards"
                    className="text-xs text-indigo-300 hover:text-white underline font-semibold"
                  >
                    View All Rewards →
                  </Link>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {profileData.active_coupons.map((c) => (
                    <div
                      key={c.code}
                      className="p-3.5 rounded-2xl bg-white/10 border border-white/15 backdrop-blur-sm space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-black text-amber-300 text-xs tracking-wider">
                          {c.code}
                        </span>
                        <button
                          type="button"
                          onClick={() => copyCouponCode(c.code)}
                          className="text-[10px] text-indigo-200 hover:text-white font-semibold underline cursor-pointer"
                        >
                          {copiedCoupon === c.code ? 'Copied!' : 'Copy'}
                        </button>
                      </div>
                      <p className="text-[11px] text-slate-200 line-clamp-2">
                        {c.description || (c.discount_type === 'PERCENTAGE' ? `${c.discount_value}% OFF` : `₹${c.discount_value} FLAT OFF`)}
                      </p>
                      <p className="text-[10px] text-slate-400">
                        Min Order: ₹{c.min_order_amount.toLocaleString()}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Purchases */}
            <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <PackageIcon size={16} className="text-indigo-600" />
                  <span>Recent Purchases</span>
                </h2>
                <Link
                  href="/orders"
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 underline"
                >
                  View All Orders →
                </Link>
              </div>

              {profileData?.recent_orders && profileData.recent_orders.length > 0 ? (
                <div className="divide-y divide-slate-100">
                  {profileData.recent_orders.map((ord) => (
                    <div key={ord.id} className="py-3.5 flex items-center justify-between text-xs hover:bg-slate-50/50 px-2 rounded-xl transition-colors">
                      <div>
                        <p className="font-mono font-bold text-slate-900">
                          #{ord.id.slice(0, 8).toUpperCase()}
                        </p>
                        <p className="text-[11px] text-slate-400">
                          {ord.created_at ? new Date(ord.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : 'Recent'}
                        </p>
                      </div>
                      <div className="text-right space-y-1">
                        <p className="font-extrabold text-slate-900">
                          ₹{ord.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </p>
                        <Badge
                          variant={ord.status === 'CONFIRMED' || ord.status === 'COMPLETED' ? 'success' : 'neutral'}
                          size="xs"
                        >
                          {ord.status}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-6 rounded-2xl bg-slate-50 border border-dashed border-slate-200 text-center text-xs text-slate-500 space-y-1">
                  <p className="font-medium text-slate-700">No orders placed yet</p>
                  <p className="text-[11px] text-slate-400">
                    Browse our running shoes and athletic gear collection!
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
