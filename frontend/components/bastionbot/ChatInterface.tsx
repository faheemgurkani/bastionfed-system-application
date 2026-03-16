'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';
import { Bot, User, ShieldAlert, FileText, Search, Settings } from 'lucide-react';
import { GoogleGenAI } from '@google/genai';

export function ChatInterface() {
  const [messages, setMessages] = useState([
    {
      id: '1',
      role: 'assistant',
      content: 'Hello, Analyst. I am BastionBot, your SOC copilot. I have analyzed the latest FL aggregation round and identified 3 potential anomalies. How can I assist you today?',
      timestamp: new Date().toISOString(),
    },
    {
      id: '2',
      role: 'user',
      content: 'Show me the details for the anomaly on the MRI scanner in Radiology Wing B.',
      timestamp: new Date().toISOString(),
    },
    {
      id: '3',
      role: 'assistant',
      content: 'Certainly. The MRI scanner (IP: 10.4.2.15) exhibited a 42% deviation in its local model updates during Round 47. Specifically, the gradients associated with network communication patterns spiked abnormally. This signature is consistent with a potential data exfiltration attempt or a compromised node trying to poison the global model. I recommend immediate isolation.',
      timestamp: new Date().toISOString(),
      action: {
        type: 'QUARANTINE',
        target: '10.4.2.15',
        label: 'Isolate Device'
      }
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = useCallback(async (content: string) => {
    const newMessage = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    
    setMessages(prev => [...prev, newMessage]);
    setIsLoading(true);
    
    try {
      const ai = new GoogleGenAI({ apiKey: process.env.NEXT_PUBLIC_GEMINI_API_KEY as string });
      const chat = ai.chats.create({
        model: "gemini-3.1-pro-preview",
        config: {
          systemInstruction: "You are BastionBot, a Blue Team cybersecurity SOC copilot for an IoMT hospital environment. Provide concise, technical, and actionable responses. Use markdown for formatting.",
        },
      });

      // Replay history
      for (const msg of messages) {
        if (msg.role === 'user') {
          await chat.sendMessage({ message: msg.content });
        } else {
          // We can't easily inject assistant messages into the chat history with this SDK version,
          // so we'll just send the latest message for now, or we could build a prompt string.
          // For simplicity, we'll just send the new message.
        }
      }

      const response = await chat.sendMessage({ message: content });
      
      const botResponse = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.text || 'I could not process that request.',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, botResponse]);
    } catch (error) {
      console.error('Error calling Gemini API:', error);
      const errorResponse = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Error connecting to BastionBot AI service. Please check your API key and network connection.',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorResponse]);
    } finally {
      setIsLoading(false);
    }
  }, [messages]);

  const quickActions = [
    { icon: <ShieldAlert className="w-4 h-4" />, label: 'Analyze latest alerts' },
    { icon: <FileText className="w-4 h-4" />, label: 'Generate shift report' },
    { icon: <Search className="w-4 h-4" />, label: 'Search IoCs' },
    { icon: <Settings className="w-4 h-4" />, label: 'Check FL health' },
  ];

  return (
    <div className="flex flex-col h-full bg-bg-surface border border-border-default rounded-lg overflow-hidden">
      <div className="p-4 border-b border-border-default bg-bg-base flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center text-black">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-medium text-white">BastionBot</h2>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-severity-low"></span>
              <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider">Online & Ready</span>
            </div>
          </div>
        </div>
        <button className="text-text-muted hover:text-white transition-colors p-2">
          <Settings className="w-4 h-4" />
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto p-6 space-y-6 no-scrollbar">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>
      
      <div className="p-4 border-t border-border-default bg-bg-base flex flex-col gap-4">
        <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
          {quickActions.map((action, i) => (
            <button 
              key={i}
              onClick={() => handleSendMessage(action.label)}
              disabled={isLoading}
              className="flex items-center gap-2 px-3 py-1.5 border border-border-default rounded-full text-xs text-text-secondary hover:text-white hover:border-white transition-colors whitespace-nowrap bg-bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {action.icon} {action.label}
            </button>
          ))}
        </div>
        <ChatInput onSend={handleSendMessage} isLoading={isLoading} />
      </div>
    </div>
  );
}
