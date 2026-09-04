import React from 'react';
import Link from 'next/link';

export interface MetricCardProps {
  title: string;
  value: string | number;
  subtext?: string;
  icon?: React.ReactNode;
  trend?: {
    value: string;
    isPositive: boolean;
  };
  variant?: 'neutral' | 'purple' | 'success' | 'warning';
  href?: string;
  onClick?: () => void;
  ctaText?: string;
}

export function MetricCard({
  title,
  value,
  subtext,
  icon,
  trend,
  href,
  onClick,
  ctaText = 'View details',
}: MetricCardProps) {
  const cardContent = (
    <div className="flex flex-col justify-between h-full space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider group-hover:text-indigo-600 transition-colors">
          {title}
        </span>
        {icon && (
          <div className="w-7 h-7 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center text-slate-700 group-hover:bg-indigo-50 group-hover:text-indigo-600 group-hover:border-indigo-100 transition-colors">
            {icon}
          </div>
        )}
      </div>

      <div className="space-y-1">
        <div className="text-2xl font-extrabold text-slate-900 tracking-tight group-hover:text-indigo-950 transition-colors">
          {value}
        </div>
        {(subtext || trend) && (
          <div className="flex items-center gap-2 text-xs">
            {trend && (
              <span
                className={`font-semibold ${
                  trend.isPositive ? 'text-emerald-600' : 'text-rose-600'
                }`}
              >
                {trend.isPositive ? '↑' : '↓'} {trend.value}
              </span>
            )}
            {subtext && <span className="text-slate-500 leading-snug">{subtext}</span>}
          </div>
        )}
      </div>

      {(href || onClick) && (
        <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] font-medium text-slate-400 group-hover:text-indigo-600 transition-colors">
          <span>{ctaText}</span>
          <span className="transform group-hover:translate-x-0.5 transition-transform">&rarr;</span>
        </div>
      )}
    </div>
  );

  const containerClasses = `bg-white border border-slate-200 rounded-2xl p-5 shadow-xs transition-all duration-200 flex flex-col justify-between ${
    href || onClick
      ? 'group cursor-pointer hover:border-indigo-300 hover:shadow-md hover:bg-slate-50/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2'
      : ''
  }`;

  if (href) {
    return (
      <Link href={href} className={containerClasses} aria-label={`${title}: ${value}. ${subtext || ''}`}>
        {cardContent}
      </Link>
    );
  }

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${containerClasses} text-left w-full`}
        aria-label={`${title}: ${value}. ${subtext || ''}`}
      >
        {cardContent}
      </button>
    );
  }

  return <div className={containerClasses}>{cardContent}</div>;
}

