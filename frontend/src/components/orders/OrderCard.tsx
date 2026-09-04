'use client';

import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/Button';
import { CheckCircleIcon, RotateCcwIcon, ReceiptIcon } from '@/components/ui/Icons';
import { OrderData } from '@/lib/types/orders';
import { ProductImage } from '@/components/ui/ProductImage';

export interface OrderCardProps {
  order: OrderData;
  onViewDetails: (order: OrderData) => void;
  onBuyAgain: (orderId: string) => void;
  onViewInvoice: (order: OrderData) => void;
  isReordering?: boolean;
}

export function OrderCard({
  order,
  onViewDetails,
  onBuyAgain,
  onViewInvoice,
  isReordering = false,
}: OrderCardProps) {
  const formattedDate = new Date(order.created_at).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

  return (
    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-2xs hover:shadow-xs transition-shadow">
      {/* Card Header */}
      <div className="px-4 sm:px-6 py-4 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="text-xs font-semibold text-slate-500 block">ORDER PLACED</span>
          <span className="text-sm font-medium text-slate-900">{formattedDate}</span>
        </div>
        <div>
          <span className="text-xs font-semibold text-slate-500 block">TOTAL</span>
          <span className="text-sm font-bold font-mono text-slate-900">
            ₹{Number(order.total_amount).toLocaleString('en-IN')}
          </span>
        </div>
        <div>
          <span className="text-xs font-semibold text-slate-500 block">ORDER #</span>
          <span className="text-xs font-mono font-medium text-slate-700">{order.id}</span>
        </div>
        <div>
          <span
            className={`px-2.5 py-1 rounded-full text-xs font-bold ${
              order.status === 'CONFIRMED' || order.status === 'DELIVERED'
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : order.status === 'PROCESSING' || order.status === 'RETURN_REQUESTED'
                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                : 'bg-rose-50 text-rose-700 border border-rose-200'
            }`}
          >
            {order.status}
          </span>
        </div>
      </div>

      {/* Card Body — Item List */}
      <div className="px-4 sm:px-6 py-4 divide-y divide-slate-100">
        {order.items.map((item, idx) => (
          <div key={idx} className="flex items-center gap-4 py-3 first:pt-0 last:pb-0">
            <div className="w-16 h-16 rounded-xl bg-slate-100 border border-slate-200 overflow-hidden shrink-0 flex items-center justify-center">
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
              <h4 className="text-sm font-semibold text-slate-900 truncate">{item.name}</h4>
              <p className="text-xs text-slate-500">{item.category || 'Gear'}</p>
              <div className="flex items-center gap-3 text-xs text-slate-600 mt-1">
                <span>Qty: <span className="font-semibold text-slate-900">{item.quantity}</span></span>
                <span>•</span>
                <span className="font-mono font-medium">₹{Number(item.unit_price).toLocaleString('en-IN')}</span>
              </div>
            </div>

            <div className="text-right shrink-0">
              <span className="text-sm font-mono font-bold text-slate-900">
                ₹{Number(item.subtotal).toLocaleString('en-IN')}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Card Footer Actions */}
      <div className="bg-slate-50/40 border-t border-slate-200/80 px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1 text-emerald-700 font-medium">
            <CheckCircleIcon size={13} /> Razorpay Verified
          </span>
          {order.delivery_address && (
            <>
              <span>•</span>
              <span className="text-slate-500 truncate max-w-[200px] sm:max-w-xs">
                Ship to: <span className="text-slate-700 font-medium">{order.delivery_address.city}</span>
              </span>
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onViewInvoice(order)}
            className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition-colors"
            title="View Invoice"
            aria-label="View Invoice"
          >
            <ReceiptIcon size={16} />
          </button>

          <Link href={`/orders/${order.id}`}>
            <Button variant="secondary" size="sm">
              Track Order
            </Button>
          </Link>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => onViewDetails(order)}
          >
            Details
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => onBuyAgain(order.id)}
            disabled={isReordering}
            leftIcon={<RotateCcwIcon size={13} />}
          >
            {isReordering ? 'Adding...' : 'Buy Again'}
          </Button>
        </div>
      </div>
    </div>
  );
}
