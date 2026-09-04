import React, { useEffect } from 'react';
import { CheckIcon, AlertTriangleIcon, XIcon } from './Icons';

export interface ToastProps {
  message: string;
  type?: 'success' | 'error' | 'info';
  onClose: () => void;
  duration?: number;
}

export function Toast({ message, type = 'info', onClose, duration = 3500 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, duration);
    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const typeStyles = {
    success: 'bg-emerald-50 border-emerald-200 text-emerald-900',
    error: 'bg-rose-50 border-rose-200 text-rose-900',
    info: 'bg-indigo-50 border-indigo-200 text-indigo-900',
  };

  const iconStyles = {
    success: <CheckIcon size={16} className="text-emerald-600" />,
    error: <AlertTriangleIcon size={16} className="text-rose-600" />,
    info: <span className="text-indigo-600 font-bold text-xs">ℹ</span>,
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-4 fade-in duration-200">
      <div
        className={`flex items-center gap-3 px-4 py-3 rounded-2xl border shadow-lg ${typeStyles[type]} min-w-[280px] max-w-md bg-white`}
      >
        <div className="shrink-0">{iconStyles[type]}</div>
        <p className="text-xs font-medium flex-1 leading-snug">{message}</p>
        <button
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          aria-label="Close notification"
        >
          <XIcon size={14} />
        </button>
      </div>
    </div>
  );
}
