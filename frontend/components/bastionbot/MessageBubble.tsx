'use client';

import { Bot, User, ShieldAlert, CheckCircle } from 'lucide-react';
import { useState } from 'react';
import Markdown from 'react-markdown';

interface MessageBubbleProps {
  message: {
    id: string;
    role: string;
    content: string;
    timestamp: string;
    action?: {
      type: string;
      target: string;
      label: string;
    };
  };
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isBot = message.role === 'assistant';
  const [actionTaken, setActionTaken] = useState(false);

  const handleAction = () => {
    setActionTaken(true);
    // FastAPI endpoint: POST http://localhost:8000/api/devices/{id}/quarantine
    // TODO: Replace with fetch() when backend is connected
  };

  return (
    <div className={`flex gap-4 ${isBot ? '' : 'flex-row-reverse'}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
        isBot ? 'bg-white text-black' : 'bg-bg-overlay border border-border-strong text-white'
      }`}>
        {isBot ? <Bot className="w-5 h-5" /> : <User className="w-5 h-5" />}
      </div>
      
      <div className={`flex flex-col gap-2 max-w-[80%] ${isBot ? 'items-start' : 'items-end'}`}>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text-secondary">{isBot ? 'BastionBot' : 'Analyst'}</span>
          <span className="font-mono text-[10px] text-text-muted">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
        
        <div className={`p-4 rounded-lg text-sm leading-relaxed ${
          isBot 
            ? 'bg-bg-overlay border border-border-default text-white rounded-tl-none' 
            : 'bg-white text-black rounded-tr-none'
        }`}>
          <div className="prose prose-sm prose-invert max-w-none">
            <Markdown>{message.content}</Markdown>
          </div>
        </div>
        
        {message.action && (
          <div className="mt-2 bg-bg-base border border-border-default rounded-md p-3 w-full max-w-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="font-display text-[10px] text-text-muted uppercase tracking-wider flex items-center gap-1">
                <ShieldAlert className="w-3 h-3" /> Recommended Action
              </span>
              <span className="font-mono text-[10px] text-text-secondary">{message.action.target}</span>
            </div>
            
            <button 
              onClick={handleAction}
              disabled={actionTaken}
              className={`w-full py-2 rounded text-xs font-medium transition-colors flex items-center justify-center gap-2 ${
                actionTaken 
                  ? 'bg-bg-overlay border border-border-strong text-text-muted cursor-not-allowed' 
                  : 'bg-white text-black hover:bg-interactive-hover'
              }`}
            >
              {actionTaken ? (
                <><CheckCircle className="w-4 h-4" /> Action Executed</>
              ) : (
                message.action.label
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
