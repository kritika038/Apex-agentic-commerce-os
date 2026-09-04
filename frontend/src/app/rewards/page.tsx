'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  CoinsIcon,
  AwardIcon,
  GiftIcon,
  TagIcon,
  SparklesIcon,
  CheckCircleIcon,
  RotateCcwIcon,
} from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';
import { StorefrontHeader } from '@/components/storefront/StorefrontHeader';
import { AuthModal } from '@/components/auth/AuthModal';
import { apiClient } from '@/lib/api';
import { CustomerRewardsData } from '@/lib/types/rewards';
import { UserProfile } from '@/lib/types/user';

export default function RewardsPage() {
  const [rewards, setRewards] = useState<CustomerRewardsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [copiedVoucher, setCopiedVoucher] = useState<string | null>(null);

  const fetchUserProfile = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setUserProfile(null);
      setLoading(false);
      return;
    }
    try {
      const res = await apiClient.get('/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUserProfile(res.data);
    } catch {
      localStorage.removeItem('access_token');
      setUserProfile(null);
    }
  };

  const fetchRewards = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get('/rewards/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setRewards(res.data);
    } catch (err: unknown) {
      console.error('Failed to load rewards:', err);
      setError('Could not load your rewards. Please check your network connection.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUserProfile();
    fetchRewards();
  }, []);

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedVoucher(code);
    setTimeout(() => setCopiedVoucher(null), 2500);
  };

  const handleSignOut = () => {
    localStorage.removeItem('access_token');
    setUserProfile(null);
    setRewards(null);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Header */}
      <StorefrontHeader
        cartItemCount={0}
        onOpenCart={() => {}}
        onOpenAI={() => {}}
        onOpenAuth={() => setIsAuthOpen(true)}
        onSignOut={handleSignOut}
        searchQuery=""
        onSearchChange={() => {}}
        userProfile={userProfile}
      />

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Breadcrumb Navigation */}
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
          <Link href="/" className="hover:text-slate-900 transition-colors">
            Home
          </Link>
          <span>/</span>
          <span className="text-slate-900">Apex Rewards & Loyalty</span>
        </div>

        {/* Hero Section */}
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-6 sm:p-8 text-white shadow-xl relative overflow-hidden">
          <div className="absolute right-0 top-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="relative z-10 max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-400/30 text-indigo-200 text-xs font-bold">
              <SparklesIcon size={14} className="text-indigo-300" />
              <span>APEX VIP REWARDS PROGRAM</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Your Rewards, Coins & Vouchers
            </h1>
            <p className="text-xs sm:text-sm text-slate-300">
              Earn Apex Points with every verified purchase, redeem Apex Coins for instant checkout discounts, and unlock exclusive VIP gear vouchers.
            </p>
          </div>
        </div>

        {/* Unauthenticated State */}
        {!userProfile ? (
          <div className="bg-white rounded-3xl p-10 border border-slate-200 shadow-sm text-center space-y-4 max-w-md mx-auto">
            <div className="w-16 h-16 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto text-2xl">
              <CoinsIcon size={32} />
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-bold text-slate-900">Sign in to view your rewards</h2>
              <p className="text-xs text-slate-500">
                Log in to check your available Apex Coins, active vouchers, and points balance.
              </p>
            </div>
            <Button
              variant="primary"
              size="md"
              onClick={() => setIsAuthOpen(true)}
              className="w-full font-bold"
            >
              Sign In to Apex Store
            </Button>
          </div>
        ) : loading ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs font-semibold text-slate-500">Loading your loyalty ledger...</p>
          </div>
        ) : error ? (
          <div className="bg-white rounded-3xl p-8 border border-rose-200 text-center space-y-3 max-w-md mx-auto">
            <p className="text-xs font-medium text-rose-600">{error}</p>
            <Button variant="secondary" size="sm" onClick={fetchRewards}>
              Try Again
            </Button>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Balances Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Apex Coins Card */}
              <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs space-y-4 relative overflow-hidden">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center">
                      <CoinsIcon size={24} />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                        Apex Coins Balance
                      </div>
                      <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-mono">
                        {rewards?.coin_balance.toLocaleString('en-IN')}{' '}
                        <span className="text-xs font-semibold text-slate-400 font-sans">Coins</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-amber-50/60 border border-amber-200/70 rounded-2xl p-3.5 flex items-center justify-between text-xs">
                  <div>
                    <span className="text-amber-900 font-semibold">Estimated Cash Value: </span>
                    <strong className="font-mono text-amber-950 font-bold">
                      ₹{Number(rewards?.estimated_coin_value_inr).toLocaleString('en-IN')}
                    </strong>
                  </div>
                  <span className="text-[10px] text-amber-700 font-medium">10 Coins = ₹1.00</span>
                </div>
              </div>

              {/* Apex Points Card */}
              <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                      <AwardIcon size={24} />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                        Loyalty Points
                      </div>
                      <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-mono">
                        {rewards?.points_balance.toLocaleString('en-IN')}{' '}
                        <span className="text-xs font-semibold text-slate-400 font-sans">Points</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-indigo-50/60 border border-indigo-200/70 rounded-2xl p-3.5 flex items-center justify-between text-xs">
                  <div>
                    <span className="text-indigo-900 font-semibold">Earning Rule: </span>
                    <span className="text-indigo-800">1 Apex Point per ₹100 paid</span>
                  </div>
                  <span className="text-[10px] text-indigo-700 font-medium">Auto-credited</span>
                </div>
              </div>
            </div>

            {/* Vouchers Section */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <GiftIcon size={18} className="text-amber-600" />
                  <h2 className="text-base font-bold text-slate-900">
                    Your Exclusive Vouchers ({rewards?.available_vouchers.length || 0})
                  </h2>
                </div>
              </div>

              {rewards?.available_vouchers.length === 0 ? (
                <div className="bg-white rounded-2xl p-6 border border-slate-200 text-center text-xs text-slate-500">
                  No active personal vouchers at the moment. Keep shopping to unlock VIP vouchers!
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {rewards?.available_vouchers.map((v) => (
                    <div
                      key={v.id}
                      className="bg-white rounded-2xl p-5 border border-slate-200 shadow-2xs space-y-3 flex flex-col justify-between"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md">
                            {v.discount_type === 'PERCENTAGE'
                              ? `${v.discount_value}% OFF`
                              : `₹${v.discount_value} OFF`}
                          </span>
                          <span className="text-[11px] text-slate-400">
                            Min Order: ₹{v.min_cart_amount}
                          </span>
                        </div>
                        <h3 className="text-sm font-bold text-slate-900">{v.title}</h3>
                        <p className="text-xs text-slate-500">{v.description}</p>
                      </div>

                      <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                        <div className="font-mono text-xs font-bold bg-slate-100 px-3 py-1.5 rounded-xl text-slate-800 border border-slate-200">
                          {v.code}
                        </div>

                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleCopyCode(v.code)}
                          leftIcon={
                            copiedVoucher === v.code ? (
                              <CheckCircleIcon size={14} className="text-emerald-600" />
                            ) : (
                              <TagIcon size={14} />
                            )
                          }
                        >
                          {copiedVoucher === v.code ? 'Copied!' : 'Copy Code'}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Unified Activity Ledger */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <RotateCcwIcon size={18} className="text-slate-600" />
                <h2 className="text-base font-bold text-slate-900">Rewards Activity Ledger</h2>
              </div>

              <div className="bg-white rounded-3xl border border-slate-200 shadow-xs overflow-hidden">
                <div className="divide-y divide-slate-100">
                  {rewards?.coin_history.length === 0 && rewards?.points_history.length === 0 ? (
                    <div className="p-8 text-center text-xs text-slate-500">
                      No rewards activity recorded yet.
                    </div>
                  ) : (
                    <>
                      {rewards?.coin_history.map((entry) => (
                        <div
                          key={`coin_${entry.id}`}
                          className="p-4 flex items-center justify-between gap-4 text-xs hover:bg-slate-50/50 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
                                entry.amount >= 0
                                  ? 'bg-emerald-50 text-emerald-600'
                                  : 'bg-rose-50 text-rose-600'
                              }`}
                            >
                              <CoinsIcon size={15} />
                            </div>
                            <div>
                              <div className="font-bold text-slate-900">{entry.description}</div>
                              <div className="text-[10px] text-slate-400">
                                {new Date(entry.created_at).toLocaleString('en-IN', {
                                  dateStyle: 'medium',
                                  timeStyle: 'short',
                                })}
                              </div>
                            </div>
                          </div>

                          <div
                            className={`font-mono font-bold text-sm shrink-0 ${
                              entry.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'
                            }`}
                          >
                            {entry.amount >= 0 ? `+${entry.amount}` : entry.amount} Coins
                          </div>
                        </div>
                      ))}

                      {rewards?.points_history.map((entry) => (
                        <div
                          key={`pts_${entry.id}`}
                          className="p-4 flex items-center justify-between gap-4 text-xs hover:bg-slate-50/50 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                              <AwardIcon size={15} />
                            </div>
                            <div>
                              <div className="font-bold text-slate-900">{entry.description}</div>
                              <div className="text-[10px] text-slate-400">
                                {new Date(entry.created_at).toLocaleString('en-IN', {
                                  dateStyle: 'medium',
                                  timeStyle: 'short',
                                })}
                              </div>
                            </div>
                          </div>

                          <div className="font-mono font-bold text-sm text-indigo-600 shrink-0">
                            +{entry.points} Points
                          </div>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Auth Modal */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        authConfig={null}
        onSuccess={(profile) => {
          setUserProfile(profile);
          setIsAuthOpen(false);
          fetchRewards();
        }}
      />
    </div>
  );
}
