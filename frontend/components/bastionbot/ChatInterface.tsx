'use client';

import { useEffect, useRef, useState } from 'react';
import type { User } from 'firebase/auth';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';
import { ConversationSidebar } from './ConversationSidebar';
import { ApiError, apiFetchJson, isAbortError } from '@/lib/api';
import type { BastionBotChatResponse, BotConversationHistoryResponse, BotMessage, ConversationSummary } from '@/lib/types';
import { Bot, Loader2, Sparkles } from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';

export function ChatInterface() {
  const { user, isGuest } = useAuth();
  const signedInUser = !isGuest ? user : null;
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<BotMessage[]>([]);
  const [sidebarLoading, setSidebarLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const quickActions = [
    'Explain the Alerts workflow.',
    'How do I verify the audit chain?',
    'Summarize the current incident workflow.',
    'How does FL Health work in BastionFed?',
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  function storageKey(uid: string): string {
    return `bastionbot:active:${uid}`;
  }

  async function getBastionBotHeaders(currentUser: User): Promise<Record<string, string>> {
    const token = await currentUser.getIdToken();
    return {
      Authorization: `Bearer ${token}`,
      'X-BastionFed-UID': currentUser.uid,
    };
  }

  async function loadConversation(conversationId: string, presetHeaders?: Record<string, string>, signal?: AbortSignal) {
    if (!signedInUser) return;
    const currentUser: User = signedInUser;
    setHistoryLoading(true);
    try {
      const headers = presetHeaders ?? await getBastionBotHeaders(currentUser);
      const requestInit = signal ? { headers, signal } : { headers };
      const data = await apiFetchJson<BotConversationHistoryResponse>(
        `/api/bastionbot/conversations/${conversationId}`,
        requestInit,
      );
      setMessages(data.messages);
    } catch (error) {
      if (isAbortError(error)) return;
      setError(error instanceof ApiError ? error.message : 'Failed to load this conversation.');
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    if (!signedInUser) return;
    const currentUser: User = signedInUser;

    let cancelled = false;
    const ac = new AbortController();

    async function bootstrap() {
      setSidebarLoading(true);
      setError(null);
      try {
        const headers = await getBastionBotHeaders(currentUser);
        const data = await apiFetchJson<{ conversations: ConversationSummary[] }>('/api/bastionbot/conversations', {
          headers,
          signal: ac.signal,
        });
        if (cancelled) return;

        setConversations(data.conversations);
        const storedId = typeof window !== 'undefined' ? window.localStorage.getItem(storageKey(currentUser.uid)) : null;
        const nextId = storedId && data.conversations.some((conversation) => conversation.id === storedId)
          ? storedId
          : (data.conversations[0]?.id ?? null);

        setActiveConversationId(nextId);
        if (nextId) {
          await loadConversation(nextId, headers, ac.signal);
        } else {
          setMessages([]);
        }
      } catch (error) {
        if (isAbortError(error)) return;
        if (!cancelled) setError(error instanceof ApiError ? error.message : 'Failed to load BastionBot.');
      } finally {
        if (!cancelled) setSidebarLoading(false);
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [signedInUser]);

  function persistActiveConversation(conversationId: string | null) {
    if (!signedInUser || typeof window === 'undefined') return;
    if (conversationId) {
      window.localStorage.setItem(storageKey(signedInUser.uid), conversationId);
    } else {
      window.localStorage.removeItem(storageKey(signedInUser.uid));
    }
  }

  function upsertConversation(conversation: ConversationSummary) {
    setConversations((prev) => {
      const next = [conversation, ...prev.filter((item) => item.id !== conversation.id)];
      next.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
      return next;
    });
  }

  async function handleSendMessage(content: string) {
    if (!signedInUser || isLoading) return;

    const optimisticMessage: BotMessage = {
      id: `local-${Date.now()}`,
      role: 'USER',
      content,
      timestamp: new Date().toISOString(),
      sources: [],
    };

    setMessages((prev) => [...prev, optimisticMessage]);
    setError(null);
    setIsLoading(true);

    try {
      if (!signedInUser) return;
      const currentUser: User = signedInUser;
      const headers = await getBastionBotHeaders(currentUser);
      const payload: Record<string, unknown> = { message: content };
      if (activeConversationId) payload.conversationId = activeConversationId;

      const response = await apiFetchJson<BastionBotChatResponse>('/api/bastionbot/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      upsertConversation(response.conversation);
      setActiveConversationId(response.conversationId);
      persistActiveConversation(response.conversationId);
      await loadConversation(response.conversationId, headers);
    } catch (error) {
      setMessages((prev) => prev.filter((message) => message.id !== optimisticMessage.id));
      setError(error instanceof ApiError ? error.message : 'Failed to send your BastionBot question.');
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSelectConversation(conversationId: string) {
    setActiveConversationId(conversationId);
    persistActiveConversation(conversationId);
    await loadConversation(conversationId);
  }

  function handleNewConversation() {
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
    persistActiveConversation(null);
  }

  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) ?? null;

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row bg-bg-surface border border-border-default rounded-lg overflow-hidden">
      <ConversationSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        loading={sidebarLoading}
        collapsed={sidebarCollapsed}
        onNewConversation={handleNewConversation}
        onSelectConversation={handleSelectConversation}
        onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
      />

      <div className="flex min-w-0 flex-1 flex-col min-h-[620px]">
        <div className="flex items-center justify-between gap-3 border-b border-border-default bg-bg-base p-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center text-black">
              <Bot className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h2 className="truncate text-sm font-medium text-white">
                {activeConversation?.title ?? 'New BastionBot conversation'}
              </h2>
              <div className="flex flex-wrap items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-[10px] font-mono text-text-muted uppercase tracking-wider">
                  Ask mode · grounded, read-only
                </span>
              </div>
            </div>
          </div>

          <div className="shrink-0 text-[10px] font-mono uppercase tracking-wider text-text-muted">
            {activeConversation ? `${activeConversation.messageCount} messages` : 'Ready for your first question'}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 sm:p-5 lg:p-6 space-y-5 no-scrollbar">
          {error && (
            <div className="rounded-md border border-severity-high/50 bg-bg-base px-4 py-3 text-sm text-severity-high">
              {error}
            </div>
          )}

          {!historyLoading && messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center px-6">
              <div className="w-12 h-12 rounded-full bg-bg-overlay border border-border-default flex items-center justify-center mb-4">
                <Bot className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-lg font-medium text-white">Ask BastionBot about BastionFed</h3>
              <p className="mt-2 max-w-xl text-sm text-text-secondary">
                BastionBot can explain screens, analyst workflows, backend endpoints, and live platform state. It is grounded in the current BastionFed docs, code map, and runtime data.
              </p>
            </div>
          )}

          {historyLoading ? (
            <div className="h-full flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-text-muted" />
            </div>
          ) : (
            messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))
          )}
          <div ref={messagesEndRef} className="h-1" />
        </div>

        <div className="p-4 border-t border-border-default bg-bg-base flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action) => (
              <button
                key={action}
                onClick={() => void handleSendMessage(action)}
                disabled={isLoading}
                className="flex max-w-full items-center gap-2 rounded-full border border-border-default bg-bg-surface px-3 py-1.5 text-left text-xs text-text-secondary transition-colors hover:border-white hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span className="truncate">{action}</span>
              </button>
            ))}
          </div>
          <ChatInput onSend={(message) => void handleSendMessage(message)} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
}
