'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/Badge';
import {
  UserIcon,
  PackageIcon,
  CoinsIcon,
  LogOutIcon,
  ShieldCheckIcon,
  SparklesIcon,
  ActivityIcon,
  ShoppingBagIcon,
  FileTextIcon,
} from '@/components/ui/Icons';
import { UserProfile } from '@/lib/types/user';
import { apiClient } from '@/lib/api';

interface ProfileMenuProps {
  userProfile: UserProfile | null;
  onOpenAuth?: () => void;
  onSignOut?: () => void;
  variant?: 'storefront' | 'merchant';
}

export function ProfileMenu({
  userProfile,
  onOpenAuth,
  onSignOut,
}: ProfileMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [actionableCount, setActionableCount] = useState<number>(0);
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Fetch actionable price requests badge
  useEffect(() => {
    if (!userProfile) {
      setActionableCount(0);
      return;
    }
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    if (!token) return;

    apiClient
      .get<{ actionable_count: number; total_count: number }>('/negotiation/my-requests/badge')
      .then((res) => {
        if (res.data?.actionable_count !== undefined) {
          setActionableCount(res.data.actionable_count);
        }
      })
      .catch(() => {
        // Silently catch
      });
  }, [userProfile, isOpen]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleSignOut = () => {
    setIsOpen(false);
    if (onSignOut) {
      onSignOut();
    } else {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_profile');
      router.push('/');
    }
  };

  if (!userProfile) {
    return (
      <button
        onClick={onOpenAuth}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-indigo-600 text-white text-xs font-semibold shadow-xs transition-all"
      >
        <UserIcon size={14} />
        <span>Sign In</span>
      </button>
    );
  }

  const isMerchant = userProfile.role === 'merchant_admin';
  const initial = (userProfile.full_name || userProfile.email || 'U').charAt(0).toUpperCase();

  return (
    <div className="relative" ref={menuRef}>
      {/* Profile Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 p-1 pl-1.5 pr-2.5 rounded-full border transition-all ${
          isOpen
            ? 'border-indigo-500 bg-indigo-50/50 ring-2 ring-indigo-500/20'
            : isMerchant
            ? 'border-purple-200 hover:border-purple-300 bg-purple-50/30 hover:bg-purple-50'
            : 'border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50'
        }`}
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        <div
          className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 overflow-hidden shadow-2xs ${
            isMerchant
              ? 'bg-slate-900 text-purple-300'
              : 'bg-indigo-600 text-white'
          }`}
        >
          {userProfile.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={userProfile.avatar_url}
              alt={userProfile.full_name || 'Avatar'}
              className="w-full h-full object-cover"
            />
          ) : (
            initial
          )}
        </div>

        <div className="hidden md:flex flex-col items-start text-left">
          <span className="text-xs font-bold text-slate-800 line-clamp-1 max-w-[100px]">
            {userProfile.full_name || userProfile.email.split('@')[0]}
          </span>
          <span className="text-[10px] text-slate-500 font-medium">
            {isMerchant ? 'Merchant' : 'Customer'}
          </span>
        </div>

        <svg
          className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown Menu Modal */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-72 rounded-2xl bg-white border border-slate-200 shadow-xl py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
          {/* Header Card */}
          <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50">
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white shrink-0 overflow-hidden shadow-xs ${
                  isMerchant ? 'bg-slate-900 text-purple-300' : 'bg-indigo-600'
                }`}
              >
                {userProfile.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={userProfile.avatar_url}
                    alt={userProfile.full_name || 'Avatar'}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  initial
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-slate-900 truncate">
                  {userProfile.full_name || 'User'}
                </p>
                <p className="text-[11px] text-slate-500 truncate">
                  {userProfile.email}
                </p>
                <div className="mt-1">
                  <Badge variant={isMerchant ? 'purple' : 'info'} size="xs">
                    {isMerchant ? '👑 Merchant Admin' : '🛍️ Verified Customer'}
                  </Badge>
                </div>
              </div>
            </div>
          </div>

          {/* Role-Specific Navigation Links */}
          <div className="p-1 space-y-0.5 text-xs">
            {isMerchant ? (
              <>
                <div className="px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Merchant Operations
                </div>
                <Link
                  href="/dashboard/profile"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <UserIcon size={14} className="text-purple-600" />
                  <span>Merchant Profile</span>
                </Link>
                <Link
                  href="/shopping"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <ShoppingBagIcon size={14} className="text-indigo-600" />
                  <span>Storefront</span>
                </Link>
                <Link
                  href="/dashboard"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <ActivityIcon size={14} className="text-indigo-600" />
                  <span>Merchant Dashboard</span>
                </Link>
                <Link
                  href="/dashboard/ai-growth"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <SparklesIcon size={14} className="text-amber-500" />
                  <span>AI Growth</span>
                </Link>
                <Link
                  href="/dashboard/governance"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <ShieldCheckIcon size={14} className="text-blue-600" />
                  <span>Governance</span>
                </Link>
                <Link
                  href="/dashboard/audit"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <FileTextIcon size={14} className="text-slate-600" />
                  <span>Audit Ledger</span>
                </Link>
              </>
            ) : (
              <>
                <div className="px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Customer Account
                </div>
                <Link
                  href="/profile"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <UserIcon size={14} className="text-indigo-600" />
                  <span>View Profile</span>
                </Link>
                <Link
                  href="/price-requests"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center justify-between px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm">🏷️</span>
                    <span>Price Requests</span>
                  </div>
                  {actionableCount > 0 && (
                    <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-amber-500 text-white animate-pulse">
                      {actionableCount}
                    </span>
                  )}
                </Link>
                <Link
                  href="/orders"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <PackageIcon size={14} className="text-slate-600" />
                  <span>Orders</span>
                </Link>
                <Link
                  href="/rewards"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <CoinsIcon size={14} className="text-amber-500" />
                  <span>Rewards</span>
                </Link>
                <Link
                  href="/profile#addresses"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <span className="text-slate-500 text-xs">📍</span>
                  <span>Saved Addresses</span>
                </Link>
                <Link
                  href="/profile#settings"
                  onClick={() => setIsOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors"
                >
                  <span className="text-slate-500 text-xs">⚙️</span>
                  <span>Account Settings</span>
                </Link>
              </>
            )}
          </div>

          {/* Footer Actions */}
          <div className="p-1 border-t border-slate-100 mt-1">
            <button
              onClick={handleSignOut}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-rose-600 hover:bg-rose-50 font-semibold text-xs transition-colors"
            >
              <LogOutIcon size={14} />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
