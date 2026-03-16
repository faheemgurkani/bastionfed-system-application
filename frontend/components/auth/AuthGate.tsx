'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/auth-context';

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading, isGuest } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user && !isGuest) {
      router.replace('/');
    }
  }, [loading, user, isGuest, router]);

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center min-h-[calc(100vh-64px)]">
        <div className="w-8 h-8 border-2 border-border-strong border-t-white rounded-full animate-spin" aria-hidden />
      </div>
    );
  }

  if (!user && !isGuest) {
    return null;
  }

  return <>{children}</>;
}
