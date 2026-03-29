'use client';

import { useState, KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
}

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (input.trim() && !isLoading) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="relative flex items-center">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        placeholder={isLoading ? "BastionBot is thinking..." : "Ask BastionBot about BastionFed features, workflows, alerts, incidents, or APIs..."}
        className="w-full min-w-0 bg-bg-surface border border-border-default rounded-lg pl-4 pr-14 py-3 sm:py-4 text-sm text-white placeholder:text-text-muted focus:outline-none focus:border-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      />
      
      <button 
        onClick={handleSend}
        disabled={!input.trim() || isLoading}
        className="absolute right-3 p-2 bg-white text-black rounded hover:bg-interactive-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
      </button>
    </div>
  );
}
