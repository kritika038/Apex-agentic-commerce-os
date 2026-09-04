'use client';

import React from 'react';
import Link from 'next/link';
import {
  SparklesIcon,
  ShoppingBagIcon,
  SearchIcon,
  MicIcon,
} from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';
import { ProfileMenu } from '@/components/auth/ProfileMenu';
import { UserProfile } from '@/lib/types/user';
export type { UserProfile };

export interface StorefrontHeaderProps {
  cartItemCount: number;
  onOpenCart: () => void;
  onOpenAI: () => void;
  onOpenAuth: () => void;
  onSignOut: () => void;
  onOpenVoiceSearch?: () => void;
  onOpenVisualSearch?: () => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  userProfile: UserProfile | null;
}

export function StorefrontHeader({
  cartItemCount,
  onOpenCart,
  onOpenAI,
  onOpenAuth,
  onSignOut,
  onOpenVoiceSearch,
  onOpenVisualSearch,
  searchQuery,
  onSearchChange,
  userProfile,
}: StorefrontHeaderProps) {
  const isMerchantAdmin = userProfile?.role === 'merchant_admin';

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200/80 shadow-2xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-3 sm:gap-6">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-2.5 group shrink-0">
          <div className="w-8 h-8 rounded-xl bg-slate-900 flex items-center justify-center text-white shadow-xs group-hover:bg-indigo-600 transition-colors">
            <span className="font-extrabold text-sm tracking-tighter">A</span>
          </div>
          <div className="flex flex-col">
            <span className="font-extrabold text-sm sm:text-base tracking-tight text-slate-900 leading-none">
              APEX STORE
            </span>
            <span className="text-[10px] font-medium text-slate-500 tracking-wide mt-0.5">
              Governed AI Commerce
            </span>
          </div>
        </Link>

        {/* Global Search Bar */}
        <div className="flex-1 max-w-lg mx-2 hidden sm:block">
          <div className="relative flex items-center">
            <SearchIcon
              size={15}
              className="absolute left-3.5 text-slate-400 pointer-events-none"
            />
            <input
              type="text"
              placeholder="Search products, brands, categories..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full bg-slate-50 text-slate-900 border border-slate-200 rounded-full pl-9 pr-14 py-2 text-xs placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all"
            />
            <div className="absolute right-2 flex items-center gap-1">
              {searchQuery && (
                <button
                  onClick={() => onSearchChange('')}
                  className="p-1 text-xs text-slate-400 hover:text-slate-600 rounded-full"
                  aria-label="Clear search"
                >
                  ✕
                </button>
              )}
              {onOpenVisualSearch && (
                <button
                  type="button"
                  onClick={onOpenVisualSearch}
                  className="p-1 text-slate-400 hover:text-indigo-600 rounded-full transition-colors text-xs"
                  title="Visual Search (Search by Image)"
                  aria-label="Visual Search"
                >
                  📷
                </button>
              )}
              {onOpenVoiceSearch && (
                <button
                  type="button"
                  onClick={onOpenVoiceSearch}
                  className="p-1 text-slate-400 hover:text-indigo-600 rounded-full transition-colors"
                  title="Voice Search (English / Hindi)"
                  aria-label="Voice Search"
                >
                  <MicIcon size={14} />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Right Action Icons & Controls */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {/* AI Assistant Button */}
          <Button
            onClick={onOpenAI}
            variant="secondary"
            size="sm"
            className="border-indigo-200 text-indigo-700 bg-indigo-50/50 hover:bg-indigo-50 font-semibold"
            leftIcon={<SparklesIcon size={14} className="text-indigo-600" />}
          >
            <span className="hidden sm:inline">AI Assistant</span>
            <span className="sm:hidden">AI</span>
          </Button>

          {/* Cart Icon & Trigger */}
          <button
            onClick={onOpenCart}
            className="relative p-2 rounded-xl text-slate-700 hover:text-slate-900 hover:bg-slate-100 transition-colors"
            title="Shopping Cart"
            aria-label="Shopping Cart"
          >
            <ShoppingBagIcon size={18} />
            {cartItemCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-slate-900 text-white text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center shadow-xs">
                {cartItemCount}
              </span>
            )}
          </button>

          {/* Role-Guarded Merchant Console (ONLY visible to merchant_admin) */}
          {isMerchantAdmin && (
            <Link
              href="/dashboard"
              className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-xs transition-colors"
            >
              Merchant Console →
            </Link>
          )}

          {/* Interactive Role-Aware Profile Menu */}
          <div className="pl-1 border-l border-slate-200">
            <ProfileMenu
              userProfile={userProfile}
              onOpenAuth={onOpenAuth}
              onSignOut={onSignOut}
              variant="storefront"
            />
          </div>
        </div>
      </div>

      {/* Mobile Search Bar Row */}
      <div className="px-4 pb-3 sm:hidden">
        <div className="relative flex items-center">
          <SearchIcon size={14} className="absolute left-3 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search products, categories..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-slate-50 text-slate-900 border border-slate-200 rounded-xl pl-9 pr-8 py-2 text-xs placeholder:text-slate-400 focus:outline-none focus:bg-white focus:ring-1 focus:ring-indigo-500"
          />
          {onOpenVoiceSearch && (
            <button
              type="button"
              onClick={onOpenVoiceSearch}
              className="absolute right-2.5 p-1 text-slate-400 hover:text-indigo-600 transition-colors"
              title="Voice Search"
              aria-label="Voice Search"
            >
              <MicIcon size={14} />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
