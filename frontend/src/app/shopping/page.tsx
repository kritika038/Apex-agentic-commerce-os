'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient, extractErrorMessage } from '@/lib/api';
import { loadRazorpayScript, RazorpayCheckoutOptions } from '@/lib/razorpay';
import { StorefrontHeader } from '@/components/storefront/StorefrontHeader';
import { CategoryTabs } from '@/components/storefront/CategoryTabs';
import { ProductGrid } from '@/components/storefront/ProductGrid';
import { Product } from '@/components/storefront/ProductCard';
import { AIShoppingDrawer, AIMessage } from '@/components/storefront/AIShoppingDrawer';
import { CartDrawer, CartData } from '@/components/storefront/CartDrawer';
import {
  CheckoutModal,
  PaymentReceipt,
  PaymentConfig,
  DeliveryAddressData,
} from '@/components/storefront/CheckoutModal';
import { AuthModal, AuthConfig } from '@/components/auth/AuthModal';
import { VoiceSearchModal } from '@/components/storefront/VoiceSearchModal';
import { VisualSearchModal } from '@/components/storefront/VisualSearchModal';
import { Toast, ToastProps } from '@/components/ui/Toast';
import { SparklesIcon } from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';
import { PriceComparisonModal } from '@/components/comparison/PriceComparisonModal';
import { VirtualTryOnModal } from '@/components/virtual_tryon/VirtualTryOnModal';
import { CartPricingBreakdown } from '@/lib/types/rewards';
import { UserProfile } from '@/lib/types/user';

export default function ShoppingPage() {
  // Session & Auth State
  const [sessionId, setSessionId] = useState('');
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // Virtual Try-On State
  const [vtoProduct, setVtoProduct] = useState<Product | null>(null);

  // Price Comparison Modal State
  const [comparisonProductId, setComparisonProductId] = useState<string | null>(null);

  // Marketplace Brand & Price Filter State
  const [selectedBrand, setSelectedBrand] = useState('All Brands');
  const [selectedPriceRange, setSelectedPriceRange] = useState<string>('all');

  // Catalog State
  const [catalogProducts, setCatalogProducts] = useState<Product[]>([]);
  const [filteredProducts, setFilteredProducts] = useState<Product[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'featured' | 'price-low' | 'price-high' | 'stock'>('featured');
  const [inStockOnly, setInStockOnly] = useState(false);
  const [activeStructuredIntent, setActiveStructuredIntent] = useState<{
    query?: string;
    category?: string;
    max_price?: number | null;
    min_price?: number | null;
    quantity?: number;
    sort?: string | null;
    in_stock_only?: boolean;
    clarification_needed?: boolean;
    clarification_reason?: string;
  } | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  // Cart & Pricing State
  const [cart, setCart] = useState<CartData>({ items: [], total_amount: 0, currency: 'INR' });
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [addingProductId, setAddingProductId] = useState<string | null>(null);
  const [updatingCartItemId, setUpdatingCartItemId] = useState<string | null>(null);
  const [appliedCoupon, setAppliedCoupon] = useState<string | null>(null);
  const [appliedVoucher, setAppliedVoucher] = useState<string | null>(null);
  const [useCoins, setUseCoins] = useState(false);
  const [pricingBreakdown, setPricingBreakdown] = useState<CartPricingBreakdown | null>(null);

  // Voice & Visual Search Modal States
  const [isVoiceModalOpen, setIsVoiceModalOpen] = useState(false);
  const [isVisualModalOpen, setIsVisualModalOpen] = useState(false);

  // AI Assistant Drawer State
  const [isAIOpen, setIsAIOpen] = useState(false);
  const [aiMessages, setAiMessages] = useState<AIMessage[]>([
    {
      role: 'assistant',
      content:
        'Hello! I am your AI Shopping Assistant for Apex Sports. Tell me your workout goals, budget, or preferred sport, and I will recommend verified gear.',
      timestamp: 'Just now',
    },
  ]);
  const [aiLoading, setAiLoading] = useState(false);

  // Checkout State
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [checkoutStep, setCheckoutStep] = useState<
    'address' | 'review' | 'approval_required' | 'policy_blocked' | 'processing' | 'verifying' | 'success' | 'failed'
  >('address');
  const [approvalDetails, setApprovalDetails] = useState<{
    approvalId?: string;
    amount: number;
    threshold: number;
    reason?: string;
  } | null>(null);
  const [deliveryAddress, setDeliveryAddress] = useState<DeliveryAddressData>({
    full_name: '',
    phone: '',
    email: '',
    address_line1: '',
    address_line2: '',
    landmark: '',
    city: '',
    state: '',
    pin_code: '',
    country: 'India',
  });
  const [paymentConfig, setPaymentConfig] = useState<PaymentConfig | null>(null);
  const [receipt, setReceipt] = useState<PaymentReceipt | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  // Toast State
  const [toast, setToast] = useState<ToastProps | null>(null);

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type, onClose: () => setToast(null) });
  };

  // 1. Initialize Session & Load Profile / Auth Config / Payment Config / Saved Address
  useEffect(() => {
    let currentSessionId = localStorage.getItem('cart_session_id');
    if (!currentSessionId) {
      currentSessionId = `sess_${Math.random().toString(36).substring(2, 10)}`;
      localStorage.setItem('cart_session_id', currentSessionId);
    }
    setSessionId(currentSessionId);

    // Check URL parameters for assistant or search query
    if (typeof window !== 'undefined') {
      const searchParams = new URLSearchParams(window.location.search);
      if (searchParams.get('assistant') === 'open' || searchParams.get('ai') === 'true') {
        setIsAIOpen(true);
      }
      const q = searchParams.get('q');
      if (q) {
        setSearchQuery(q);
      }
    }

    // Restore saved address
    const savedAddress = localStorage.getItem('checkout_delivery_address');
    if (savedAddress) {
      try {
        setDeliveryAddress(JSON.parse(savedAddress));
      } catch {
        // Ignore JSON parse error
      }
    }

    // Fetch auth config
    apiClient
      .get('/auth/config')
      .then((res) => setAuthConfig(res.data))
      .catch((err) => console.error('Error fetching auth config', err));

    // Fetch payment config
    apiClient
      .get('/payments/config')
      .then((res) => setPaymentConfig(res.data))
      .catch((err) => console.error('Error fetching payment config', err));

    // Check token and user profile
    const token = localStorage.getItem('access_token');
    if (token) {
      apiClient
        .get('/auth/me', { headers: { Authorization: `Bearer ${token}` } })
        .then((res) => {
          setUserProfile(res.data);
          if (res.data?.email && !savedAddress) {
            setDeliveryAddress((p) => ({
              ...p,
              email: res.data.email,
              full_name: res.data.full_name || p.full_name,
            }));
          }
        })
        .catch(() => {
          localStorage.removeItem('access_token');
          setUserProfile(null);
        });
    }
  }, []);

  // 2. Fetch Catalog Products
  const fetchCatalog = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const res = await apiClient.get('/products?limit=300');
      const formatted: Product[] = (res.data || []).map((item: {
        id: string;
        name: string;
        brand?: string;
        category?: string;
        subcategory?: string;
        price: number | string;
        mrp?: number | string;
        stock_quantity?: number;
        image_url?: string;
        description?: string;
        rating?: number;
        review_count?: number;
        lowest_market_price?: number | null;
        external_stores_count?: number;
      }) => ({
        id: item.id,
        name: item.name,
        brand: item.brand,
        category: item.category || 'Gear',
        subcategory: item.subcategory,
        price: Number(item.price),
        mrp: item.mrp ? Number(item.mrp) : undefined,
        stock_quantity: item.stock_quantity ?? 10,
        image_url: item.image_url,
        description: item.description,
        rating: item.rating ?? 4.5,
        review_count: item.review_count ?? 50,
        lowest_market_price: item.lowest_market_price,
        external_stores_count: item.external_stores_count ?? 0,
      }));
      setCatalogProducts(formatted);
      setFilteredProducts(formatted);
      setCatalogError(null);
    } catch (err: unknown) {
      console.error('Error fetching products', err);
      const errMsg = extractErrorMessage(err, 'Failed to connect to the catalog server. Please check backend connection.');
      setCatalogError(errMsg);
      showToast(errMsg, 'error');
    } finally {
      setCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCatalog();
  }, [fetchCatalog]);

  // 3. Fetch Active Session Cart
  const fetchCart = useCallback(async (sid?: string) => {
    const targetSession = sid || sessionId;
    if (!targetSession) return;
    try {
      const res = await apiClient.get<CartData>(`/cart?session_id=${targetSession}`);
      setCart(res.data);
    } catch (err: unknown) {
      console.error('Error fetching cart', err);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId) {
      fetchCart(sessionId);
    }
  }, [sessionId, fetchCart]);

  // 4. Recalculate Pricing Breakdown
  const recalculatePricing = useCallback(async () => {
    if (!sessionId || cart.items.length === 0) {
      setPricingBreakdown(null);
      return;
    }
    try {
      const res = await apiClient.post<CartPricingBreakdown>(`/rewards/calculate-pricing?session_id=${sessionId}`, {
        coupon_code: appliedCoupon,
        voucher_code: appliedVoucher,
        use_coins: useCoins,
      });
      setPricingBreakdown(res.data);
    } catch (err: unknown) {
      console.error('Error recalculating pricing breakdown', err);
    }
  }, [sessionId, cart.items.length, appliedCoupon, appliedVoucher, useCoins]);

  useEffect(() => {
    recalculatePricing();
  }, [recalculatePricing]);

  // 5. Filter & Sort Catalog Products
  useEffect(() => {
    let list = [...catalogProducts];

    // Check if an authoritative AI structured search intent is active
    if (activeStructuredIntent) {
      if (activeStructuredIntent.clarification_needed) {
        if (selectedCategory !== 'All') {
          list = list.filter((p) => p.category?.toLowerCase() === selectedCategory.toLowerCase());
        }
      } else {
        // 1. Structured Category Filtering
        if (activeStructuredIntent.category) {
          const targetCat = activeStructuredIntent.category.toLowerCase();
          list = list.filter((p) => {
            const pCat = (p.category || '').toLowerCase();
            const pSub = (p.subcategory || '').toLowerCase();
            const pName = (p.name || '').toLowerCase();
            if (targetCat === 'running' || targetCat === 'footwear') {
              return pCat.includes('footwear') || pSub.includes('running') || pName.includes('shoe') || pName.includes('running');
            }
            return pCat.includes(targetCat) || pSub.includes(targetCat) || pName.includes(targetCat);
          });
        } else if (selectedCategory !== 'All') {
          list = list.filter((p) => p.category?.toLowerCase() === selectedCategory.toLowerCase());
        }

        // 2. Structured Max Budget Filtering
        if (activeStructuredIntent.max_price !== undefined && activeStructuredIntent.max_price !== null) {
          const maxP = Number(activeStructuredIntent.max_price);
          list = list.filter((p) => p.price <= maxP);
        }

        // 3. Structured Min Budget Filtering
        if (activeStructuredIntent.min_price !== undefined && activeStructuredIntent.min_price !== null) {
          const minP = Number(activeStructuredIntent.min_price);
          list = list.filter((p) => p.price >= minP);
        }

        // 4. In Stock Only
        if (activeStructuredIntent.in_stock_only || inStockOnly) {
          list = list.filter((p) => (p.stock_quantity ?? 0) > 0);
        }
      }
    } else {
      // Standard UI Category Filter
      if (selectedCategory !== 'All') {
        list = list.filter((p) => {
          const pCat = (p.category || '').toLowerCase();
          const target = selectedCategory.toLowerCase();
          if (target === 'running' || target === 'footwear') {
            return pCat.includes('footwear') || pCat.includes('running') || (p.subcategory || '').toLowerCase().includes('running');
          }
          return pCat.includes(target);
        });
      }

      // Brand Filter
      if (selectedBrand !== 'All Brands') {
        list = list.filter((p) => (p.brand || '').toLowerCase() === selectedBrand.toLowerCase());
      }

      // Price Range Filter
      if (selectedPriceRange === 'under-999') {
        list = list.filter((p) => p.price <= 999);
      } else if (selectedPriceRange === 'under-2999') {
        list = list.filter((p) => p.price <= 2999);
      } else if (selectedPriceRange === 'under-5000') {
        list = list.filter((p) => p.price <= 5000);
      } else if (selectedPriceRange === 'above-5000') {
        list = list.filter((p) => p.price > 5000);
      }

      // Standard Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        list = list.filter((p) => {
          const nameMatch = (p.name || '').toLowerCase().includes(q);
          const brandMatch = (p.brand || '').toLowerCase().includes(q);
          const catMatch = (p.category || '').toLowerCase().includes(q);
          const subcatMatch = (p.subcategory || '').toLowerCase().includes(q);
          const descMatch = (p.description || '').toLowerCase().includes(q);
          return nameMatch || brandMatch || catMatch || subcatMatch || descMatch;
        });
      }

      // In Stock Only
      if (inStockOnly) {
        list = list.filter((p) => (p.stock_quantity ?? 0) > 0);
      }
    }

    // Sorting
    switch (sortBy) {
      case 'price-low':
        list.sort((a, b) => a.price - b.price);
        break;
      case 'price-high':
        list.sort((a, b) => b.price - a.price);
        break;
      case 'stock':
        list.sort((a, b) => (b.stock_quantity ?? 0) - (a.stock_quantity ?? 0));
        break;
      case 'featured':
      default:
        break;
    }

    setFilteredProducts(list);
  }, [catalogProducts, selectedCategory, selectedBrand, selectedPriceRange, searchQuery, inStockOnly, sortBy, activeStructuredIntent]);

  // 6. Cart Mutations
  const handleAddToCart = async (product: Product) => {
    if (!sessionId) return;
    setAddingProductId(product.id);
    try {
      const res = await apiClient.post('/cart/items', {
        product_id: product.id,
        quantity: 1,
        session_id: sessionId,
      });
      setCart(res.data);
      showToast(`Added "${product.name}" to cart.`, 'success');
      setIsCartOpen(true);
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Failed to add item to cart.'), 'error');
    } finally {
      setAddingProductId(null);
    }
  };

  const handleUpdateQuantity = async (productId: string, newQuantity: number) => {
    if (!sessionId) return;
    setUpdatingCartItemId(productId);
    try {
      if (newQuantity <= 0) {
        const res = await apiClient.delete(`/cart/items/${productId}?session_id=${sessionId}`);
        setCart(res.data);
      } else {
        const res = await apiClient.patch(`/cart/items/${productId}?session_id=${sessionId}`, {
          quantity: newQuantity,
          session_id: sessionId,
        });
        setCart(res.data);
      }
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Could not update item quantity.'), 'error');
    } finally {
      setUpdatingCartItemId(null);
    }
  };

  const handleRemoveItem = async (productId: string) => {
    if (!sessionId) return;
    setUpdatingCartItemId(productId);
    try {
      const res = await apiClient.delete(`/cart/items/${productId}?session_id=${sessionId}`);
      setCart(res.data);
      showToast('Item removed from cart.', 'info');
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Failed to remove item.'), 'error');
    } finally {
      setUpdatingCartItemId(null);
    }
  };

  const handleClearCart = async () => {
    if (!sessionId) return;
    try {
      await apiClient.delete(`/cart?session_id=${sessionId}`);
      setCart({ items: [], total_amount: 0, currency: 'INR' });
      setAppliedCoupon(null);
      setAppliedVoucher(null);
      setPricingBreakdown(null);
      showToast('Cart cleared.', 'info');
    } catch (err: unknown) {
      showToast(extractErrorMessage(err, 'Failed to clear cart.'), 'error');
    }
  };

  // 7. Voice Shopping Transcript Handler
  const handleVoiceTranscript = (transcriptText: string) => {
    setSearchQuery(transcriptText);
    // Also feed into AI Shopping Assistant if it asks questions or has preferences
    handleSendAIMessage(transcriptText);
    setIsAIOpen(true);
    showToast(`Voice Search: "${transcriptText}"`, 'info');
  };

  // 8. AI Shopping Assistant Interaction
  const handleSendAIMessage = async (userText: string) => {
    if (!userText.trim() || aiLoading) return;

    const userMsg: AIMessage = {
      role: 'user',
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setAiMessages((prev) => [...prev, userMsg]);
    setAiLoading(true);

    try {
      const res = await apiClient.post('/ai/shopping', {
        message: userText,
        session_id: sessionId,
        delivery_address: deliveryAddress,
        applied_coupon: appliedCoupon,
        applied_voucher: appliedVoucher,
        use_coins: useCoins,
      });

      const data = res.data;

      // Update cart state if mutated by agent
      if (data.cart && data.cart.items) {
        setCart(data.cart);
      }

      // Extract discovered products from ShoppingAgent
      const discoveredItems: Product[] = (data.products || []).map((p: {
        id?: string;
        product_id?: string;
        name?: string;
        product_name?: string;
        price?: number | string;
        product_price?: number | string;
        category?: string;
        image_url?: string;
        description?: string;
        reason?: string;
      }) => ({
        id: p.id || p.product_id || '',
        name: p.name || p.product_name || 'Athletic Product',
        price: Number(p.price ?? p.product_price ?? 0),
        category: p.category || 'Gear',
        image_url: p.image_url,
        description: p.description || p.reason,
      }));

      // Extract cross-sell suggestions from SalesAgent
      const recItems: Product[] = (data.recommendations || []).map((r: {
        id?: string;
        recommended_product_id?: string;
        product_id?: string;
        name?: string;
        product_name?: string;
        price?: number | string;
        product_price?: number | string;
        category?: string;
        image_url?: string;
        reason?: string;
        description?: string;
      }) => ({
        id: r.recommended_product_id || r.product_id || r.id || '',
        name: r.product_name || r.name || 'Recommended Gear',
        price: Number(r.product_price ?? r.price ?? 0),
        category: r.category || 'Accessories',
        image_url: r.image_url,
        description: r.reason || r.description,
      }));

      // Deduplicate recommendations by product id
      const seenIds = new Set<string>();
      const combinedRecommendations: Product[] = [];
      for (const item of [...discoveredItems, ...recItems]) {
        if (item.id && !seenIds.has(item.id)) {
          seenIds.add(item.id);
          combinedRecommendations.push(item);
        }
      }

      if (data.structured_intent) {
        setActiveStructuredIntent(data.structured_intent);
      }

      if (data.actions && data.actions.includes('OPEN_VIRTUAL_TRYON') && discoveredItems.length > 0) {
        setVtoProduct(discoveredItems[0]);
      }

      const assistantMsg: AIMessage = {
        role: 'assistant',
        content: data.message || data.reply || 'Here are verified options tailored to your request:',
        recommendations: combinedRecommendations,
        order_review: data.order_review,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setAiMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      console.error('AI Assistant Error:', err);
      const safeMsg = extractErrorMessage(
        err,
        'I encountered an issue connecting to the catalog intelligence service. Please try again.'
      );
      const assistantMsg: AIMessage = {
        role: 'assistant',
        content: safeMsg,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setAiMessages((prev) => [...prev, assistantMsg]);
    } finally {
      setAiLoading(false);
    }
  };

  // 9. Checkout & Real Razorpay Flow
  const handleStartCheckout = async () => {
    if (cart.items.length === 0) {
      showToast('Your cart is empty.', 'error');
      return;
    }

    setIsCartOpen(false);
    setIsCheckoutOpen(true);
    setCheckoutStep('address');
    setCheckoutError(null);
    setReceipt(null);
    setApprovalDetails(null);
  };

  const handleStartPayment = async (forceApprove: boolean = false) => {
    try {
      setCheckoutStep('processing');
      setCheckoutError(null);

      // Verify Razorpay Configuration
      if (paymentConfig && !paymentConfig.configured) {
        setCheckoutStep('failed');
        setCheckoutError(
          'Online payment is currently unavailable because Razorpay has not been configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to backend/.env.'
        );
        return;
      }

      // Step 1: Create Purchase Intent with Delivery Address Snapshot & Discounts
      const intentRes = await apiClient.post('/purchase-intents/', {
        session_id: sessionId,
        buyer_id: userProfile?.email || deliveryAddress.email || 'guest_shopper',
        delivery_address: deliveryAddress,
        coupon_code: appliedCoupon,
        voucher_code: appliedVoucher,
        use_coins: useCoins,
      });
      const intentData = intentRes.data;

      // Step 2: Evaluate Intent & Generate Authorization
      const evalRes = await apiClient.post(`/purchase-intents/${intentData.id}/evaluate`);
      const authData = evalRes.data;

      let authorizationId = authData.authorization?.id || authData.authorization_id;

      // Handle Autonomous Threshold Exceeded -> Transition to APPROVAL_REQUIRED (NOT Payment Failed!)
      if (authData.decision === 'REQUIRES_APPROVAL') {
        if (!forceApprove) {
          setApprovalDetails({
            approvalId: authData.approval_request?.id,
            amount: Number(intentData.requested_amount || cart.total_amount),
            threshold: 5000,
            reason: authData.approval_request?.reason,
          });
          setCheckoutStep('approval_required');
          return;
        } else if (authData.approval_request?.id) {
          // Explicit User Approval granted -> approve request and retrieve authorization ID
          const approveRes = await apiClient.post(`/approvals/${authData.approval_request.id}/approve`, {
            reason: 'Explicitly authorized by customer at checkout',
          });
          authorizationId = approveRes.data.authorization?.id;
        }
      }

      const isApproved = authData.decision === 'ALLOW' || authData.approved === true || forceApprove;

      if (!isApproved || !authorizationId) {
        setCheckoutStep('policy_blocked');
        const violations = authData.violations || authData.policy_violations || [];
        const approvalReason = authData.approval_request?.reason;
        const failureMessage =
          (Array.isArray(violations) && violations.length > 0 ? violations.join('. ') : null) ||
          approvalReason ||
          authData.decision_reason ||
          'Purchase intent blocked by deterministic policy evaluation.';

        setCheckoutError(failureMessage);
        return;
      }

      // Step 3: Create Razorpay Order with authoritative amount
      const orderRes = await apiClient.post('/payments/create-order', {
        purchase_intent_id: intentData.id,
        authorization_id: authorizationId,
        idempotency_key: `idem_${intentData.id.slice(0, 8)}_${Date.now()}`,
      });
      const orderPayload = orderRes.data;

      if (!orderPayload.razorpay_order_id) {
        setCheckoutStep('failed');
        setCheckoutError(
          orderPayload.status === 'FAILED'
            ? 'Payment order creation failed on payment provider. Please verify credentials or try again.'
            : 'Could not generate Razorpay order ID.'
        );
        return;
      }

      // Step 4: Load Official Razorpay Checkout Script
      const scriptLoaded = await loadRazorpayScript();
      if (!scriptLoaded) {
        setCheckoutStep('failed');
        setCheckoutError('Failed to load secure Razorpay checkout script.');
        return;
      }

      // Step 5: Open Real Razorpay Modal
      const keyId =
        orderPayload.razorpay_key_id ||
        orderPayload.key_id ||
        paymentConfig?.key_id ||
        process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;

      if (!keyId) {
        setCheckoutStep('failed');
        setCheckoutError('Razorpay Public Key ID is not configured on the backend or in NEXT_PUBLIC_RAZORPAY_KEY_ID.');
        return;
      }

      const options: RazorpayCheckoutOptions = {
        key: keyId,
        amount: Math.round(Number(orderPayload.amount) * 100),
        currency: orderPayload.currency || 'INR',
        name: 'Apex Sports Store',
        description: `Order for ${cart.items.length} item(s)`,
        order_id: orderPayload.razorpay_order_id,
        prefill: {
          name: deliveryAddress.full_name,
          email: deliveryAddress.email,
          contact: deliveryAddress.phone,
        },
        notes: {
          purchase_intent_id: intentData.id,
          session_id: sessionId,
        },
        theme: {
          color: '#0f172a',
        },
        handler: async (response) => {
          setCheckoutStep('verifying');
          try {
            // Step 6: Verify Cryptographic Signature on Backend
            const verifyRes = await apiClient.post('/payments/verify-signature', {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            });

            setReceipt({
              payment_id: response.razorpay_payment_id,
              order_id: response.razorpay_order_id,
              amount: Number(verifyRes.data.amount || pricingBreakdown?.total || cart.total_amount),
              currency: verifyRes.data.currency || 'INR',
              status: verifyRes.data.status || 'CAPTURED',
              signature_verified: true,
              delivery_address: deliveryAddress,
              created_at: new Date().toLocaleDateString('en-IN', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              }),
            });
            setCheckoutStep('success');
            // Clear cart upon verified purchase
            setCart({ items: [], total_amount: 0, currency: 'INR' });
            setAppliedCoupon(null);
            setAppliedVoucher(null);
            setPricingBreakdown(null);
          } catch (verifyErr: unknown) {
            console.error('[CHECKOUT] Signature verification error:', verifyErr);
            const safeVerifyError = extractErrorMessage(
              verifyErr,
              'Payment signature verification failed.'
            );
            setCheckoutStep('failed');
            setCheckoutError(safeVerifyError);
          }
        },
        modal: {
          ondismiss: () => {
            setCheckoutStep((prev) => (prev === 'success' ? 'success' : 'review'));
          },
        },
      };

      if (typeof window !== 'undefined' && window.Razorpay) {
        const rzp = new window.Razorpay(options);
        rzp.on('payment.failed', (response: { error: { description?: string; reason?: string } }) => {
          setCheckoutStep('failed');
          setCheckoutError(
            response?.error?.description ||
            response?.error?.reason ||
            'Payment failed or was cancelled on Razorpay gateway.'
          );
        });
        rzp.open();
      } else {
        setCheckoutStep('failed');
        setCheckoutError('Razorpay SDK is not available in current window.');
      }
    } catch (err: unknown) {
      console.error('[CHECKOUT] Checkout error:', err);
      const safeError = extractErrorMessage(err, 'Could not initialize payment with server.');
      setCheckoutStep('failed');
      setCheckoutError(safeError);
    }
  };

  const handleSignOut = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_profile');
    setUserProfile(null);
    showToast('Signed out successfully.', 'info');
  };

  const categories = [
    'All',
    'Sports & Fitness',
    'Footwear',
    'Electronics',
    'Fashion',
    'Home & Kitchen',
    'Beauty & Personal Care',
    'Travel',
    'Accessories',
  ];

  const brandList = [
    'All Brands',
    'Nike',
    'Adidas',
    'Puma',
    'Decathlon',
    'Sony',
    'Apple',
    'boAt',
    'Noise',
    'Milton',
    'Philips',
    "Levi's",
    'American Tourister',
  ];

  const priceRanges = [
    { label: 'All Prices', id: 'all' },
    { label: 'Under ₹999', id: 'under-999' },
    { label: 'Under ₹2,999', id: 'under-2999' },
    { label: 'Under ₹5,000', id: 'under-5000' },
    { label: 'Above ₹5,000', id: 'above-5000' },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      {/* Toast Notification */}
      {toast && <Toast {...toast} />}

      {/* Global Storefront Header */}
      <StorefrontHeader
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        cartItemCount={cart.items.reduce((s, i) => s + i.quantity, 0)}
        onOpenCart={() => setIsCartOpen(true)}
        onOpenAI={() => setIsAIOpen(true)}
        onOpenVoiceSearch={() => setIsVoiceModalOpen(true)}
        onOpenVisualSearch={() => setIsVisualModalOpen(true)}
        userProfile={userProfile}
        onOpenAuth={() => setIsAuthOpen(true)}
        onSignOut={handleSignOut}
      />

      {/* Category Tabs Bar */}
      <CategoryTabs
        categories={categories}
        selectedCategory={selectedCategory}
        onSelectCategory={setSelectedCategory}
      />

      {/* Storefront Main Body */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-6">
        {/* Marketplace Brand & Quick Price Filter Toolbar */}
        <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3 shadow-2xs">
          {/* Brand Filter Row */}
          <div className="flex items-center gap-2 overflow-x-auto scrollbar-none pb-1">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider shrink-0 mr-1">
              Brands:
            </span>
            {brandList.map((brand) => (
              <button
                key={brand}
                onClick={() => setSelectedBrand(brand)}
                className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                  selectedBrand === brand
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {brand}
              </button>
            ))}
          </div>

          {/* Price Range Filter Row */}
          <div className="flex items-center gap-2 overflow-x-auto scrollbar-none pt-1 border-t border-slate-100">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider shrink-0 mr-1">
              Budget:
            </span>
            {priceRanges.map((range) => (
              <button
                key={range.id}
                onClick={() => setSelectedPriceRange(range.id)}
                className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                  selectedPriceRange === range.id
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {range.label}
              </button>
            ))}
          </div>
        </div>

        {/* Subtle AI Assistant Banner */}
        <div className="rounded-2xl bg-white border border-slate-200 p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xs">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0">
              <SparklesIcon size={20} />
            </div>
            <div>
              <h2 className="font-bold text-sm sm:text-base text-slate-900 leading-tight">
                Looking for running shoes, earbuds, or gym gear?
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Our AI Shopping Assistant finds verified gear and checks external prices across Amazon, Flipkart, and Official Stores.
              </p>
            </div>
          </div>

          <Button
            onClick={() => {
              setIsAIOpen(true);
              handleSendAIMessage('Show me running shoes under ₹5,000');
            }}
            variant="accent"
            size="sm"
            className="font-semibold shrink-0"
            leftIcon={<SparklesIcon size={14} />}
          >
            Ask AI Assistant
          </Button>
        </div>

        {/* Active AI Search Filter Criteria Bar */}
        {activeStructuredIntent && (
          <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 bg-indigo-50/70 border border-indigo-200/80 rounded-2xl text-xs text-indigo-950 shadow-2xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold flex items-center gap-1.5 text-indigo-900">
                <SparklesIcon size={14} className="text-indigo-600" />
                Active AI Search:
              </span>
              {activeStructuredIntent.clarification_needed ? (
                <span className="px-2.5 py-1 rounded-lg bg-amber-100 text-amber-900 border border-amber-300 font-semibold flex items-center gap-1">
                  <span>⚠️</span> Budget clarification needed
                </span>
              ) : (
                <>
                  {activeStructuredIntent.category && (
                    <span className="px-2.5 py-1 rounded-lg bg-white border border-indigo-200 text-slate-800 font-medium shadow-2xs">
                      Category: <strong>{activeStructuredIntent.category}</strong>
                    </span>
                  )}
                  {activeStructuredIntent.max_price !== undefined && activeStructuredIntent.max_price !== null && (
                    <span className="px-2.5 py-1 rounded-lg bg-white border border-indigo-200 text-slate-800 font-medium shadow-2xs">
                      Budget: <strong>Up to ₹{Number(activeStructuredIntent.max_price).toLocaleString()}</strong>
                    </span>
                  )}
                </>
              )}
            </div>

            <button
              onClick={() => {
                setActiveStructuredIntent(null);
                setSearchQuery('');
                setSelectedCategory('All');
                setSelectedBrand('All Brands');
                setSelectedPriceRange('all');
              }}
              className="text-xs text-indigo-700 hover:text-indigo-900 font-semibold hover:underline cursor-pointer"
            >
              ✕ Clear AI filter
            </button>
          </div>
        )}

        {/* Product Grid Component */}
        <ProductGrid
          products={filteredProducts}
          isLoading={catalogLoading}
          apiError={catalogError}
          onRetry={fetchCatalog}
          onAddToCart={handleAddToCart}
          onOpenPriceCheck={(p) => setComparisonProductId(p.id)}
          addingProductId={addingProductId}
          onResetFilters={() => {
            setSelectedCategory('All');
            setSelectedBrand('All Brands');
            setSelectedPriceRange('all');
            setSearchQuery('');
            setInStockOnly(false);
            setActiveStructuredIntent(null);
          }}
          sortBy={sortBy}
          onSortChange={setSortBy}
          inStockOnly={inStockOnly}
          onToggleInStock={setInStockOnly}
          totalCount={catalogProducts.length}
        />
      </main>

      {/* Fixed Bottom-Right AI Trigger Button */}
      <div className="fixed bottom-6 right-6 z-40">
        <button
          onClick={() => setIsAIOpen(true)}
          className="flex items-center gap-2.5 px-4 py-3 rounded-full bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-lg hover:shadow-xl transition-all duration-200 border border-slate-700 select-none group active:scale-95 cursor-pointer"
          aria-label="Open AI Shopping Assistant"
        >
          <SparklesIcon size={15} className="text-indigo-400 group-hover:scale-110 transition-transform" />
          <span>AI Shopping Assistant</span>
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        </button>
      </div>

      <AIShoppingDrawer
        isOpen={isAIOpen}
        onClose={() => setIsAIOpen(false)}
        messages={aiMessages}
        onSendMessage={handleSendAIMessage}
        isLoading={aiLoading}
        onAddToCart={handleAddToCart}
        addingProductId={addingProductId}
        onOpenVoiceSearch={() => setIsVoiceModalOpen(true)}
        onConfirmOrderReview={() => {
          setIsAIOpen(false);
          setIsCheckoutOpen(true);
          setCheckoutStep('review');
        }}
        onApproveAndPayOrderReview={() => {
          setIsAIOpen(false);
          setIsCheckoutOpen(true);
          handleStartPayment(true);
        }}
      />

      <CartDrawer
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        cart={cart}
        onUpdateQuantity={handleUpdateQuantity}
        onRemoveItem={handleRemoveItem}
        onClearCart={handleClearCart}
        onCheckout={handleStartCheckout}
        updatingCartItemId={updatingCartItemId}
        catalogProducts={catalogProducts}
        appliedCoupon={appliedCoupon}
        onApplyCoupon={setAppliedCoupon}
        appliedVoucher={appliedVoucher}
        onApplyVoucher={setAppliedVoucher}
        useCoins={useCoins}
        onToggleCoins={setUseCoins}
        pricingBreakdown={pricingBreakdown}
      />

      <PriceComparisonModal
        isOpen={!!comparisonProductId}
        onClose={() => setComparisonProductId(null)}
        productId={comparisonProductId}
        onBuyOnApex={(pId) => {
          const p = catalogProducts.find((i) => i.id === pId);
          if (p) handleAddToCart(p);
        }}
      />

      <CheckoutModal
        isOpen={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        cart={cart}
        catalogProducts={catalogProducts}
        checkoutStep={checkoutStep}
        setCheckoutStep={setCheckoutStep}
        deliveryAddress={deliveryAddress}
        setDeliveryAddress={setDeliveryAddress}
        onStartPayment={handleStartPayment}
        paymentConfig={paymentConfig}
        receipt={receipt}
        errorMessage={checkoutError}
        pricingBreakdown={pricingBreakdown}
        onReset={() => setCheckoutStep('address')}
        approvalDetails={approvalDetails}
      />

      <VoiceSearchModal
        isOpen={isVoiceModalOpen}
        onClose={() => setIsVoiceModalOpen(false)}
        onTranscript={handleVoiceTranscript}
      />

      <VisualSearchModal
        isOpen={isVisualModalOpen}
        onClose={() => setIsVisualModalOpen(false)}
        onAddToCart={(prodId) => {
          const p = catalogProducts.find((i) => i.id === prodId);
          if (p) handleAddToCart(p);
        }}
      />

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        authConfig={authConfig}
        onSuccess={(user) => {
          setUserProfile(user);
          showToast(`Welcome back, ${user.full_name || user.email}!`, 'success');
        }}
      />

      {/* VirtualTryOnModal */}
      {vtoProduct && (
        <VirtualTryOnModal
          isOpen={Boolean(vtoProduct)}
          onClose={() => setVtoProduct(null)}
          product={{
            id: vtoProduct.id,
            name: vtoProduct.name,
            brand: vtoProduct.brand,
            category: vtoProduct.category,
            price: vtoProduct.price,
            image_url: vtoProduct.image_url,
          }}
          sessionId={sessionId}
          onAddToCart={(pid) => {
            const p = catalogProducts.find((i) => i.id === pid) || vtoProduct;
            if (p) handleAddToCart(p);
            setVtoProduct(null);
          }}
          onBuyNow={(pid) => {
            const p = catalogProducts.find((i) => i.id === pid) || vtoProduct;
            if (p) handleAddToCart(p);
            setVtoProduct(null);
            handleStartCheckout();
          }}
          onComparePrices={(pid) => {
            setVtoProduct(null);
            setComparisonProductId(pid);
          }}
          onSelectProductToTry={(targetId) => {
            const nextProd = catalogProducts.find((i) => i.id === targetId);
            if (nextProd) setVtoProduct(nextProd);
          }}
        />
      )}

      {/* Clean Light Theme Footer */}
      <footer className="border-t border-slate-200 bg-white text-slate-500 text-xs py-8 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-900">Apex Sports</span>
            <span>— Governed AI Commerce OS</span>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <span>Prices and inventory verified by server</span>
            {userProfile?.role === 'merchant_admin' && (
              <a href="/dashboard" className="text-indigo-600 hover:text-indigo-800 font-semibold">
                Merchant Console →
              </a>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}
