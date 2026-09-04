'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  SparklesIcon,
  XIcon,
  PlusIcon,
  ShoppingBagIcon,
  MicIcon,
  CreditCardIcon,
  AlertTriangleIcon,
  ShieldCheckIcon,
  MapPinIcon,
} from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Product } from './ProductCard';
import { ProductImage } from '@/components/ui/ProductImage';

export interface OrderReviewData {
  items: Array<{
    product_id: string;
    name: string;
    quantity: number;
    price: number;
    subtotal: number;
    category?: string;
    image_url?: string;
  }>;
  subtotal: number;
  coupon_code?: string;
  coupon_discount?: number;
  voucher_code?: string;
  voucher_discount?: number;
  coins_used?: number;
  coin_discount?: number;
  shipping: number;
  total: number;
  currency: string;
  delivery_address?: {
    full_name?: string;
    phone?: string;
    address_line1?: string;
    city?: string;
    state?: string;
    pin_code?: string;
  };
  delivery_address_required?: boolean;
  autonomous_threshold: number;
  is_above_threshold: boolean;
  potential_points?: number;
}

export interface AIMessage {
  role: 'assistant' | 'user';
  content: string;
  recommendations?: Product[];
  order_review?: OrderReviewData;
  timestamp?: string;
  confidence?: number;
}

export interface AIShoppingDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  messages: AIMessage[];
  onSendMessage: (query: string) => void;
  isLoading: boolean;
  onAddToCart: (product: Product) => void;
  addingProductId: string | null;
  onOpenVoiceSearch?: () => void;
  onConfirmOrderReview?: (review: OrderReviewData) => void;
  onApproveAndPayOrderReview?: (review: OrderReviewData) => void;
}

const PROMPT_SUGGESTIONS = [
  '5k ke andar running shoes chahiye',
  'black wala',
  'Nike wala',
  'best price check karo',
  'ye wala le lo',
  '2 pairs',
  'use SAVE500',
  'checkout'
];

export function AIShoppingDrawer({
  isOpen,
  onClose,
  messages,
  onSendMessage,
  isLoading,
  onAddToCart,
  addingProductId,
  onOpenVoiceSearch,
  onConfirmOrderReview,
  onApproveAndPayOrderReview,
}: AIShoppingDrawerProps) {
  const [inputVal, setInputVal] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim() || isLoading) return;
    onSendMessage(inputVal.trim());
    setInputVal('');
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Drawer Panel */}
      <div className="relative w-full max-w-md bg-white border-l border-slate-200 h-full shadow-2xl flex flex-col justify-between z-10 animate-in slide-in-from-right duration-250 text-slate-900">
        {/* Header */}
        <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-white">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-indigo-50 border border-indigo-200/60 flex items-center justify-center text-indigo-600">
              <SparklesIcon size={16} />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-900 leading-none">
                AI Shopping Assistant
              </h3>
              <p className="text-[11px] text-slate-500 font-normal mt-0.5">
                Autonomous Commerce Concierge
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            aria-label="Close Assistant"
          >
            <XIcon size={16} />
          </button>
        </div>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs bg-slate-50/50">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} space-y-2`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'bg-white text-slate-800 border border-slate-200 shadow-xs'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.timestamp && (
                  <span
                    className={`block text-[10px] mt-1.5 ${
                      msg.role === 'user' ? 'text-slate-400' : 'text-slate-400'
                    }`}
                  >
                    {msg.timestamp}
                  </span>
                )}
              </div>

              {/* Embedded Recommendation Product Cards */}
              {msg.recommendations && msg.recommendations.length > 0 && (
                <div className="w-full space-y-2.5 pt-1">
                  <div className="text-[11px] font-semibold text-slate-500 flex items-center gap-1">
                    <ShoppingBagIcon size={12} className="text-indigo-600" />
                    <span>Verified Catalog Options:</span>
                  </div>

                  <div className="space-y-2.5">
                    {msg.recommendations.map((rec) => {
                      const safePrice = Number(rec.price || 0);

                      return (
                        <div
                          key={rec.id}
                          className="bg-white border border-slate-200 rounded-xl p-3 space-y-2 shadow-xs hover:border-slate-300 transition-all"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-3 min-w-0">
                              <ProductImage
                                src={rec.image_url}
                                alt={rec.name}
                                productId={rec.id}
                                productName={rec.name}
                                category={rec.category}
                                className="w-12 h-12 rounded-lg object-cover bg-slate-100 shrink-0 border border-slate-100"
                                containerClassName="w-12 h-12 rounded-lg shrink-0"
                              />
                              <div className="min-w-0">
                                <h4 className="font-semibold text-xs text-slate-900 truncate">
                                  {rec.name}
                                </h4>
                                {rec.brand && (
                                  <span className="text-[10px] text-indigo-600 font-semibold block">
                                    {rec.brand}
                                  </span>
                                )}
                                <div className="flex items-center gap-2 mt-0.5">
                                  <span className="font-bold text-slate-900 text-xs font-mono">
                                    ₹{safePrice.toLocaleString('en-IN')}
                                  </span>
                                  {rec.category && (
                                    <Badge variant="neutral" size="xs">
                                      {rec.category}
                                    </Badge>
                                  )}
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-1.5 shrink-0">
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => onSendMessage(`price compare ${rec.name}`)}
                                className="h-7 px-2 text-[10px]"
                              >
                                Price Check
                              </Button>
                              <Button
                                size="sm"
                                variant="primary"
                                onClick={() => onAddToCart(rec)}
                                disabled={addingProductId === rec.id}
                                className="h-7 px-2 text-[10px]"
                                leftIcon={<PlusIcon size={11} />}
                              >
                                {addingProductId === rec.id ? 'Adding...' : 'Add'}
                              </Button>
                            </div>
                          </div>

                          {/* "Why this?" Transparency Rationale */}
                          {rec.why_this_rationale && rec.why_this_rationale.length > 0 && (
                            <div className="mt-1.5 p-2 rounded-lg bg-slate-50 border border-slate-100 text-[10px] text-slate-600 space-y-0.5">
                              <span className="font-semibold text-slate-800 block text-[10px]">
                                Why this recommendation:
                              </span>
                              {rec.why_this_rationale.map((bullet, bIdx) => (
                                <p key={bIdx} className="leading-tight">
                                  {bullet}
                                </p>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Structured Order Review & Governance Action Card */}
              {msg.order_review && (
                <div className="w-full mt-2 rounded-2xl border border-indigo-200 bg-white shadow-md p-4 space-y-3.5 text-xs text-slate-900">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <div className="flex items-center gap-1.5 font-bold text-slate-900">
                      {msg.order_review.is_above_threshold ? (
                        <AlertTriangleIcon size={16} className="text-amber-600" />
                      ) : (
                        <ShieldCheckIcon size={16} className="text-indigo-600" />
                      )}
                      <span>
                        {msg.order_review.is_above_threshold
                          ? 'APPROVAL REQUIRED'
                          : 'READY TO ORDER'}
                      </span>
                    </div>
                    {msg.order_review.is_above_threshold ? (
                      <Badge variant="warning" size="xs">
                        HIGH VALUE &gt; ₹5,000
                      </Badge>
                    ) : (
                      <Badge variant="success" size="xs">
                        POLICY VERIFIED
                      </Badge>
                    )}
                  </div>

                  {/* Items List */}
                  <div className="space-y-2">
                    {msg.order_review.items.map((it, i) => (
                      <div
                        key={i}
                        className="flex justify-between items-center py-1 border-b border-slate-50 last:border-0"
                      >
                        <div className="min-w-0 pr-2">
                          <span className="font-semibold text-slate-900 truncate block">
                            {it.name}
                          </span>
                          <span className="text-slate-500 text-[11px]">
                            Qty: {it.quantity} × ₹{Number(it.price).toLocaleString('en-IN')}
                          </span>
                        </div>
                        <span className="font-bold text-slate-900 font-mono shrink-0">
                          ₹{Number(it.subtotal).toLocaleString('en-IN')}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Pricing Breakdown */}
                  <div className="pt-2 border-t border-slate-100 space-y-1 text-[11px] text-slate-600">
                    <div className="flex justify-between">
                      <span>Subtotal</span>
                      <span className="font-medium text-slate-900 font-mono">
                        ₹{Number(msg.order_review.subtotal).toLocaleString('en-IN')}
                      </span>
                    </div>
                    {(msg.order_review.coupon_discount ?? 0) > 0 && (
                      <div className="flex justify-between text-emerald-700 font-medium">
                        <span>Coupon ({msg.order_review.coupon_code})</span>
                        <span className="font-mono">
                          -₹{Number(msg.order_review.coupon_discount).toLocaleString('en-IN')}
                        </span>
                      </div>
                    )}
                    {(msg.order_review.coin_discount ?? 0) > 0 && (
                      <div className="flex justify-between text-indigo-700 font-medium">
                        <span>Apex Coins ({msg.order_review.coins_used} used)</span>
                        <span className="font-mono">
                          -₹{Number(msg.order_review.coin_discount).toLocaleString('en-IN')}
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span>Delivery</span>
                      <span className="font-semibold text-emerald-600">FREE</span>
                    </div>
                    <div className="pt-2 border-t border-slate-200 flex justify-between items-center text-sm font-extrabold text-slate-900">
                      <span>Total Payable</span>
                      <span className="font-mono text-indigo-700">
                        ₹{Number(msg.order_review.total).toLocaleString('en-IN')}
                      </span>
                    </div>
                  </div>

                  {/* Delivery Address Snapshot */}
                  {msg.order_review.delivery_address && (
                    <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-[11px] text-slate-700 space-y-0.5">
                      <div className="flex items-center gap-1 font-semibold text-slate-900">
                        <MapPinIcon size={12} className="text-slate-500" />
                        <span>Delivery:</span>
                      </div>
                      <p className="truncate font-medium">
                        {msg.order_review.delivery_address.full_name} •{' '}
                        {msg.order_review.delivery_address.city},{' '}
                        {msg.order_review.delivery_address.state} -{' '}
                        {msg.order_review.delivery_address.pin_code}
                      </p>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="pt-2 space-y-2">
                    {msg.order_review.is_above_threshold ? (
                      <Button
                        onClick={() =>
                          onApproveAndPayOrderReview?.(msg.order_review!)
                        }
                        variant="primary"
                        size="md"
                        className="w-full font-bold shadow-md hover:shadow-lg"
                        leftIcon={<CreditCardIcon size={14} />}
                      >
                        Approve ₹{Number(msg.order_review.total).toLocaleString('en-IN')} &amp; Pay →
                      </Button>
                    ) : (
                      <Button
                        onClick={() =>
                          onConfirmOrderReview?.(msg.order_review!)
                        }
                        variant="primary"
                        size="md"
                        className="w-full font-bold shadow-md hover:shadow-lg"
                        leftIcon={<CreditCardIcon size={14} />}
                      >
                        Confirm &amp; Pay (₹{Number(msg.order_review.total).toLocaleString('en-IN')}) →
                      </Button>
                    )}

                    <Button
                      type="button"
                      onClick={() => onSendMessage('Change order')}
                      variant="secondary"
                      size="sm"
                      className="w-full text-xs"
                    >
                      Change Order
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex items-start gap-2 max-w-[85%] bg-white rounded-2xl px-4 py-3 border border-slate-200 shadow-xs">
              <div className="flex gap-1 items-center h-4">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce" />
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.2s]" />
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.4s]" />
              </div>
              <span className="text-[11px] text-slate-500 font-medium">
                Evaluating verified commerce catalog &amp; policies...
              </span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Footer / Input Bar */}
        <div className="p-3 border-t border-slate-100 bg-white space-y-2">
          {/* Quick Prompts */}
          <div className="flex gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            {PROMPT_SUGGESTIONS.map((sug, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onSendMessage(sug)}
                className="whitespace-nowrap px-2.5 py-1 rounded-full bg-slate-100 text-[11px] text-slate-600 hover:bg-slate-200 hover:text-slate-900 transition-colors font-medium shrink-0"
              >
                {sug}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex gap-2 items-center">
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder="Type in English, Hindi, or Hinglish..."
              className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all"
            />

            {onOpenVoiceSearch && (
              <button
                type="button"
                onClick={onOpenVoiceSearch}
                className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900 transition-colors shrink-0"
                aria-label="Voice Search"
                title="Voice Search"
              >
                <MicIcon size={14} />
              </button>
            )}

            <Button
              type="submit"
              size="sm"
              variant="primary"
              disabled={!inputVal.trim() || isLoading}
              className="px-4 shrink-0 font-semibold"
            >
              Send
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
