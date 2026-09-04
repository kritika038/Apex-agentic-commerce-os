'use client';

import React from 'react';
import Link from 'next/link';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { CheckCircleIcon, MapPinIcon, ReceiptIcon, RotateCcwIcon, ClockIcon } from '@/components/ui/Icons';
import { OrderData } from '@/lib/types/orders';
import { ProductImage } from '@/components/ui/ProductImage';

export interface OrderDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: OrderData | null;
  onBuyAgain: (orderId: string) => void;
  onOpenInvoice: (order: OrderData) => void;
  isReordering?: boolean;
}

export function OrderDetailsModal({
  isOpen,
  onClose,
  order,
  onBuyAgain,
  onOpenInvoice,
  isReordering = false,
}: OrderDetailsModalProps) {
  if (!order) return null;

  const formattedDate = new Date(order.created_at).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Order #${order.order_number}`} maxWidth="lg">
      <div className="space-y-6 text-slate-900">
        {/* Top Status Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
          <div>
            <div className="text-xs text-slate-500 font-medium">Order Placed on</div>
            <div className="text-sm font-bold text-slate-900 mt-0.5">{formattedDate}</div>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`px-2.5 py-1 text-xs font-bold rounded-full ${
                order.status === 'CONFIRMED'
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : order.status === 'PROCESSING'
                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                  : 'bg-rose-50 text-rose-700 border border-rose-200'
              }`}
            >
              {order.status}
            </span>
            <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
              Payment: {order.payment.status}
            </span>
          </div>
        </div>

        {/* Chronological Status Timeline */}
        <div className="border border-slate-200 rounded-xl p-4 bg-white">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Order Status Progression</h4>
          <div className="space-y-3">
            {order.timeline.map((step, idx) => (
              <div key={idx} className="flex items-start gap-3">
                <div className="pt-0.5 shrink-0">
                  {step.status === 'COMPLETED' ? (
                    <div className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs">
                      <CheckCircleIcon size={13} />
                    </div>
                  ) : step.status === 'FAILED' ? (
                    <div className="w-5 h-5 rounded-full bg-rose-100 text-rose-700 flex items-center justify-center text-xs font-bold">
                      ✕
                    </div>
                  ) : (
                    <div className="w-5 h-5 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center text-xs">
                      <ClockIcon size={12} />
                    </div>
                  )}
                </div>
                <div className="flex-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span
                      className={`font-semibold ${
                        step.status === 'COMPLETED'
                          ? 'text-slate-900'
                          : step.status === 'FAILED'
                          ? 'text-rose-700'
                          : 'text-slate-500'
                      }`}
                    >
                      {step.title}
                    </span>
                    {step.timestamp && (
                      <span className="text-[11px] text-slate-400">
                        {new Date(step.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>
                  {step.description && <p className="text-[11px] text-slate-500 mt-0.5">{step.description}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Purchased Products */}
        <div className="border border-slate-200 rounded-xl overflow-hidden">
          <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-200">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Purchased Items ({order.items.length})
            </h4>
          </div>
          <div className="divide-y divide-slate-100 p-2">
            {order.items.map((item, idx) => (
              <div key={idx} className="flex items-center gap-3 p-2 hover:bg-slate-50/50 rounded-lg">
                <div className="w-14 h-14 rounded-lg bg-slate-100 border border-slate-200 overflow-hidden shrink-0 flex items-center justify-center">
                  <ProductImage
                    src={item.image_url}
                    alt={item.name}
                    productName={item.name}
                    category={item.category}
                    className="w-full h-full object-cover"
                    containerClassName="w-full h-full"
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <h5 className="text-xs font-semibold text-slate-900 truncate">{item.name}</h5>
                  <span className="text-[11px] text-slate-500">{item.category || 'Gear'}</span>
                  <div className="text-xs text-slate-600 mt-0.5">
                    Qty: <span className="font-semibold">{item.quantity}</span> × ₹
                    {Number(item.unit_price).toLocaleString('en-IN')}
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xs font-mono font-bold text-slate-900">
                    ₹{Number(item.subtotal).toLocaleString('en-IN')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Delivery Address & Financial Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Delivery Address Snapshot */}
          <div className="border border-slate-200 rounded-xl p-4 bg-slate-50/50 text-xs space-y-1.5">
            <div className="flex items-center gap-1.5 text-slate-700 font-bold uppercase tracking-wider text-[11px] mb-2">
              <MapPinIcon size={14} className="text-indigo-600" />
              <span>Immutable Delivery Snapshot</span>
            </div>
            {order.delivery_address ? (
              <div className="text-slate-800 space-y-0.5">
                <div className="font-bold text-slate-900">{order.delivery_address.full_name}</div>
                <div>{order.delivery_address.address_line1}</div>
                {order.delivery_address.address_line2 && <div>{order.delivery_address.address_line2}</div>}
                {order.delivery_address.landmark && (
                  <div className="text-slate-500">Near: {order.delivery_address.landmark}</div>
                )}
                <div>
                  {order.delivery_address.city}, {order.delivery_address.state} - {order.delivery_address.pin_code}
                </div>
                <div className="pt-1 text-slate-600">Ph: +91 {order.delivery_address.phone}</div>
                <div className="text-slate-600">{order.delivery_address.email}</div>
              </div>
            ) : (
              <div className="text-slate-500">Address recorded on customer profile</div>
            )}
          </div>

          {/* Payment & Price Summary */}
          <div className="border border-slate-200 rounded-xl p-4 bg-slate-50/50 text-xs space-y-2">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-700 mb-2">
              Payment & Price Breakdown
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Items Total:</span>
              <span className="font-mono">₹{Number(order.price_summary.subtotal).toLocaleString('en-IN')}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Delivery Fee:</span>
              <span className="font-semibold text-emerald-700">FREE</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Payment Gateway:</span>
              <span className="font-semibold text-slate-800">Razorpay</span>
            </div>
            {order.payment.razorpay_payment_id && (
              <div className="flex justify-between text-slate-600">
                <span>Payment ID:</span>
                <span className="font-mono text-slate-900">{order.payment.razorpay_payment_id}</span>
              </div>
            )}
            <div className="flex justify-between text-sm font-bold text-slate-900 pt-2 border-t border-slate-200">
              <span>Total Paid:</span>
              <span className="font-mono text-indigo-700">₹{Number(order.total_amount).toLocaleString('en-IN')}</span>
            </div>
          </div>
        </div>

        {/* Modal Actions */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4">
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onOpenInvoice(order)}
              leftIcon={<ReceiptIcon size={14} />}
            >
              Print Invoice
            </Button>
            <Link href={`/orders/${order.id}`}>
              <Button variant="secondary" size="sm">
                Track Full Order →
              </Button>
            </Link>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Close
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => onBuyAgain(order.id)}
              disabled={isReordering}
              leftIcon={<RotateCcwIcon size={14} />}
            >
              {isReordering ? 'Adding to Cart...' : 'Buy Again'}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
