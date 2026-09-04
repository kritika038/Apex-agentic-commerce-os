'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api';

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const router = useRouter();
  const pathname = usePathname();
  const [status, setStatus] = useState<'checking' | 'allowed'>('checking');

  useEffect(() => {
    document.title = 'Apex Merchant | AI Commerce OS';
    const verifyAccess = async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.replace('/');
        return;
      }

      try {
        const response = await apiClient.get('/auth/me', {
          headers: { Authorization: `Bearer ${token}` },
        });
        const user = response.data;
        localStorage.setItem('user_profile', JSON.stringify(user));

        if (user.role !== 'merchant_admin') {
          router.replace('/shopping');
          return;
        }

        setStatus('allowed');
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_profile');
        router.replace('/');
      }
    };

    setStatus('checking');
    verifyAccess();
  }, [pathname, router]);

  if (status !== 'allowed') {
    return (
      <div className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center">
        <div className="flex items-center gap-2.5 text-xs font-semibold text-slate-500">
          <span className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <span>Verifying merchant authorization...</span>
        </div>
      </div>
    );
  }

  return children;
}
