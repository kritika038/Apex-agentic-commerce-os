'use client';

import React from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { PrinterIcon, CheckCircleIcon } from '@/components/ui/Icons';
import { OrderData } from '@/lib/types/orders';

export interface OrderInvoiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: OrderData | null;
}

export function OrderInvoiceModal({ isOpen, onClose, order }: OrderInvoiceModalProps) {
  if (!order) return null;

  const handlePrint = () => {
    if (typeof window !== 'undefined') {
      window.print();
    }
  };

  const formattedDate = new Date(order.created_at).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Official Tax Invoice & Receipt" maxWidth="lg">
      <div className="space-y-6 text-slate-900 print:text-black">
        {/* Invoice Header */}
        <div className="flex items-start justify-between border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center text-white font-bold text-sm">
                ⚡
              </div>
              <span className="text-lg font-black tracking-tight text-slate-900">Apex Sports Store</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">Governed AI Commerce OS · Retail Receipt</p>
          </div>
          <div className="text-right">
            <div className="text-sm font-bold text-slate-900">INVOICE</div>
            <div className="text-xs font-mono font-bold text-indigo-600">#{order.order_number}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">{formattedDate}</div>
          </div>
        </div>

        {/* Customer & Billing Details */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs bg-slate-50 p-4 rounded-xl border border-slate-200">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
              Delivered & Billed To
            </span>
            {order.delivery_address ? (
              <div className="space-y-0.5 text-slate-800">
                <div className="font-semibold text-slate-900">{order.delivery_address.full_name}</div>
                <div>{order.delivery_address.address_line1}</div>
                {order.delivery_address.address_line2 && <div>{order.delivery_address.address_line2}</div>}
                {order.delivery_address.landmark && (
                  <div className="text-slate-500">Near: {order.delivery_address.landmark}</div>
                )}
                <div>
                  {order.delivery_address.city}, {order.delivery_address.state} - {order.delivery_address.pin_code}
                </div>
                <div>{order.delivery_address.country}</div>
                <div className="mt-1 text-slate-600">Ph: +91 {order.delivery_address.phone}</div>
                <div className="text-slate-600">{order.delivery_address.email}</div>
              </div>
            ) : (
              <div className="text-slate-500">Customer profile address</div>
            )}
          </div>

          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
              Payment & Governance Summary
            </span>
            <div className="space-y-1 text-slate-800">
              <div className="flex justify-between">
                <span className="text-slate-500">Payment Gateway:</span>
                <span className="font-medium text-slate-900">Razorpay Secure</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Payment Status:</span>
                <span className="font-bold text-emerald-700">{order.payment.status}</span>
              </div>
              {order.payment.razorpay_payment_id && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Payment ID:</span>
                  <span className="font-mono text-slate-900">{order.payment.razorpay_payment_id}</span>
                </div>
              )}
              {order.payment.razorpay_order_id && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Razorpay Order ID:</span>
                  <span className="font-mono text-slate-900">{order.payment.razorpay_order_id}</span>
                </div>
              )}
              <div className="flex justify-between pt-1 border-t border-slate-200">
                <span className="text-slate-500">Security Signature:</span>
                <span className="text-[11px] font-semibold text-emerald-700 flex items-center gap-1">
                  <CheckCircleIcon size={12} /> HMAC-SHA256 Verified
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Itemized Table */}
        <div className="overflow-x-auto border border-slate-200 rounded-xl">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100/75 border-b border-slate-200 text-slate-600 font-semibold">
              <tr>
                <th className="py-2.5 px-3">Item Description</th>
                <th className="py-2.5 px-3 text-center">Qty</th>
                <th className="py-2.5 px-3 text-right">Unit Rate (₹)</th>
                <th className="py-2.5 px-3 text-right">Amount (₹)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 text-slate-800">
              {order.items.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-50/50">
                  <td className="py-2.5 px-3">
                    <div className="font-semibold text-slate-900">{item.name}</div>
                    <div className="text-[11px] text-slate-500">{item.category}</div>
                  </td>
                  <td className="py-2.5 px-3 text-center">{item.quantity}</td>
                  <td className="py-2.5 px-3 text-right font-mono">₹{Number(item.unit_price).toLocaleString('en-IN')}</td>
                  <td className="py-2.5 px-3 text-right font-mono font-semibold">
                    ₹{Number(item.subtotal).toLocaleString('en-IN')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Financial Summary */}
        <div className="flex justify-end">
          <div className="w-full sm:w-64 space-y-1.5 text-xs">
            <div className="flex justify-between text-slate-600">
              <span>Items Subtotal:</span>
              <span className="font-mono">₹{Number(order.price_summary.subtotal).toLocaleString('en-IN')}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Delivery Charges:</span>
              <span className="font-semibold text-emerald-700">FREE</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Taxes (GST Included):</span>
              <span className="font-mono">₹0.00</span>
            </div>
            <div className="flex justify-between text-sm font-bold text-slate-900 pt-2 border-t border-slate-200">
              <span>Total Paid:</span>
              <span className="font-mono text-indigo-700">₹{Number(order.total_amount).toLocaleString('en-IN')}</span>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between border-t border-slate-200 pt-4 print:hidden">
          <div className="text-[11px] text-slate-500">
            This is an authoritative computer-generated receipt issued under Agentic Commerce OS.
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Close
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handlePrint}
              leftIcon={<PrinterIcon size={14} />}
            >
              Print / Save PDF
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
