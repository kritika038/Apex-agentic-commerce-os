import React from 'react';

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`bg-slate-200 animate-pulse rounded-xl ${className}`}
      aria-hidden="true"
    />
  );
}

export function ProductCardSkeleton() {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-4 space-y-4 shadow-xs">
      <Skeleton className="w-full aspect-square rounded-xl" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
      </div>
      <div className="flex items-center justify-between pt-2">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="h-9 w-24 rounded-xl" />
      </div>
    </div>
  );
}

export function CartItemSkeleton() {
  return (
    <div className="flex items-center gap-3 p-3 bg-white border border-slate-100 rounded-xl">
      <Skeleton className="w-16 h-16 rounded-lg shrink-0" />
      <div className="flex-1 space-y-1.5">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/3" />
      </div>
      <Skeleton className="h-7 w-20 rounded-lg" />
    </div>
  );
}

export function MetricCardSkeleton() {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-3 shadow-xs">
      <div className="flex items-center justify-between">
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="w-6 h-6 rounded-lg" />
      </div>
      <Skeleton className="h-7 w-32" />
      <Skeleton className="h-3 w-40" />
    </div>
  );
}
