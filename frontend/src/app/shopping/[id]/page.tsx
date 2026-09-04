'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiClient, extractErrorMessage } from '@/lib/api';
import { StorefrontHeader } from '@/components/storefront/StorefrontHeader';
import { AIShoppingDrawer, AIMessage } from '@/components/storefront/AIShoppingDrawer';
import { CartDrawer, CartData } from '@/components/storefront/CartDrawer';
import { AuthModal, AuthConfig } from '@/components/auth/AuthModal';
import { Toast, ToastProps } from '@/components/ui/Toast';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  ShoppingBagIcon,
  SparklesIcon,
  ShieldCheckIcon,
  CheckIcon,
  PlusIcon,
  MinusIcon,
  StarIcon,
} from '@/components/ui/Icons';
import { PriceComparisonCard } from '@/components/comparison/PriceComparisonCard';
import { PriceComparisonModal } from '@/components/comparison/PriceComparisonModal';
import { VirtualTryOnModal } from '@/components/virtual_tryon/VirtualTryOnModal';
import { NegotiationModal } from '@/components/negotiation/NegotiationModal';
import { TryOnEligibilityResponse } from '@/lib/types/virtual_tryon';
import { UserProfile } from '@/lib/types/user';
import { ProductImage } from '@/components/ui/ProductImage';

interface ProductDetail {
  id: string;
  merchant_id: string;
  name: string;
  brand?: string;
  description?: string;
  category: string;
  subcategory?: string;
  price: number;
  mrp?: number;
  currency: string;
  stock_quantity: number;
  in_stock: boolean;
  image_url?: string;
  image_urls?: string[];
  gallery_images?: string[];
  variant_images?: Record<string, string>;
  rating?: number;
  review_count?: number;
  gtin?: string;
  model_number?: string;
  sku?: string;
  tags?: string[];
  lowest_market_price?: number | null;
  external_stores_count?: number;
  attributes?: Record<string, unknown>;
}

interface SmartBundle {
  target_product_id: string;
  target_product_name: string;
  target_price: number;
  confidence: number;
  evidence: string;
  bundle_price: number;
  savings: number;
}

interface FitRecommendation {
  status: 'RECOMMENDED' | 'INSUFFICIENT_DATA';
  recommended_size?: string;
  explanation: string;
  confidence_score: number;
  fit_tendency: string;
}

interface ReviewSummary {
  status: 'AVAILABLE' | 'NO_REVIEWS';
  review_count: number;
  average_rating: number;
  overall_sentiment: string;
  pros: string[];
  cons: string[];
  fit_summary: string;
}

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productId = params?.id as string;

  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [isAdding, setIsAdding] = useState(false);
  const [isComparisonModalOpen, setIsComparisonModalOpen] = useState(false);
  const [isVTOOpen, setIsVTOOpen] = useState(false);
  const [isVTOSupported, setIsVTOSupported] = useState(false);
  const [selectedColor, setSelectedColor] = useState<string>('Classic Black');
  const [selectedSize, setSelectedSize] = useState<string>('Medium');
  const [isNegotiationOpen, setIsNegotiationOpen] = useState(false);

  // Intelligence state
  const [bundles, setBundles] = useState<SmartBundle[]>([]);
  const [fitData, setFitData] = useState<FitRecommendation | null>(null);
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary | null>(null);
  const [addingBundleIndex, setAddingBundleIndex] = useState<number | null>(null);

  // Session & Cart state
  const [sessionId, setSessionId] = useState('');
  const [cart, setCart] = useState<CartData>({ items: [], total_amount: 0, currency: 'INR' });
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // AI Drawer state
  const [isAIOpen, setIsAIOpen] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiMessages, setAiMessages] = useState<AIMessage[]>([
    {
      role: 'assistant',
      content: 'I can answer questions about this product, fit, durability, or suggest compatible gear.',
      timestamp: 'Just now',
    },
  ]);

  // Toast
  const [toast, setToast] = useState<ToastProps | null>(null);
  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type, onClose: () => setToast(null) });
  };

  // 1. Initialize session & user
  useEffect(() => {
    let sid = localStorage.getItem('cart_session_id');
    if (!sid) {
      sid = `sess_${Math.random().toString(36).substring(2, 10)}`;
      localStorage.setItem('cart_session_id', sid);
    }
    setSessionId(sid);

    apiClient
      .get('/auth/config')
      .then((res) => setAuthConfig(res.data))
      .catch(() => {});

    const token = localStorage.getItem('access_token');
    if (token) {
      apiClient
        .get('/auth/me', { headers: { Authorization: `Bearer ${token}` } })
        .then((res) => setUserProfile(res.data))
        .catch(() => {});
    }
  }, []);

  // 2. Fetch product details & intelligence
  const fetchProduct = useCallback(async () => {
    if (!productId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get(`/products/${productId}`);
      const productData = res.data;
      setProduct(productData);
      if (productData.attributes?.color && typeof productData.attributes.color === 'string') {
        setSelectedColor(productData.attributes.color);
      }
      if (productData.attributes?.size && typeof productData.attributes.size === 'string') {
        setSelectedSize(productData.attributes.size);
      }

      // Record interaction signal
      const sid = localStorage.getItem('cart_session_id');
      if (sid) {
        apiClient.post('/personalization/interactions', {
          product_id: productId,
          event_type: 'PRODUCT_VIEW',
          session_id: sid,
          metadata: { name: res.data.name, category: res.data.category },
        }).catch(() => {});
      }

      // Fetch smart bundles
      apiClient.get(`/personalization/products/${productId}/bundles`)
        .then((bRes) => setBundles(bRes.data || []))
        .catch(() => setBundles([]));

      // Fetch fit recommendation
      apiClient.get(`/personalization/products/${productId}/fit-recommendation`)
        .then((fRes) => setFitData(fRes.data))
        .catch(() => setFitData(null));

      // Fetch review summary
      apiClient.get(`/personalization/products/${productId}/reviews/summary`)
        .then((rRes) => setReviewSummary(rRes.data))
        .catch(() => setReviewSummary(null));

      // Check Virtual Try-On eligibility
      apiClient.post<TryOnEligibilityResponse>('/virtual-tryon/check', { product_id: productId })
        .then((vRes) => setIsVTOSupported(vRes.data.supported))
        .catch(() => setIsVTOSupported(false));

    } catch (err) {
      const errMsg = extractErrorMessage(err, 'Product not found or unavailable.');
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    fetchProduct();
  }, [fetchProduct]);

  // 3. Fetch cart
  const fetchCart = useCallback(async (sid: string) => {
    if (!sid) return;
    try {
      const res = await apiClient.get(`/cart?session_id=${sid}`);
      setCart(res.data);
    } catch {
      // safe cart error
    }
  }, []);

  useEffect(() => {
    if (sessionId) {
      fetchCart(sessionId);
    }
  }, [sessionId, fetchCart]);

  // Add main product to cart
  const handleAddToCart = async () => {
    if (!product || !sessionId) return;
    setIsAdding(true);
    try {
      const res = await apiClient.post('/cart/items', {
        session_id: sessionId,
        product_id: product.id,
        quantity,
      });
      setCart(res.data);
      showToast(`Added ${quantity} × ${product.name} to cart.`, 'success');
      setIsCartOpen(true);
    } catch (err) {
      showToast(extractErrorMessage(err, 'Failed to add item to cart.'), 'error');
    } finally {
      setIsAdding(false);
    }
  };

  // Add Smart Bundle to cart
  const handleAddBundle = async (bundle: SmartBundle, index: number) => {
    if (!product || !sessionId) return;
    setAddingBundleIndex(index);
    try {
      // Add main product
      await apiClient.post('/cart/items', {
        session_id: sessionId,
        product_id: product.id,
        quantity: 1,
      });

      // Add complementary bundle product
      const res = await apiClient.post('/cart/items', {
        session_id: sessionId,
        product_id: bundle.target_product_id,
        quantity: 1,
      });

      setCart(res.data);
      showToast(`Added "${product.name}" + "${bundle.target_product_name}" bundle to cart!`, 'success');
      setIsCartOpen(true);
    } catch (err) {
      showToast(extractErrorMessage(err, 'Failed to add bundle to cart.'), 'error');
    } finally {
      setAddingBundleIndex(null);
    }
  };

  // AI Chat
  const handleSendAIMessage = async (messageText: string) => {
    if (!sessionId) return;
    const userMsg: AIMessage = {
      role: 'user',
      content: messageText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setAiMessages((prev) => [...prev, userMsg]);
    setAiLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await apiClient.post(
        '/ai/chat',
        { session_id: sessionId, message: messageText },
        { headers }
      );

      const aiResponse = res.data;
      const assistantMsg: AIMessage = {
        role: 'assistant',
        content: aiResponse.reply || "I've reviewed the catalog.",
        recommendations: (aiResponse.products || []).map((p: Record<string, unknown>) => ({
          id: String(p.id),
          name: String(p.name),
          price: Number(p.price),
          category: String(p.category || 'Gear'),
          description: p.description ? String(p.description) : undefined,
          image_url: p.image_url ? String(p.image_url) : undefined,
          stock_quantity: p.stock_quantity ? Number(p.stock_quantity) : 10,
        })),
        order_review: aiResponse.order_review,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setAiMessages((prev) => [...prev, assistantMsg]);
      await fetchCart(sessionId);
    } catch {
      setAiMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I encountered an issue checking the catalog.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setAiLoading(false);
    }
  };

  const variantImages = (product?.attributes as Record<string, unknown>)?.variant_images as Record<string, string> | undefined;
  const variantImage = selectedColor && variantImages && variantImages[selectedColor] ? variantImages[selectedColor] : null;

  const imageSrc =
    variantImage ||
    product?.image_url ||
    (product?.image_urls && product.image_urls.length > 0 ? product.image_urls[0] : null) ||
    'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop&q=80';

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      {toast && <Toast {...toast} />}

      <StorefrontHeader
        cartItemCount={cart.items.reduce((s, i) => s + i.quantity, 0)}
        onOpenCart={() => setIsCartOpen(true)}
        onOpenAI={() => setIsAIOpen(true)}
        onOpenAuth={() => setIsAuthOpen(true)}
        onSignOut={() => {
          localStorage.removeItem('access_token');
          setUserProfile(null);
          showToast('Signed out.', 'info');
        }}
        searchQuery=""
        onSearchChange={() => router.push('/shopping')}
        userProfile={userProfile}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
          <Link href="/" className="hover:text-slate-900 transition-colors">
            Home
          </Link>
          <span>/</span>
          <Link href="/shopping" className="hover:text-slate-900 transition-colors">
            Storefront
          </Link>
          <span>/</span>
          <span className="text-slate-900 font-bold truncate max-w-xs">{product?.name || 'Product Detail'}</span>
        </div>

        {loading ? (
          <div className="p-16 text-center text-slate-400 space-y-3">
            <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm font-medium">Loading authoritative product details...</p>
          </div>
        ) : error || !product ? (
          <div className="p-12 text-center bg-white rounded-3xl border border-slate-200 space-y-4 max-w-md mx-auto">
            <p className="text-sm text-rose-600 font-semibold">{error || 'Product not found.'}</p>
            <Link href="/shopping">
              <Button variant="primary" size="md">
                ← Return to Storefront
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Top Grid: Image + Main Purchasing Box */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 bg-white rounded-3xl border border-slate-200 p-6 sm:p-10 shadow-xs">
              {/* Left: Product Image Box */}
              <div className="lg:col-span-6 space-y-4">
                <div className="aspect-square bg-slate-100 rounded-2xl overflow-hidden relative border border-slate-100">
                  <ProductImage
                    src={imageSrc}
                    alt={product.name}
                    productId={product.id}
                    productName={product.name}
                    category={product.category}
                    subcategory={product.subcategory}
                    className="w-full h-full object-cover object-center"
                    containerClassName="w-full h-full"
                    priority
                  />
                  <div className="absolute top-4 left-4 z-20">
                    <span className="px-3 py-1 rounded-lg bg-white/95 text-xs font-bold text-slate-800 shadow-xs uppercase tracking-wider">
                      {product.category}
                    </span>
                  </div>
                  <div className="absolute top-4 right-4 z-20">
                    <Badge variant={product.in_stock ? 'success' : 'error'} size="sm" dot={product.in_stock}>
                      {product.in_stock ? `${product.stock_quantity} in stock` : 'Out of Stock'}
                    </Badge>
                  </div>
                </div>

                {/* Sizing & Fit Intelligence Card */}
                {fitData && (
                  <div className="p-4 rounded-2xl bg-indigo-50/60 border border-indigo-100 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-indigo-900 flex items-center gap-1.5">
                        <span>👟</span>
                        <span>Size &amp; Fit Intelligence</span>
                      </span>
                      {(() => {
                        const rawScore =
                          typeof fitData.confidence_score === 'number' && !isNaN(fitData.confidence_score)
                            ? fitData.confidence_score
                            : typeof (fitData as unknown as Record<string, unknown>).confidence === 'number' && !isNaN((fitData as unknown as Record<string, unknown>).confidence as number)
                            ? ((fitData as unknown as Record<string, unknown>).confidence as number)
                            : null;
                        return rawScore !== null ? (
                          <span className="text-[10px] font-semibold text-indigo-700 bg-white px-2 py-0.5 rounded border border-indigo-200">
                            {Math.round(rawScore * 100)}% Confidence
                          </span>
                        ) : (
                          <span className="text-[10px] font-semibold text-indigo-700 bg-white px-2 py-0.5 rounded border border-indigo-200">
                            Fit Verified
                          </span>
                        );
                      })()}
                    </div>
                    <p className="text-xs text-indigo-950 font-medium leading-relaxed">
                      {fitData.explanation}
                    </p>
                  </div>
                )}
              </div>

              {/* Right: Product Meta & Purchase Controls */}
              <div className="lg:col-span-6 flex flex-col justify-between space-y-6">
                <div className="space-y-4">
                  <div>
                    <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider block mb-1">
                      Verified Apex Catalog
                    </span>
                    <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                      {product.name}
                    </h1>
                  </div>

                  {/* Price Display */}
                  <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
                    <div className="flex items-baseline gap-3">
                      <span className="text-3xl font-black text-slate-900 font-mono">
                        ₹{Number(product.price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                      {product.mrp && product.mrp > product.price && (
                        <span className="text-base font-mono text-slate-400 line-through">
                          ₹{Number(product.mrp).toLocaleString('en-IN')}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-slate-500 font-medium">
                      (Inclusive of all taxes • Locked Catalog Price)
                    </span>
                  </div>

                  {/* BuyHatke-Style Embedded Price Comparison Card */}
                  <PriceComparisonCard
                    productId={product.id}
                    onOpenFullModal={() => setIsComparisonModalOpen(true)}
                  />

                  {/* Description */}
                  <div className="space-y-2">
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Description</h3>
                    <p className="text-sm text-slate-600 leading-relaxed">
                      {product.description ||
                        'Premium high-performance athletic gear rigorously tested for endurance, comfort, and professional performance.'}
                    </p>
                  </div>

                  {/* Trust Invariants */}
                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center gap-2.5 text-xs text-slate-700 font-medium">
                      <ShieldCheckIcon size={16} className="text-indigo-600 shrink-0" />
                      <span>Deterministic Price Lock</span>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center gap-2.5 text-xs text-slate-700 font-medium">
                      <CheckIcon size={16} className="text-emerald-600 shrink-0" />
                      <span>Razorpay Secure Settle</span>
                    </div>
                  </div>
                </div>

                {/* Variant Selectors for Wearable/Try-On Products */}
                {isVTOSupported && (
                  <div className="space-y-3 pt-3 border-t border-slate-100">
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-slate-700 uppercase tracking-wider">Color:</span>
                        <span className="text-indigo-600 font-semibold">{selectedColor}</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {['Classic Black', 'Navy Blue', 'Pure White', 'Crimson Red'].map((c) => (
                          <button
                            key={c}
                            type="button"
                            onClick={() => setSelectedColor(c)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
                              selectedColor === c
                                ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                                : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                            }`}
                          >
                            {c}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-slate-700 uppercase tracking-wider">Size:</span>
                        <span className="text-indigo-600 font-semibold">{selectedSize}</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {['UK 7 / Small', 'UK 8 / Medium', 'UK 9 / Large', 'UK 10 / XL'].map((s) => {
                          const label = s.includes('/') ? s.split('/')[1].trim() : s;
                          return (
                            <button
                              key={s}
                              type="button"
                              onClick={() => setSelectedSize(label)}
                              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
                                selectedSize === label
                                  ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                                  : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                              }`}
                            >
                              {s}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}

                {/* Purchase Actions */}
                <div className="space-y-4 pt-4 border-t border-slate-100">
                  <div className="flex items-center gap-4">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Quantity:</span>
                    <div className="flex items-center border border-slate-200 rounded-xl bg-slate-50 overflow-hidden">
                      <button
                        type="button"
                        onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                        disabled={quantity <= 1 || !product.in_stock}
                        className="p-2 text-slate-600 hover:bg-slate-200 transition-colors disabled:opacity-40"
                      >
                        <MinusIcon size={14} />
                      </button>
                      <span className="px-4 py-1.5 text-sm font-bold text-slate-900 min-w-10 text-center font-mono">
                        {quantity}
                      </span>
                      <button
                        type="button"
                        onClick={() => setQuantity((q) => Math.min(product.stock_quantity || 10, q + 1))}
                        disabled={quantity >= (product.stock_quantity || 10) || !product.in_stock}
                        className="p-2 text-slate-600 hover:bg-slate-200 transition-colors disabled:opacity-40"
                      >
                        <PlusIcon size={14} />
                      </button>
                    </div>
                  </div>

                  {/* Primary Ecommerce Action */}
                  <div className="space-y-3">
                    <Button
                      onClick={handleAddToCart}
                      disabled={!product.in_stock || isAdding}
                      isLoading={isAdding}
                      variant="primary"
                      size="lg"
                      className="w-full font-bold shadow-md hover:shadow-lg py-3.5 bg-indigo-600 hover:bg-indigo-700 text-white flex items-center justify-center gap-2"
                      leftIcon={<ShoppingBagIcon size={18} />}
                    >
                      {product.in_stock ? `Add to Cart • ₹${(product.price * quantity).toLocaleString('en-IN')}` : 'Out of Stock'}
                    </Button>

                    {/* Secondary AI & Shopping Assistance Row */}
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <Button
                        onClick={() => setIsNegotiationOpen(true)}
                        variant="outline"
                        size="md"
                        className="flex-1 min-w-[150px] border-emerald-300 bg-emerald-50/80 hover:bg-emerald-100 text-emerald-800 font-bold text-xs py-2.5 shadow-2xs"
                        leftIcon={<SparklesIcon size={15} className="text-emerald-600" />}
                      >
                        🤝 Ask for a better price
                      </Button>

                      {isVTOSupported && (
                        <Button
                          onClick={() => setIsVTOOpen(true)}
                          variant="outline"
                          size="md"
                          className="flex-1 min-w-[110px] border-indigo-200 bg-indigo-50/70 hover:bg-indigo-100 text-indigo-700 font-bold text-xs py-2.5 shadow-2xs"
                          leftIcon={<SparklesIcon size={15} className="text-indigo-600" />}
                        >
                          AI Try-On
                        </Button>
                      )}

                      <Button
                        onClick={() => setIsComparisonModalOpen(true)}
                        variant="outline"
                        size="md"
                        className="flex-1 min-w-[120px] border-slate-200 bg-white hover:bg-slate-50 text-slate-700 font-semibold text-xs py-2.5 shadow-2xs"
                        leftIcon={<SparklesIcon size={15} className="text-slate-500" />}
                      >
                        Compare Prices
                      </Button>

                      <Button
                        onClick={() => {
                          setIsAIOpen(true);
                          handleSendAIMessage(`Tell me more about ${product.name} and why it is good for ${product.category}.`);
                        }}
                        variant="outline"
                        size="md"
                        className="flex-1 min-w-[90px] border-slate-200 bg-white hover:bg-slate-50 text-slate-700 font-semibold text-xs py-2.5 shadow-2xs"
                      >
                        Ask AI
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Smart Bundles Section */}
            {bundles.length > 0 && (
              <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div>
                    <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                      <span>⚡</span>
                      <span>Frequently Bought Together</span>
                    </h2>
                    <p className="text-xs text-slate-500">Co-purchased by marathon runners &amp; athletes</p>
                  </div>
                  <Badge variant="purple" size="sm">
                    Instant Smart Bundle
                  </Badge>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {bundles.map((b, idx) => (
                    <div
                      key={b.target_product_id}
                      className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex flex-col justify-between gap-3 hover:border-indigo-300 transition-all"
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-xs text-slate-900">{b.target_product_name}</span>
                          <span className="text-[11px] font-extrabold text-slate-900 font-mono">
                            +₹{Number(b.target_price).toLocaleString('en-IN')}
                          </span>
                        </div>
                        <p className="text-xs text-slate-600 leading-snug">{b.evidence}</p>
                      </div>

                      <div className="pt-2 border-t border-slate-200/60 flex items-center justify-between">
                        <span className="text-xs text-emerald-700 font-semibold">
                          Bundle Total: <strong className="font-mono">₹{Number(b.bundle_price).toLocaleString('en-IN')}</strong>
                        </span>
                        <Button
                          onClick={() => handleAddBundle(b, idx)}
                          isLoading={addingBundleIndex === idx}
                          variant="primary"
                          size="xs"
                        >
                          Add Both to Cart
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Review Intelligence Section */}
            <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div>
                  <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <StarIcon size={18} className="text-amber-500" />
                    <span>Customer Review &amp; Sentiment Intelligence</span>
                  </h2>
                  <p className="text-xs text-slate-500">Grounded analysis synthesized from authentic customer reviews</p>
                </div>
                {reviewSummary?.status === 'AVAILABLE' && (
                  <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                    ★ {reviewSummary.average_rating} ({reviewSummary.review_count} Reviews)
                  </span>
                )}
              </div>

              {reviewSummary?.status === 'AVAILABLE' ? (
                <div className="space-y-4">
                  <p className="text-xs text-slate-700 font-medium">
                    {reviewSummary.overall_sentiment}
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-200 space-y-1.5">
                      <span className="font-bold text-emerald-900 block">Highlights &amp; Pros</span>
                      <ul className="space-y-1 text-emerald-800 list-disc list-inside">
                        {reviewSummary.pros.map((p, i) => (
                          <li key={i}>{p}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 space-y-1.5">
                      <span className="font-bold text-amber-900 block">Considerations</span>
                      <ul className="space-y-1 text-amber-800 list-disc list-inside">
                        {reviewSummary.cons.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-slate-500">
                  No verified customer reviews available yet for this product.
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* AIShoppingDrawer */}
      <AIShoppingDrawer
        isOpen={isAIOpen}
        onClose={() => setIsAIOpen(false)}
        messages={aiMessages}
        onSendMessage={handleSendAIMessage}
        isLoading={aiLoading}
        onAddToCart={async (rec) => {
          if (!sessionId) return;
          try {
            const res = await apiClient.post('/cart/items', {
              session_id: sessionId,
              product_id: rec.id,
              quantity: 1,
            });
            setCart(res.data);
            showToast(`Added ${rec.name} to cart.`, 'success');
            setIsCartOpen(true);
          } catch (err) {
            showToast(extractErrorMessage(err, 'Failed to add to cart.'), 'error');
          }
        }}
        addingProductId={isAdding ? (product?.id || null) : null}
        onOpenVoiceSearch={() => {}}
        onConfirmOrderReview={() => router.push('/shopping')}
        onApproveAndPayOrderReview={() => router.push('/shopping')}
      />

      {/* CartDrawer */}
      <CartDrawer
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        cart={cart}
        updatingCartItemId={null}
        onUpdateQuantity={async (itemId, newQty) => {
          if (!sessionId) return;
          try {
            const res = await apiClient.put(`/cart/items/${itemId}`, {
              session_id: sessionId,
              quantity: newQty,
            });
            setCart(res.data);
          } catch (err) {
            showToast(extractErrorMessage(err, 'Failed to update quantity.'), 'error');
          }
        }}
        onRemoveItem={async (itemId) => {
          if (!sessionId) return;
          try {
            const res = await apiClient.delete(`/cart/items/${itemId}?session_id=${sessionId}`);
            setCart(res.data);
          } catch (err) {
            showToast(extractErrorMessage(err, 'Failed to remove item.'), 'error');
          }
        }}
        onClearCart={async () => {
          if (!sessionId) return;
          try {
            const res = await apiClient.delete(`/cart?session_id=${sessionId}`);
            setCart(res.data);
          } catch (err) {
            showToast(extractErrorMessage(err, 'Failed to clear cart.'), 'error');
          }
        }}
        onCheckout={() => router.push('/shopping')}
      />

      {/* AuthModal */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        authConfig={authConfig}
        onSuccess={(profile) => {
          setUserProfile(profile);
          showToast(`Welcome back, ${profile.full_name || profile.email}!`, 'success');
        }}
      />

      {/* PriceComparisonModal */}
      <PriceComparisonModal
        isOpen={isComparisonModalOpen}
        onClose={() => setIsComparisonModalOpen(false)}
        productId={productId}
        onBuyOnApex={() => handleAddToCart()}
      />

      {/* VirtualTryOnModal */}
      {product && (
        <VirtualTryOnModal
          isOpen={isVTOOpen}
          onClose={() => setIsVTOOpen(false)}
          product={{
            id: product.id,
            name: product.name,
            brand: product.brand,
            category: product.category,
            price: product.price,
            image_url: imageSrc,
            color: selectedColor || (typeof product.attributes?.color === 'string' ? product.attributes.color : undefined),
            size: selectedSize || (typeof product.attributes?.size === 'string' ? product.attributes.size : undefined),
          }}
          sessionId={sessionId}
          onAddToCart={() => {
            handleAddToCart();
            setIsVTOOpen(false);
          }}
          onSelectProductToTry={(targetId) => {
            setIsVTOOpen(false);
            router.push(`/shopping/${targetId}`);
          }}
        />
      )}

      {/* NegotiationModal */}
      {product && (
        <NegotiationModal
          isOpen={isNegotiationOpen}
          onClose={() => setIsNegotiationOpen(false)}
          product={{
            id: product.id,
            name: product.name,
            price: product.price,
            currency: product.currency || 'INR',
            stock_quantity: product.stock_quantity || 10,
            category: product.category,
            image_url: imageSrc,
          }}
          customerEmail={userProfile?.email || 'shopper@apex.local'}
          onOrderCompleted={(orderId) => {
            showToast(`Negotiated order ${orderId} confirmed!`, 'success');
          }}
        />
      )}
    </div>
  );
}
