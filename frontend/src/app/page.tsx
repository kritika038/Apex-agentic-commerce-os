'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  SparklesIcon,
  ShieldCheckIcon,
  CreditCardIcon,
  ArrowRightIcon,
  CheckIcon,
  UserIcon,
} from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { AuthModal, UserProfile, AuthConfig } from '@/components/auth/AuthModal';
import { apiClient } from '@/lib/api';
import { ProductImage } from '@/components/ui/ProductImage';

interface Product {
  id: string;
  name: string;
  category: string;
  price: number;
  stock_quantity?: number;
  image_url?: string;
  description?: string;
}

const HOW_IT_WORKS_STEPS = [
  {
    num: '1',
    title: 'Tell us what you need',
    desc: 'Describe what you are looking for in natural language — by sport, budget, or specifications.',
  },
  {
    num: '2',
    title: 'AI finds relevant products',
    desc: 'The shopping assistant searches the catalog and recommends verified matching gear.',
  },
  {
    num: '3',
    title: 'Server verifies price & stock',
    desc: 'Deterministic backend services confirm inventory availability and authoritatively lock catalog prices.',
  },
  {
    num: '4',
    title: 'You review & approve',
    desc: 'An immutable authorization document snapshots the exact price before payment.',
  },
  {
    num: '5',
    title: 'Razorpay securely settles',
    desc: 'Payment executes via official Razorpay checkout with cryptographic signature verification.',
  },
];

const ARCHITECTURE_STEPS = [
  {
    step: '01',
    title: 'AI Intent & Search',
    description: 'Customer or buyer agent expresses intent via natural language.',
    badge: 'Discovery',
  },
  {
    step: '02',
    title: 'Catalog & Stock Resolution',
    description: 'Server retrieves live inventory and validated prices from database.',
    badge: 'Catalog',
  },
  {
    step: '03',
    title: 'Purchase Intent Formulation',
    description: 'Structured intent document specifies requested quantities and budget bounds.',
    badge: 'Intent',
  },
  {
    step: '04',
    title: 'Deterministic Policy Evaluation',
    description: 'Rules engine evaluates stock availability, price limits, and seller policies.',
    badge: 'Governance',
  },
  {
    step: '05',
    title: 'Authorization Snapshot',
    description: 'Cryptographic snapshot fixes the exact authorized total before payment.',
    badge: 'Lock',
  },
  {
    step: '06',
    title: 'Razorpay Payment & Capture',
    description: 'Official checkout opens; server verifies HMAC-SHA256 signature.',
    badge: 'Settlement',
  },
  {
    step: '07',
    title: 'SHA-256 Audit Ledger',
    description: 'Immutable, hash-chained ledger logs every state transition with full lineage.',
    badge: 'Audit',
  },
];

export default function LandingPage() {
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [featuredProducts, setFeaturedProducts] = useState<Product[]>([]);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    // Load auth configuration
    apiClient
      .get('/auth/config')
      .then((res) => setAuthConfig(res.data))
      .catch(() =>
        setAuthConfig({
          google_oauth_configured: false,
          allow_dev_auth: true,
          environment: 'development',
        })
      );

    // Load featured products from catalog
    apiClient
      .get('/products')
      .then((res) => setFeaturedProducts((res.data || []).slice(0, 4)))
      .catch((err) => console.error('Error fetching featured products:', err));

    // Check existing session
    const token = localStorage.getItem('access_token');
    if (token) {
      apiClient
        .get('/auth/me')
        .then((res) => {
          setUserProfile(res.data);
          localStorage.setItem('user_profile', JSON.stringify(res.data));
        })
        .catch(() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('user_profile');
          setUserProfile(null);
        });
    }
  }, []);

  const handleSignOut = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_profile');
    setUserProfile(null);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans selection:bg-indigo-600 selection:text-white">
      {/* 1. Global Navigation */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-xl bg-slate-900 flex items-center justify-center text-white font-bold text-sm shadow-xs group-hover:bg-indigo-600 transition-colors">
              ⚡
            </div>
            <span className="font-extrabold text-base tracking-tight text-slate-900">
              Agentic Commerce OS
            </span>
          </Link>

          {/* Nav Links */}
          <nav className="hidden md:flex items-center space-x-7 text-sm font-medium text-slate-600">
            <Link href="/shopping" className="hover:text-slate-900 transition-colors">
              Storefront
            </Link>
            <Link href="/agent-commerce" className="hover:text-slate-900 transition-colors">
              AI-to-AI Commerce
            </Link>
            <Link href="/demo" className="hover:text-slate-900 transition-colors">
              Interactive Demo
            </Link>
            <a href="#how-it-works" className="hover:text-slate-900 transition-colors">
              How It Works
            </a>
            <a href="#trust" className="hover:text-slate-900 transition-colors">
              Trust &amp; Security
            </a>
          </nav>

          {/* Right Action */}
          <div className="flex items-center gap-3">
            {userProfile?.role === 'merchant_admin' && (
              <Link
                href="/dashboard"
                className="hidden sm:inline-flex text-xs font-semibold px-3 py-1.5 rounded-xl bg-slate-900 text-white hover:bg-slate-800 transition-colors shadow-xs"
              >
                Merchant Console →
              </Link>
            )}

            {userProfile ? (
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-600 font-medium hidden sm:inline">
                  {userProfile.full_name || userProfile.email}
                </span>
                <Button onClick={handleSignOut} variant="outline" size="sm">
                  Sign Out
                </Button>
              </div>
            ) : (
              <Button onClick={() => setIsAuthOpen(true)} variant="primary" size="sm" leftIcon={<UserIcon size={14} />}>
                Sign In
              </Button>
            )}

            {/* Mobile Menu Trigger */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              aria-label="Toggle Navigation Menu"
            >
              <span className="text-lg">☰</span>
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-slate-200 bg-white px-4 pt-3 pb-5 space-y-3 text-sm font-medium text-slate-700">
            <Link
              href="/shopping"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-1.5 hover:text-indigo-600"
            >
              Storefront
            </Link>
            <Link
              href="/agent-commerce"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-1.5 hover:text-indigo-600"
            >
              AI-to-AI Commerce
            </Link>
            <Link
              href="/demo"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-1.5 hover:text-indigo-600"
            >
              Interactive Demo
            </Link>
            <a
              href="#how-it-works"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-1.5 hover:text-indigo-600"
            >
              How It Works
            </a>
            <a
              href="#trust"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-1.5 hover:text-indigo-600"
            >
              Trust &amp; Security
            </a>
            {userProfile?.role === 'merchant_admin' && (
              <Link
                href="/dashboard"
                onClick={() => setMobileMenuOpen(false)}
                className="block py-1.5 font-bold text-indigo-600"
              >
                Merchant Console →
              </Link>
            )}
          </div>
        )}
      </header>

      {/* 2. Split-Screen Hero Section */}
      <section className="bg-white border-b border-slate-200 py-16 sm:py-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
            {/* Left Column (55%) */}
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-xs font-semibold text-slate-700">
                <span className="w-2 h-2 rounded-full bg-indigo-600" />
                AI-POWERED SHOPPING
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 tracking-tight leading-[1.1] text-balance">
                Shop smarter.
                <br />
                <span className="text-indigo-600">Buy with confidence.</span>
              </h1>

              <p className="text-base sm:text-lg text-slate-600 max-w-xl leading-relaxed text-balance">
                Discover products with an AI shopping assistant while every price, inventory check, and payment remains governed by secure backend controls.
              </p>

              {/* Action CTAs */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2">
                <Link
                  href="/shopping"
                  className="inline-flex items-center justify-center font-bold text-base px-6 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white shadow-md hover:shadow-lg active:scale-[0.98] transition-all gap-2 cursor-pointer"
                >
                  <span>Start Shopping</span>
                  <ArrowRightIcon size={16} />
                </Link>

                <a
                  href="#how-it-works"
                  className="inline-flex items-center justify-center font-semibold text-base px-6 py-3 rounded-xl bg-white hover:bg-slate-50 text-slate-800 border border-slate-200 shadow-xs active:scale-[0.98] transition-all cursor-pointer"
                >
                  See How It Works
                </a>
              </div>

              {/* Trust Indicators */}
              <div className="pt-6 border-t border-slate-100 flex flex-wrap gap-x-6 gap-y-2 text-xs font-medium text-slate-600">
                <div className="flex items-center gap-1.5">
                  <span className="text-emerald-600 font-bold">✓</span>
                  <span>Verified inventory</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-emerald-600 font-bold">✓</span>
                  <span>Secure Razorpay checkout</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-emerald-600 font-bold">✓</span>
                  <span>Server-controlled pricing</span>
                </div>
              </div>
            </div>

            {/* Right Column (45%) — Professional Lifestyle Photography */}
            <div className="lg:col-span-5 relative">
              <div className="relative rounded-2xl overflow-hidden shadow-xl border border-slate-200 bg-slate-100 aspect-4/3 sm:aspect-5/4">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=1200&q=85&auto=format&fit=crop"
                  alt="Customer shopping online on laptop with AI assistant"
                  className="w-full h-full object-cover object-center"
                />

                {/* Clean Product UI Overlay Card */}
                <Link
                  href="/shopping?assistant=open"
                  className="block absolute bottom-4 left-4 right-4 bg-white/95 backdrop-blur-md rounded-xl p-3.5 border border-slate-200/80 shadow-lg text-xs space-y-2 hover:bg-white transition-all cursor-pointer"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded-md bg-indigo-50 text-indigo-600 flex items-center justify-center text-[10px]">
                        <SparklesIcon size={12} />
                      </div>
                      <span className="font-bold text-slate-900">AI Shopping Assistant</span>
                    </div>
                    <span className="text-[10px] text-emerald-600 font-semibold bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                      Live
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-slate-700">
                    <p className="font-medium text-slate-900">&quot;Looking for marathon running shoes under ₹5,000?&quot;</p>
                    <p className="text-slate-500 text-[11px] mt-1">Found 3 verified options in stock with locked pricing. Click to ask AI →</p>
                  </div>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Trust Bar */}
      <section id="trust" className="bg-slate-50 border-b border-slate-200 py-8 scroll-mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center sm:text-left">
            <div className="space-y-1">
              <div className="flex items-center justify-center sm:justify-start gap-2 text-slate-900 font-bold text-sm">
                <CreditCardIcon size={16} className="text-indigo-600" />
                <span>Secure Payments</span>
              </div>
              <p className="text-xs text-slate-500">Official Razorpay checkout with HMAC-SHA256 signature verification.</p>
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-center sm:justify-start gap-2 text-slate-900 font-bold text-sm">
                <ShieldCheckIcon size={16} className="text-indigo-600" />
                <span>Verified Inventory</span>
              </div>
              <p className="text-xs text-slate-500">Live database inventory checks prevent overselling.</p>
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-center sm:justify-start gap-2 text-slate-900 font-bold text-sm">
                <CheckIcon size={16} className="text-indigo-600" />
                <span>Server-Controlled Pricing</span>
              </div>
              <p className="text-xs text-slate-500">Zero LLM price authority. Authoritative SQL catalog grounding.</p>
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-center sm:justify-start gap-2 text-slate-900 font-bold text-sm">
                <SparklesIcon size={16} className="text-indigo-600" />
                <span>Auditable Ledger</span>
              </div>
              <p className="text-xs text-slate-500">SHA-256 hash chained audit trail for complete traceability.</p>
            </div>
          </div>
        </div>
      </section>

      {/* 4. How AI Shopping Works */}
      <section id="how-it-works" className="py-16 sm:py-24 bg-white border-b border-slate-200 scroll-mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
              How AI Shopping Works
            </h2>
            <p className="text-sm text-slate-600">
              A seamless blend of natural language discovery and deterministic financial governance.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
            {HOW_IT_WORKS_STEPS.map((step) => (
              <div
                key={step.num}
                className="bg-slate-50 border border-slate-200 rounded-2xl p-5 space-y-3 relative flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <span className="w-8 h-8 rounded-xl bg-indigo-600 text-white font-bold text-sm flex items-center justify-center shadow-xs">
                    {step.num}
                  </span>
                  <h3 className="font-bold text-sm text-slate-900">{step.title}</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 5. Featured Products (Real Catalog Grounding) */}
      <section className="py-16 sm:py-24 bg-slate-50 border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider block">
                Verified Catalog
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight mt-1">
                Featured Athletic Gear
              </h2>
            </div>
            <Link
              href="/shopping"
              className="text-sm font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1.5 transition-colors"
            >
              <span>Explore All Products</span>
              <ArrowRightIcon size={14} />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {featuredProducts.map((p) => (
              <div
                key={p.id}
                className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs hover:shadow-md hover:border-slate-300 transition-all flex flex-col justify-between"
              >
                <Link
                  href={`/shopping/${p.id}`}
                  className="block aspect-square bg-slate-100 overflow-hidden relative border-b border-slate-100 cursor-pointer group"
                >
                  <ProductImage
                    src={p.image_url}
                    alt={p.name}
                    productId={p.id}
                    productName={p.name}
                    category={p.category}
                    className="w-full h-full object-cover object-center group-hover:scale-105 transition-transform duration-300"
                    containerClassName="w-full h-full"
                  />
                  <span className="absolute top-3 left-3 px-2 py-0.5 rounded-md bg-white/90 text-[10px] font-semibold text-slate-700 shadow-2xs">
                    {p.category}
                  </span>
                </Link>
                <div className="p-4 space-y-3 flex-1 flex flex-col justify-between">
                  <div>
                    <Link href={`/shopping/${p.id}`} className="block">
                      <h3 className="font-semibold text-sm text-slate-900 line-clamp-1 hover:text-indigo-600 transition-colors">
                        {p.name}
                      </h3>
                    </Link>
                    <p className="text-xs text-slate-500 line-clamp-2 mt-1">{p.description}</p>
                  </div>
                  <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                    <span className="font-extrabold text-base text-slate-900 font-mono">
                      ₹{Number(p.price).toLocaleString('en-IN')}
                    </span>
                    <Link
                      href={`/shopping/${p.id}`}
                      className="inline-flex items-center justify-center text-xs font-semibold px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800 transition-colors"
                    >
                      View Product
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 6. AI Shopping Interaction Section */}
      <section className="py-16 sm:py-24 bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            {/* Left: Chat Flow */}
            <div className="lg:col-span-6 space-y-4">
              <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider">
                Conversational Assistant
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
                Ask naturally. Get verified product options.
              </h2>
              <p className="text-sm text-slate-600 leading-relaxed">
                Whether you need shoes for marathon training, breathable apparel, or accessories within a specific budget, the assistant queries real catalog inventory and explains why each item fits.
              </p>

              <div className="pt-2">
                <Link
                  href="/shopping?assistant=open"
                  className="inline-flex items-center justify-center font-semibold text-sm px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm hover:shadow-md transition-all gap-2 cursor-pointer"
                >
                  <SparklesIcon size={16} />
                  <span>Try the AI Shopping Assistant</span>
                </Link>
              </div>
            </div>

            {/* Right: Example UI Container */}
            <div className="lg:col-span-6 bg-slate-50 border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
              <div className="bg-slate-900 text-white p-3.5 rounded-2xl text-xs max-w-[85%] ml-auto shadow-xs">
                &quot;I need running shoes for marathon training under ₹5,000.&quot;
              </div>

              <div className="bg-white border border-slate-200 text-slate-800 p-4 rounded-2xl text-xs max-w-[90%] shadow-xs space-y-3">
                <p>I found 3 verified options in stock that fit marathon training within your budget:</p>
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-slate-200 shrink-0 overflow-hidden">
                      <ProductImage
                        src="https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=100&q=80&auto=format&fit=crop"
                        alt="Pro Running Shoes"
                        productName="Pro Running Shoes"
                        category="Running"
                        className="w-full h-full object-cover"
                        containerClassName="w-full h-full"
                      />
                    </div>
                    <div>
                      <div className="font-bold text-slate-900">Pro Marathon Runner v2</div>
                      <div className="text-[11px] text-slate-500">₹3,499 • Carbon plate, lightweight</div>
                    </div>
                  </div>
                  <span className="text-emerald-700 font-semibold text-[10px] bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                    In Stock
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 7. Trust & Governance Boundaries (What AI Can vs Cannot Do) */}
      <section className="py-16 sm:py-24 bg-slate-50 border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
              Deterministic Security Invariants
            </h2>
            <p className="text-sm text-slate-600">
              Clear boundaries guarantee that AI assists discovery without ever overriding financial truth.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {/* What AI Can Do */}
            <div className="bg-white border border-emerald-200 rounded-2xl p-6 shadow-xs space-y-4">
              <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm">
                <span className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center text-xs">
                  ✓
                </span>
                <span>What the AI Agent Can Do</span>
              </div>
              <ul className="space-y-2.5 text-xs text-slate-700">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 font-bold">•</span>
                  <span>Search product catalog via semantic intent</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 font-bold">•</span>
                  <span>Suggest complementary accessories and cross-sells</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 font-bold">•</span>
                  <span>Draft structured purchase intents on behalf of buyers</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 font-bold">•</span>
                  <span>Answer product specification questions</span>
                </li>
              </ul>
            </div>

            {/* What AI Cannot Do */}
            <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
              <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
                <span className="w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center text-xs text-rose-600 font-bold">
                  ✕
                </span>
                <span>What the AI Agent Cannot Do (Blocked)</span>
              </div>
              <ul className="space-y-2.5 text-xs text-slate-700">
                <li className="flex items-start gap-2">
                  <span className="text-rose-500 font-bold">•</span>
                  <span>Cannot modify database prices or apply unauthorized discounts</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-rose-500 font-bold">•</span>
                  <span>Cannot bypass deterministic policy evaluations</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-rose-500 font-bold">•</span>
                  <span>Cannot execute payments without merchant gateway authorization</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-rose-500 font-bold">•</span>
                  <span>Cannot bypass cryptographic signature verification</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* 8. Seven-Step Transaction Lifecycle */}
      <section className="py-16 sm:py-24 bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
              Seven-Step Transaction Lifecycle
            </h2>
            <p className="text-sm text-slate-600">
              End-to-end architectural execution from buyer intent to immutable settlement.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-7 gap-4">
            {ARCHITECTURE_STEPS.map((step) => (
              <div
                key={step.step}
                className="bg-slate-50 border border-slate-200 rounded-2xl p-4 space-y-3 flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-indigo-600">{step.step}</span>
                    <Badge variant="neutral" size="xs">
                      {step.badge}
                    </Badge>
                  </div>
                  <h3 className="font-bold text-xs text-slate-900 leading-snug">{step.title}</h3>
                  <p className="text-[11px] text-slate-600 leading-relaxed">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 9. Final CTA */}
      <section className="py-16 sm:py-24 bg-slate-900 text-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
            Ready to experience governed AI commerce?
          </h2>
          <p className="text-sm sm:text-base text-slate-300 max-w-xl mx-auto">
            Discover how natural language discovery pairs with deterministic financial security.
          </p>
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/shopping"
              className="inline-flex items-center justify-center font-bold text-base px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg transition-all gap-2 w-full sm:w-auto"
            >
              <span>Start Shopping</span>
              <ArrowRightIcon size={16} />
            </Link>
            <Link
              href="/demo"
              className="inline-flex items-center justify-center font-semibold text-base px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 shadow-md transition-all w-full sm:w-auto"
            >
              Launch Flagship Demo
            </Link>
          </div>
        </div>
      </section>

      {/* 10. Clean Light Theme Footer */}
      <footer className="border-t border-slate-200 bg-white text-slate-500 text-xs py-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-lg bg-slate-900 text-white flex items-center justify-center font-bold text-xs">
              ⚡
            </div>
            <span className="font-bold text-slate-900">Agentic Commerce OS</span>
            <span>— Governed AI E-Commerce &amp; Merchant Platform</span>
          </div>

          <div className="flex items-center gap-6">
            <Link href="/shopping" className="hover:text-slate-900 transition-colors">
              Storefront
            </Link>
            <Link href="/agent-commerce" className="hover:text-slate-900 transition-colors">
              AI-to-AI Commerce
            </Link>
            <Link href="/demo" className="hover:text-slate-900 transition-colors">
              Judge Mode
            </Link>
            {userProfile?.role === 'merchant_admin' && (
              <Link href="/dashboard" className="text-indigo-600 font-semibold hover:text-indigo-800">
                Merchant Console
              </Link>
            )}
          </div>
        </div>
      </footer>

      {/* Auth Modal */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        authConfig={authConfig}
        onSuccess={(user) => {
          setUserProfile(user);
        }}
      />
    </div>
  );
}
