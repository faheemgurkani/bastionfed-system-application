'use client';

import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/auth-context';
import { Shield } from 'lucide-react';

export function AccessCard() {
  const router = useRouter();
  const { signInWithGoogle, continueAsGuest } = useAuth();

  const handleGuestAccess = () => {
    continueAsGuest();
    router.push('/dashboard');
  };

  const handleGoogleSignIn = async () => {
    await signInWithGoogle();
    router.push('/dashboard');
  };

  return (
    <div className="overflow-hidden rounded-lg border border-border-default bg-bg-surface">
      <div className="grid grid-cols-1 md:grid-cols-2">
        <div className="flex flex-col gap-6 p-6 md:p-8">
          <div className="flex flex-col items-center text-center">
            <h2 className="text-2xl font-display font-bold text-white">
              Access BastionFed SOC
            </h2>
            <p className="text-balance text-sm text-text-muted mt-4">
              Sign in with Google or continue as a guest to access the Blue Team console.
            </p>
          </div>
          <div className="flex flex-col gap-4 mt-8 md:mt-12">
            <button
              onClick={handleGoogleSignIn}
              type="button"
              className="flex w-full items-center justify-center gap-2 rounded-md border border-border-strong bg-bg-overlay px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-bg-subtle"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="h-4 w-4">
                <path
                  d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
                  fill="currentColor"
                />
              </svg>
              Sign in with Google
            </button>
            <div className="relative text-center text-sm">
              <span className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-border-default" />
              </span>
              <span className="relative z-10 bg-bg-surface px-2 text-text-muted">
                Or continue with
              </span>
            </div>
            <button
              onClick={handleGuestAccess}
              type="button"
              className="flex w-full items-center justify-center gap-2 rounded-md bg-white px-4 py-3 text-sm font-medium text-black transition-colors hover:bg-interactive-hover"
            >
              Continue as guest
            </button>
          </div>
        </div>
        <div className="relative hidden bg-bg-elevated md:block">
          <div className="absolute inset-0 flex items-center justify-center p-8">
            <Shield className="h-24 w-24 text-text-muted" strokeWidth={1.5} />
          </div>
        </div>
      </div>
      <p className="border-t border-border-default px-6 py-3 text-center text-xs text-text-muted">
        By continuing, you agree to our Terms of Service and Privacy Policy.
      </p>
    </div>
  );
}
