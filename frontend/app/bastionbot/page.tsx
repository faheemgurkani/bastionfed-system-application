'use client';

import { useState } from 'react';
import { Shield } from 'lucide-react';
import { ChatInterface } from '@/components/bastionbot/ChatInterface';
import { useAuth } from '@/contexts/auth-context';

export default function BastionBotPage() {
  const { user, loading, isDevMode, signInWithGoogle } = useAuth();
  const [googleBusy, setGoogleBusy] = useState(false);
  const signedInUser = !isDevMode ? user : null;

  async function handleGoogleSignIn() {
    if (googleBusy) return;
    setGoogleBusy(true);
    try {
      await signInWithGoogle();
    } finally {
      setGoogleBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center min-h-[calc(100vh-64px)]">
        <div className="w-8 h-8 border-2 border-border-strong border-t-white rounded-full animate-spin" aria-hidden />
      </div>
    );
  }

  if (!signedInUser) {
    return (
      <div className="flex flex-col h-full">
        <div className="mb-6">
          <h1 className="text-2xl font-medium text-white mb-1">BastionBot</h1>
          <p className="text-sm text-text-secondary">AI-assisted, read-only BastionFed product and workflow copilot.</p>
        </div>

        <div className="flex-1 min-h-[500px] rounded-lg border border-border-default bg-bg-surface p-8 flex items-center justify-center">
          <div className="max-w-xl text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-border-strong bg-bg-overlay">
              <Shield className="w-7 h-7 text-white" />
            </div>
            <h2 className="text-xl font-medium text-white">Sign-in Required</h2>
            <p className="mt-3 text-sm text-text-secondary">
              BastionBot is only available to users who sign up or sign in because conversation history and memory are isolated per user.
              {isDevMode ? ' Dev mode can browse the read-only demo tenant, but BastionBot requires a signed-in account.' : ''}
            </p>
            <button
              onClick={() => void handleGoogleSignIn()}
              disabled={googleBusy}
              className="mt-6 inline-flex items-center justify-center rounded-md bg-white px-5 py-3 text-sm font-medium text-black hover:bg-interactive-hover transition-colors disabled:opacity-50"
            >
              {googleBusy ? 'Opening Google sign-in…' : 'Sign up / Sign in with Google'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="mb-6">
        <h1 className="text-2xl font-medium text-white mb-1">BastionBot</h1>
        <p className="text-sm text-text-secondary">Ask-mode BastionFed copilot for product guidance, implementation details, and live platform context.</p>
      </div>
      
      <div className="flex-1 min-h-[500px]">
        <ChatInterface />
      </div>
    </div>
  );
}
