import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { UserIcon, LockIcon, AlertTriangleIcon } from '@/components/ui/Icons';
import { apiClient, extractErrorMessage } from '@/lib/api';

import { UserProfile } from '@/lib/types/user';
export type { UserProfile };

export interface AuthConfig {
  google_oauth_configured: boolean;
  allow_dev_auth: boolean;
  environment: string;
}

export interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  authConfig: AuthConfig | null;
  onSuccess: (user: UserProfile, token: string) => void;
}

export function AuthModal({
  isOpen,
  onClose,
  authConfig,
  onSuccess,
}: AuthModalProps) {
  const router = useRouter();
  const [authType, setAuthType] = useState<'customer' | 'merchant'>('customer');
  const [mode, setMode] = useState<'signin' | 'register'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGoogleSignIn = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const targetRole = authType === 'merchant' ? 'merchant_admin' : 'customer';
      const redirectUri =
        typeof window !== 'undefined'
          ? `${window.location.origin}/auth/callback`
          : undefined;
      const url = redirectUri
        ? `/auth/google/url?role=${targetRole}&redirect_uri=${encodeURIComponent(redirectUri)}`
        : `/auth/google/url?role=${targetRole}`;

      const res = await apiClient.get(url);
      if (res.data.configured && res.data.auth_url) {
        window.location.href = res.data.auth_url;
      } else {
        setError('Google sign-in is not configured on this server. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env.');
      }
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Google authentication could not be completed. Please try again.'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleEmailPasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      if (mode === 'signin') {
        const res = await apiClient.post('/auth/login-json', { email, password });
        const { access_token, user } = res.data;
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('user_profile', JSON.stringify(user));
        onSuccess(user, access_token);
        onClose();
        if (user.role === 'merchant_admin') {
          router.push('/dashboard');
        }
      } else {
        const res = await apiClient.post('/auth/register', {
          email,
          password,
          full_name: fullName,
        });
        const { access_token, user } = res.data;
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('user_profile', JSON.stringify(user));
        onSuccess(user, access_token);
        onClose();
        if (user.role === 'merchant_admin') {
          router.push('/dashboard');
        }
      }
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Authentication failed. Please check your credentials.'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleDevLogin = async (role: 'customer' | 'merchant_admin') => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.post('/auth/dev-login', { role });
      const { access_token, user } = res.data;
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('user_profile', JSON.stringify(user));
      onSuccess(user, access_token);
      onClose();
      if (user.role === 'merchant_admin') {
        router.push('/dashboard');
      }
    } catch {
      setError('Developer login is disabled in this environment.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="space-y-1">
          <div className="text-base font-bold text-white">
            {authType === 'merchant'
              ? 'Merchant Portal'
              : mode === 'signin'
              ? 'Welcome back'
              : 'Create Account'}
          </div>
          <div className="text-xs text-slate-400 font-normal">
            {authType === 'merchant'
              ? 'Sign in to manage your commerce operations'
              : 'Sign in to continue shopping'}
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {/* Customer vs Merchant Switch Tabs */}
        <div className="flex rounded-xl bg-slate-950 p-1 border border-slate-800">
          <button
            type="button"
            onClick={() => {
              setAuthType('customer');
              setError(null);
            }}
            className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              authType === 'customer'
                ? 'bg-slate-800 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Customer
          </button>
          <button
            type="button"
            onClick={() => {
              setAuthType('merchant');
              setMode('signin');
              setError(null);
            }}
            className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              authType === 'merchant'
                ? 'bg-slate-800 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Merchant
          </button>
        </div>

        {/* Informational hint for merchant tab */}
        {authType === 'merchant' && (
          <p className="text-[11px] text-slate-400 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
            ℹ️ Merchant privileges are determined server-side. Signing in will route to the merchant console if your account is authorized.
          </p>
        )}

        {/* Error Alert */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800/60 text-xs text-rose-300 flex items-start gap-2">
            <AlertTriangleIcon size={14} className="text-rose-400 flex-shrink-0 mt-0.5" />
            <span className="leading-snug">{error}</span>
          </div>
        )}

        {/* Google OAuth (Available for Customer & Merchant) */}
        <div className="space-y-2">
          <Button
            type="button"
            onClick={handleGoogleSignIn}
            isLoading={isLoading}
            variant="secondary"
            size="md"
            className="w-full bg-white hover:bg-slate-100 text-slate-900 border-none font-bold"
            leftIcon={
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path
                  fill="#EA4335"
                  d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.7 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.3 9 5 12 5z"
                />
                <path
                  fill="#4285F4"
                  d="M23.5 12.3c0-.8-.1-1.7-.2-2.3H12v4.6h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.9z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 12.3 0 15.1s.7 5.4 1.9 7.8l3.7-2.9z"
                />
                <path
                  fill="#34A853"
                  d="M12 23.5c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.3-6.4-5.2L1.9 16.5C3.7 20.2 7.5 23.5 12 23.5z"
                />
              </svg>
            }
          >
            Continue with Google
          </Button>

          {!authConfig?.google_oauth_configured && (
            <p className="text-[10px] text-slate-500 text-center">
              Google OAuth is optional in development. You can also sign in with email and password below.
            </p>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-slate-800" />
          <span className="text-[10px] text-slate-500 uppercase font-semibold">
            Or with email
          </span>
          <div className="flex-1 h-px bg-slate-800" />
        </div>

        {/* Demo Merchant Credentials Box (Merchant Tab Only) */}
        {authType === 'merchant' && (
          <div className="rounded-xl border border-indigo-500/30 bg-gradient-to-br from-indigo-950/60 to-slate-950 p-3.5 space-y-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wide uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                ⚡ Competition Demo Account
              </span>
              <button
                type="button"
                onClick={() => {
                  setEmail('demo-merchant@apex.test');
                  setPassword('ApexDemo@2026');
                  setError(null);
                }}
                className="text-[11px] font-bold text-indigo-300 hover:text-white bg-indigo-600/40 hover:bg-indigo-600 px-2.5 py-1 rounded-lg border border-indigo-500/50 transition-all shadow-xs flex items-center gap-1 cursor-pointer active:scale-95"
              >
                Use Demo Credentials →
              </button>
            </div>

            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-white">Demo Merchant Credentials</div>
              <p className="text-[11px] text-slate-400 leading-snug">
                Use these credentials to explore the merchant console with live catalog, inventory risk alerts, governance policies, and audit ledger.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 font-mono text-[11px]">
              <div className="flex items-center justify-between bg-slate-900/90 px-2.5 py-1.5 rounded-lg border border-slate-800">
                <span className="text-slate-400 font-sans text-[10px]">User ID:</span>
                <span className="text-indigo-200 font-semibold select-all">demo-merchant@apex.test</span>
              </div>
              <div className="flex items-center justify-between bg-slate-900/90 px-2.5 py-1.5 rounded-lg border border-slate-800">
                <span className="text-slate-400 font-sans text-[10px]">Password:</span>
                <span className="text-indigo-200 font-semibold select-all">ApexDemo@2026</span>
              </div>
            </div>
          </div>
        )}

        {/* Email & Password Form */}
        <form onSubmit={handleEmailPasswordSubmit} className="space-y-3">
          {authType === 'customer' && mode === 'register' && (
            <Input
              label="Full Name"
              placeholder="Alex Customer"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              leftIcon={<UserIcon size={14} />}
            />
          )}

          <Input
            label="Email Address"
            type="email"
            placeholder={authType === 'merchant' ? 'demo-merchant@apex.test' : 'customer@example.com'}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            leftIcon={<UserIcon size={14} />}
          />

          <Input
            label="Password"
            type="password"
            placeholder={authType === 'merchant' ? 'ApexDemo@2026' : '••••••••'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            leftIcon={<LockIcon size={14} />}
          />

          <Button
            type="submit"
            isLoading={isLoading}
            variant="primary"
            size="md"
            className="w-full mt-2"
          >
            {mode === 'signin' ? 'Sign In' : 'Create Account'}
          </Button>
        </form>

        {/* Register / Sign In Switch (Customers Only) */}
        {authType === 'customer' && (
          <div className="text-center text-xs text-slate-400 pt-1">
            {mode === 'signin' ? (
              <>
                Don&apos;t have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('register');
                    setError(null);
                  }}
                  className="text-indigo-400 hover:text-indigo-300 font-semibold underline"
                >
                  Register
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('signin');
                    setError(null);
                  }}
                  className="text-indigo-400 hover:text-indigo-300 font-semibold underline"
                >
                  Sign In
                </button>
              </>
            )}
          </div>
        )}

        {/* Developer Login Accordion (DEV ONLY) */}
        {authConfig?.allow_dev_auth && (
          <details className="pt-2 border-t border-slate-800/80 text-[11px]">
            <summary className="text-slate-500 hover:text-slate-300 cursor-pointer font-medium select-none">
              Developer Login (Local Test Accounts)
            </summary>
            <div className="mt-2 p-2.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <p className="text-[10px] text-slate-400">
                Instant one-click test authentication for local development:
              </p>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  type="button"
                  onClick={() => handleDevLogin('customer')}
                  isLoading={isLoading}
                  variant="secondary"
                  size="sm"
                  className="text-[11px] h-8"
                >
                  Developer Customer
                </Button>
                <Button
                  type="button"
                  onClick={() => handleDevLogin('merchant_admin')}
                  isLoading={isLoading}
                  variant="secondary"
                  size="sm"
                  className="text-[11px] h-8 text-indigo-300"
                >
                  Developer Merchant Admin
                </Button>
              </div>
            </div>
          </details>
        )}
      </div>
    </Modal>
  );
}
