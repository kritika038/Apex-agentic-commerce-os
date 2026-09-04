'use client';

import React, { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/Badge';
import { ProfileMenu } from '@/components/auth/ProfileMenu';
import { UserProfile } from '@/lib/types/user';

interface SubNavItem {
  label: string;
  href: string;
  description?: string;
}

interface NavGroup {
  label: string;
  href: string;
  badge?: string;
  badgeVariant?: 'purple' | 'success' | 'warning' | 'neutral';
  items?: SubNavItem[];
}

const PRIMARY_NAV_GROUPS: NavGroup[] = [
  {
    label: 'Overview',
    href: '/dashboard',
  },
  {
    label: 'AI Growth',
    href: '/dashboard/ai-growth',
  },
  {
    label: 'Store',
    href: '/shopping',
    items: [
      { label: 'Catalog', href: '/shopping', description: 'Storefront product catalog and pricing' },
      { label: 'Inventory', href: '/dashboard#activity-tabs-section', description: 'Live inventory quantities and SKU tracking' },
      { label: 'Product Performance', href: '/dashboard/protocol?tab=discover', description: 'Catalog discovery and conversion statistics' },
      { label: 'Price Intelligence', href: '/shopping', description: 'Buyhatke-style multi-market price checks' },
    ],
  },
  {
    label: 'Orders',
    href: '/orders',
    items: [
      { label: 'Orders', href: '/orders', description: 'Customer and autonomous agent order history' },
      { label: 'Purchase Intents', href: '/dashboard/approvals', description: 'Deterministic agent intent evaluation queue' },
      { label: 'Customers', href: '/dashboard#activity-tabs-section', description: 'Customer profiles and buyer agent sessions' },
    ],
  },
  {
    label: 'Finance',
    href: '/dashboard/revenue',
    items: [
      { label: 'Revenue', href: '/dashboard/revenue', description: 'Incremental GMV, campaign autopilot & analytics' },
      { label: 'Payments', href: '/dashboard/payments', description: 'Razorpay payment transactions and gateway logs' },
      { label: 'Recovery / Reconciliation', href: '/dashboard/payments/recovery', description: 'Automated settlement retry and failed state reconciliation' },
    ],
  },
  {
    label: 'Governance',
    href: '/dashboard/governance',
    items: [
      { label: 'Policies', href: '/dashboard/policies', description: 'Deterministic safety rules & spending thresholds' },
      { label: 'Approvals', href: '/dashboard/approvals', description: 'Human-in-the-loop review queue for transactions' },
      { label: 'Audit', href: '/dashboard/audit', description: 'SHA-256 cryptographically chained ledger' },
      { label: 'Monitoring', href: '/dashboard/observability', description: 'Autonomous agent step traces and latency metrics' },
      { label: 'Security Lab', href: '/dashboard/security-lab', description: 'Adversarial prompt injection & red-team tests' },
      { label: 'Controls', href: '/dashboard/control-plane', description: 'Firewall rules and provider settlement gates' },
    ],
  },
];

const JUDGE_DEMO_GROUP: NavGroup = {
  label: 'Judge Demo',
  href: '/ai-commerce',
  badge: 'Live',
  badgeVariant: 'warning',
  items: [
    { label: 'AI-to-AI Commerce', href: '/ai-commerce', description: 'Autonomous 5-stage buyer & merchant agent protocol' },
    { label: 'Agent Protocol', href: '/dashboard/protocol', description: 'Machine-to-machine structured discovery & negotiation' },
    { label: 'Technical Trace', href: '/dashboard/observability', description: 'End-to-end cryptographic execution audit' },
  ],
};

export function DashboardNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cached = localStorage.getItem('user_profile');
    if (cached) {
      try {
        setUserProfile(JSON.parse(cached));
      } catch (e) {
        console.error('Failed to parse cached user profile', e);
      }
    }
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node)) {
        setOpenDropdown(null);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
    setOpenDropdown(null);
  }, [pathname]);

  const handleSignOut = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_profile');
    router.push('/');
  };

  const isGroupActive = (group: NavGroup) => {
    if (group.href === '/dashboard') {
      return pathname === '/dashboard';
    }
    if (pathname === group.href) {
      return true;
    }
    if (group.items) {
      return group.items.some((item) => {
        const itemPath = item.href.split('?')[0].split('#')[0];
        return itemPath !== '/dashboard' && pathname.startsWith(itemPath);
      });
    }
    return pathname.startsWith(group.href);
  };

  return (
    <header ref={navRef} className="border-b border-slate-200 bg-white sticky top-0 z-40">
      {/* Top Bar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand & Subtitle */}
        <div className="flex items-center gap-6">
          <Link href="/dashboard" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-xl bg-slate-900 flex items-center justify-center font-bold text-white text-sm shadow-xs group-hover:bg-indigo-600 transition-colors">
              ⚡
            </div>
            <div className="flex flex-col">
              <span className="font-extrabold text-sm sm:text-base tracking-tight text-slate-900 leading-none">
                APEX MERCHANT
              </span>
              <span className="text-[10px] font-medium text-slate-500 tracking-wide mt-0.5">
                Merchant Operating Center
              </span>
            </div>
          </Link>

          {/* Desktop Primary Navigation Links */}
          <nav className="hidden md:flex items-center gap-1 text-xs" aria-label="Main Navigation">
            {PRIMARY_NAV_GROUPS.map((group) => {
              const active = isGroupActive(group);
              const hasSub = Boolean(group.items && group.items.length > 0);
              const isOpen = openDropdown === group.label;

              return (
                <div
                  key={group.label}
                  className="relative"
                  onMouseEnter={() => hasSub && setOpenDropdown(group.label)}
                  onMouseLeave={() => hasSub && setOpenDropdown(null)}
                >
                  <Link
                    href={group.href}
                    onClick={() => hasSub && setOpenDropdown(isOpen ? null : group.label)}
                    className={`px-3 py-2 rounded-xl font-medium flex items-center gap-1.5 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                      active
                        ? 'bg-indigo-50 text-indigo-700 font-bold'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                    }`}
                    aria-expanded={hasSub ? isOpen : undefined}
                    aria-haspopup={hasSub ? 'true' : undefined}
                  >
                    <span>{group.label}</span>
                    {group.badge && (
                      <span className="px-1.5 py-0.2 rounded-md text-[9px] font-bold bg-indigo-100 text-indigo-700">
                        {group.badge}
                      </span>
                    )}
                    {hasSub && (
                      <span className="text-[10px] text-slate-400 transform transition-transform duration-150">
                        ▾
                      </span>
                    )}
                  </Link>

                  {/* Dropdown Menu */}
                  {hasSub && isOpen && (
                    <div className="absolute top-full left-0 w-64 pt-1 z-50 animate-in fade-in-50 slide-in-from-top-1 duration-150">
                      <div className="bg-white border border-slate-200 rounded-2xl p-2 shadow-lg space-y-1">
                        <div className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          {group.label} Operations
                        </div>
                        {group.items?.map((sub) => {
                          const subPath = sub.href.split('?')[0].split('#')[0];
                          const isSubActive = subPath !== '/dashboard' && pathname.startsWith(subPath);

                          return (
                            <Link
                              key={sub.label}
                              href={sub.href}
                              onClick={() => setOpenDropdown(null)}
                              className={`block px-2.5 py-2 rounded-xl text-xs transition-colors ${
                                isSubActive
                                  ? 'bg-indigo-50 text-indigo-900 font-semibold'
                                  : 'hover:bg-slate-50 text-slate-700'
                              }`}
                            >
                              <div className="font-semibold text-slate-900 flex items-center justify-between">
                                <span>{sub.label}</span>
                                <span className="text-slate-300 text-[10px]">&rarr;</span>
                              </div>
                              {sub.description && (
                                <p className="text-[11px] text-slate-500 leading-tight mt-0.5">
                                  {sub.description}
                                </p>
                              )}
                            </Link>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </nav>
        </div>

        {/* Right Bar with Judge Demo & Profile */}
        <div className="flex items-center gap-3">
          {/* Judge Demo Button with Dropdown */}
          <div
            className="relative hidden sm:block"
            onMouseEnter={() => setOpenDropdown('JudgeDemo')}
            onMouseLeave={() => setOpenDropdown(null)}
          >
            <Link
              href={JUDGE_DEMO_GROUP.href}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold border flex items-center gap-1.5 transition-all ${
                pathname === '/ai-commerce' || pathname === '/demo'
                  ? 'bg-amber-100 text-amber-900 border-amber-300 shadow-xs'
                  : 'bg-amber-50 hover:bg-amber-100 text-amber-800 border-amber-200'
              }`}
            >
              <span>✨ Judge Demo</span>
              <span className="text-[10px] opacity-70">▾</span>
            </Link>

            {openDropdown === 'JudgeDemo' && (
              <div className="absolute top-full right-0 w-64 pt-1 z-50 animate-in fade-in-50 slide-in-from-top-1 duration-150">
                <div className="bg-white border border-slate-200 rounded-2xl p-2 shadow-lg space-y-1">
                  <div className="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-amber-600">
                    Live Autonomous Demo
                  </div>
                  {JUDGE_DEMO_GROUP.items?.map((sub) => (
                    <Link
                      key={sub.label}
                      href={sub.href}
                      onClick={() => setOpenDropdown(null)}
                      className="block px-2.5 py-2 rounded-xl text-xs hover:bg-amber-50/60 text-slate-700 transition-colors"
                    >
                      <div className="font-semibold text-slate-900 flex items-center justify-between">
                        <span>{sub.label}</span>
                        <span className="text-amber-500 text-[10px]">&rarr;</span>
                      </div>
                      {sub.description && (
                        <p className="text-[11px] text-slate-500 leading-tight mt-0.5">
                          {sub.description}
                        </p>
                      )}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>

          <Link
            href="/shopping"
            className="hidden lg:inline-flex px-3 py-1.5 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 hover:text-slate-900 text-xs font-semibold border border-slate-200 transition-colors"
          >
            Storefront &rarr;
          </Link>

          <div className="pl-1 border-l border-slate-200">
            <ProfileMenu
              userProfile={userProfile}
              onSignOut={handleSignOut}
              variant="merchant"
            />
          </div>

          {/* Mobile Hamburger Toggle */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? '✕' : '☰'}
          </button>
        </div>
      </div>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-slate-200 bg-white px-4 py-4 space-y-4 max-h-[80vh] overflow-y-auto shadow-inner">
          <div className="space-y-1">
            {PRIMARY_NAV_GROUPS.map((group) => (
              <div key={group.label} className="border-b border-slate-100 pb-2 mb-2 last:border-0">
                <Link
                  href={group.href}
                  className="font-bold text-sm text-slate-900 flex items-center justify-between py-1"
                >
                  <span>{group.label}</span>
                  {group.badge && (
                    <Badge variant={group.badgeVariant || 'neutral'} size="xs">
                      {group.badge}
                    </Badge>
                  )}
                </Link>
                {group.items && (
                  <div className="pl-3 mt-1 space-y-1 border-l-2 border-slate-100">
                    {group.items.map((sub) => (
                      <Link
                        key={sub.label}
                        href={sub.href}
                        className="block text-xs py-1 text-slate-600 hover:text-indigo-600"
                      >
                        {sub.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {/* Mobile Judge Demo */}
            <div className="pt-2">
              <Link
                href="/ai-commerce"
                className="font-bold text-sm text-amber-900 bg-amber-50 px-3 py-2 rounded-xl flex items-center justify-between"
              >
                <span>✨ Judge Demo (AI-to-AI)</span>
                <span className="text-xs">&rarr;</span>
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}

