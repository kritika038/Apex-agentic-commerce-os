import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'accent' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  const baseStyles =
    'inline-flex items-center justify-center font-medium rounded-xl transition-all duration-150 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none disabled:active:scale-100 select-none';

  const sizeStyles = {
    xs: 'text-xs px-2.5 py-1 gap-1.5',
    sm: 'text-xs px-3 py-1.5 gap-1.5',
    md: 'text-sm px-4 py-2 gap-2',
    lg: 'text-sm sm:text-base px-5 py-2.5 gap-2.5 font-semibold',
  };

  const variantStyles = {
    primary:
      'bg-slate-900 hover:bg-slate-800 text-white shadow-sm hover:shadow active:bg-slate-950',
    accent:
      'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm hover:shadow-md active:bg-indigo-800',
    secondary:
      'bg-white hover:bg-slate-50 text-slate-800 border border-slate-200 shadow-xs active:bg-slate-100',
    outline:
      'bg-transparent hover:bg-slate-100 text-slate-700 border border-slate-300 active:bg-slate-200',
    ghost:
      'bg-transparent hover:bg-slate-100 text-slate-700 active:bg-slate-200',
    danger:
      'bg-rose-600 hover:bg-rose-700 text-white shadow-sm active:bg-rose-800',
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        leftIcon
      )}
      {children}
      {!isLoading && rightIcon}
    </button>
  );
}
