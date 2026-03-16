'use client';

import { AuthGate } from '@/components/auth/AuthGate';
import { ChatInterface } from '@/components/bastionbot/ChatInterface';

export default function BastionBotPage() {
  // FastAPI endpoint: POST http://localhost:8000/api/bastionbot/chat
  // TODO: Replace with fetch() when backend is connected

  return (
    <AuthGate>
    <div className="flex flex-col h-full">
      <div className="mb-6">
        <h1 className="text-2xl font-medium text-white mb-1">BastionBot</h1>
        <p className="text-sm text-text-secondary">AI-assisted threat analysis and SOC operations copilot.</p>
      </div>
      
      <div className="flex-1 min-h-[500px]">
        <ChatInterface />
      </div>
    </div>
    </AuthGate>
  );
}
