'use client';

import { MessageSquarePlus, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import type { ConversationSummary } from '@/lib/types';

interface ConversationSidebarProps {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  loading: boolean;
  collapsed: boolean;
  onNewConversation: () => void;
  onSelectConversation: (conversationId: string) => void;
  onToggleCollapsed: () => void;
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatCompactTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString([], { month: 'short', day: 'numeric' });
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  loading,
  collapsed,
  onNewConversation,
  onSelectConversation,
  onToggleCollapsed,
}: ConversationSidebarProps) {
  return (
    <aside
      className={`border-b lg:border-b-0 lg:border-r border-border-default bg-bg-base flex shrink-0 flex-col transition-all duration-200 ${
        collapsed ? 'w-full lg:w-[72px]' : 'w-full lg:w-[280px] xl:w-[320px]'
      }`}
    >
      <div className={`border-b border-border-default ${collapsed ? 'p-3' : 'p-4'}`}>
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'justify-between gap-2'}`}>
          {!collapsed && (
            <button
              onClick={onNewConversation}
              className="flex-1 flex items-center justify-center gap-2 rounded-md bg-white text-black px-4 py-3 text-sm font-medium hover:bg-interactive-hover transition-colors"
            >
              <MessageSquarePlus className="w-4 h-4" />
              New conversation
            </button>
          )}
          <button
            onClick={onToggleCollapsed}
            className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-transparent bg-bg-surface text-text-secondary transition-colors hover:border-border-default hover:text-white"
            title={collapsed ? 'Expand conversations' : 'Collapse conversations'}
            aria-label={collapsed ? 'Expand conversations' : 'Collapse conversations'}
          >
            {collapsed ? <PanelLeftOpen className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
          </button>
        </div>
        {collapsed && (
          <button
            onClick={onNewConversation}
            className="mt-3 flex w-full items-center justify-center rounded-md bg-white px-3 py-2 text-black transition-colors hover:bg-interactive-hover lg:hidden"
            title="New conversation"
          >
            <MessageSquarePlus className="w-4 h-4" />
          </button>
        )}
      </div>

      {collapsed ? (
        <div className="hidden lg:flex flex-1 flex-col items-center gap-2 overflow-y-auto no-scrollbar p-3">
          {conversations.map((conversation) => {
            const isActive = activeConversationId === conversation.id;
            return (
              <button
                key={conversation.id}
                onClick={() => onSelectConversation(conversation.id)}
                className={`flex min-h-[42px] w-full items-center justify-center rounded-md border px-2 text-[10px] font-mono uppercase transition-colors ${
                  isActive
                    ? 'border-white bg-bg-overlay text-white'
                    : 'border-border-default bg-bg-surface text-text-muted hover:border-border-strong hover:text-white'
                }`}
                title={conversation.title}
              >
                {formatCompactTimestamp(conversation.updatedAt)}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto no-scrollbar p-3 space-y-2">
          {loading ? (
            <div className="space-y-2">
              <div className="h-20 rounded-md bg-bg-surface animate-pulse" />
              <div className="h-20 rounded-md bg-bg-surface animate-pulse" />
            </div>
          ) : conversations.length === 0 ? (
            <div className="rounded-md border border-dashed border-border-strong bg-bg-surface p-4 text-sm text-text-muted">
              Your conversations will appear here after you start chatting with BastionBot.
            </div>
          ) : (
            conversations.map((conversation) => {
              const isActive = activeConversationId === conversation.id;
              return (
                <button
                  key={conversation.id}
                  onClick={() => onSelectConversation(conversation.id)}
                  className={`w-full text-left rounded-md border px-3 py-3 transition-colors ${
                    isActive
                      ? 'border-white bg-bg-overlay'
                      : 'border-border-default bg-bg-surface hover:border-border-strong hover:bg-bg-overlay'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-white truncate">{conversation.title}</p>
                      <p className="mt-1 line-clamp-3 break-words text-xs text-text-muted">{conversation.preview}</p>
                    </div>
                    <span className="shrink-0 text-[10px] font-mono text-text-muted uppercase">
                      {conversation.messageCount}
                    </span>
                  </div>
                  <p className="mt-2 text-[10px] font-mono text-text-muted uppercase tracking-wider">
                    {formatTimestamp(conversation.updatedAt)}
                  </p>
                </button>
              );
            })
          )}
        </div>
      )}
    </aside>
  );
}
