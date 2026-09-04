'use client';

import React, { useEffect, useState, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiClient, extractErrorMessage } from '@/lib/api';

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [statusText, setStatusText] = useState('Signing you in...');
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(true);
  const hasExecutedRef = useRef(false);

  useEffect(() => {
    // Prevent double execution in React Strict Mode
    if (hasExecutedRef.current) return;

    const code = searchParams.get('code');
    const oauthError = searchParams.get('error');

    if (oauthError) {
      setIsProcessing(false);
      if (oauthError === 'access_denied') {
        setError('Google sign-in was cancelled.');
      } else {
        setError(`Google sign-in error: ${oauthError}`);
      }
      return;
    }

    if (!code) {
      setIsProcessing(false);
      setError('Authorization code missing from Google redirect.');
      return;
    }

    hasExecutedRef.current = true;

    // Timeout safety guard (12 seconds)
    const timeoutTimer = setTimeout(() => {
      setIsProcessing((prev) => {
        if (prev) {
          setError('Google authentication request timed out. Please verify your connection and try again.');
          return false;
        }
        return false;
      });
    }, 12000);

    const exchangeCode = async () => {
      try {
        setStatusText('Verifying Google credentials with security server...');
        const dynamicRedirectUri = `${window.location.origin}/auth/callback`;

        const res = await apiClient.post('/auth/google/callback', {
          code,
          redirect_uri: dynamicRedirectUri,
        });

        clearTimeout(timeoutTimer);

        const { access_token, user } = res.data;

        if (access_token) {
          localStorage.setItem('access_token', access_token);
        }
        if (user) {
          localStorage.setItem('user_profile', JSON.stringify(user));
        }

        // Verify session against /auth/me for server-authoritative role
        try {
          const meRes = await apiClient.get('/auth/me', {
            headers: { Authorization: `Bearer ${access_token}` },
          });
          if (meRes.data) {
            localStorage.setItem('user_profile', JSON.stringify(meRes.data));
          }
        } catch {
          // Fallback to returned user if /auth/me network blip occurs
        }

        setStatusText('Authentication successful! Routing to your workspace...');
        setIsProcessing(false);

        const resolvedRole = user?.role || 'customer';
        const destination = resolvedRole === 'merchant_admin' ? '/dashboard' : '/shopping';

        // Perform clean navigation
        window.location.replace(destination);
      } catch (err: unknown) {
        clearTimeout(timeoutTimer);
        setIsProcessing(false);
        const safeError = extractErrorMessage(
          err,
          'Google authentication could not be completed. Please check your credentials and try again.'
        );
        setError(safeError);
      }
    };

    exchangeCode();

    return () => {
      clearTimeout(timeoutTimer);
    };
  }, [searchParams, router]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="max-w-md w-full p-8 rounded-2xl bg-white border border-slate-200 shadow-xl text-center space-y-6">
        <div className="w-12 h-12 rounded-2xl bg-slate-900 mx-auto flex items-center justify-center text-xl text-white font-bold shadow-xs">
          ⚡
        </div>

        <div className="space-y-1">
          <h2 className="text-lg font-bold text-slate-900">
            {error ? 'Google sign-in failed' : 'Signing you in...'}
          </h2>
          <p className="text-xs text-slate-500">
            {error ? 'We were unable to complete your Google sign-in.' : statusText}
          </p>
        </div>

        {error ? (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs text-left space-y-3">
            <div className="font-semibold flex items-center gap-1.5 text-rose-700">
              <span>⚠️</span> {error}
            </div>
            <div className="pt-2 flex gap-2">
              <button
                onClick={() => {
                  window.location.replace('/');
                }}
                className="flex-1 py-2 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition-colors"
              >
                Try Again
              </button>
              <button
                onClick={() => {
                  window.location.replace('/shopping');
                }}
                className="py-2 px-4 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs transition-colors"
              >
                Storefront
              </button>
            </div>
          </div>
        ) : (
          isProcessing && (
            <div className="flex justify-center items-center py-4">
              <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
            </div>
          )
        )}

        <div className="text-[11px] text-slate-400 pt-2 border-t border-slate-100">
          Agentic Commerce OS • Authoritative Security Boundary
        </div>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  );
}

