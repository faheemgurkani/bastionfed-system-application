'use client';

import Link from 'next/link';
import { Bot, ChevronDown, Link2, User } from 'lucide-react';
import Markdown from 'react-markdown';
import type { BotMessage } from '@/lib/types';

interface MessageBubbleProps {
  message: BotMessage;
}

interface NavigationAction {
  href: string;
  label: string;
}

interface LinkableEntity {
  href: string;
  id: string;
}

function actionForSource(path: string, label: string): NavigationAction | null {
  if (path.startsWith('live://alerts/')) {
    const alertId = path.split('/').pop();
    return alertId ? { href: `/alerts?alertId=${encodeURIComponent(alertId)}`, label: `Open ${alertId}` } : null;
  }
  if (path.startsWith('live://incidents/')) {
    const incidentId = path.split('/').pop();
    return incidentId ? { href: `/incidents?incidentId=${encodeURIComponent(incidentId)}`, label: `Open ${incidentId}` } : null;
  }
  if (path === 'live://dashboard/kpis') return { href: '/dashboard', label: 'Open dashboard' };
  if (path === 'live://audit/verify' || path.includes('/audit')) return { href: '/audit', label: 'Open audit' };
  if (path === 'live://fl/status' || path.includes('/fl/')) return { href: '/fl-health', label: 'Open FL Health' };
  if (path.includes('/alerts')) return { href: '/alerts', label: 'Open alerts' };
  if (path.includes('/incidents')) return { href: '/incidents', label: 'Open incidents' };
  if (path.includes('/forensics')) return { href: '/forensics', label: 'Open forensics' };
  if (path.includes('/dashboard')) return { href: '/dashboard', label: 'Open dashboard' };
  if (path.includes('/bastionbot')) return { href: '/bastionbot', label: 'Open BastionBot' };
  if (path.includes('/api/audit') || label.toLowerCase().includes('audit')) return { href: '/audit', label: 'Open audit' };
  return null;
}

function linkableEntities(message: BotMessage): LinkableEntity[] {
  const deduped = new Map<string, LinkableEntity>();
  for (const source of message.sources ?? []) {
    if (source.path.startsWith('live://alerts/')) {
      const alertId = source.path.split('/').pop();
      if (alertId) deduped.set(alertId, { id: alertId, href: `/alerts?alertId=${encodeURIComponent(alertId)}` });
    }
    if (source.path.startsWith('live://incidents/')) {
      const incidentId = source.path.split('/').pop();
      if (incidentId) deduped.set(incidentId, { id: incidentId, href: `/incidents?incidentId=${encodeURIComponent(incidentId)}` });
    }
  }
  return [...deduped.values()];
}

function linkifyBotContent(message: BotMessage): string {
  let content = message.content;
  for (const entity of linkableEntities(message)) {
    const codePattern = new RegExp("`" + entity.id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "`", "g");
    content = content.replace(codePattern, `[${entity.id}](${entity.href})`);
    const plainPattern = new RegExp(`\\b${entity.id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "g");
    content = content.replace(plainPattern, `[${entity.id}](${entity.href})`);
  }
  return content;
}

function navigationActions(message: BotMessage): NavigationAction[] {
  const deduped = new Map<string, NavigationAction>();
  for (const source of message.sources ?? []) {
    const action = actionForSource(source.path, source.label);
    if (action && !deduped.has(action.href)) {
      deduped.set(action.href, action);
    }
  }
  return [...deduped.values()];
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isBot = message.role === 'BOT';
  const actions = isBot ? navigationActions(message) : [];
  const renderedContent = isBot ? linkifyBotContent(message) : message.content;

  return (
    <div className={`flex w-full min-w-0 gap-3 sm:gap-4 ${isBot ? '' : 'flex-row-reverse'}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
        isBot ? 'bg-white text-black' : 'bg-bg-overlay border border-border-strong text-white'
      }`}>
        {isBot ? <Bot className="w-5 h-5" /> : <User className="w-5 h-5" />}
      </div>
      
      <div className={`flex min-w-0 flex-1 flex-col gap-2 ${isBot ? 'items-start' : 'items-end'}`}>
        <div className="flex max-w-full flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-text-secondary">{isBot ? 'BastionBot' : 'Analyst'}</span>
          <span className="font-mono text-[10px] text-text-muted">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
        
        <div className={`w-full max-w-full overflow-hidden rounded-lg p-3 sm:p-4 text-sm leading-relaxed ${
          isBot 
            ? 'bg-bg-overlay border border-border-default text-white rounded-tl-none' 
            : 'bg-white text-black rounded-tr-none'
        }`}>
          <div
            className={`prose prose-sm max-w-none break-words [overflow-wrap:anywhere] ${isBot ? 'prose-invert' : 'prose-neutral'}`}
          >
            <Markdown>{renderedContent}</Markdown>
          </div>

          {isBot && actions.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2 border-t border-border-default/70 pt-3">
              {actions.map((action) => (
                <Link
                  key={action.href}
                  href={action.href}
                  className="inline-flex max-w-full items-center gap-2 rounded-md border border-border-strong bg-bg-base px-3 py-2 text-xs font-medium text-white transition-colors hover:border-white hover:bg-bg-surface"
                >
                  <Link2 className="h-3.5 w-3.5" />
                  <span className="truncate">{action.label}</span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {isBot && message.sources && message.sources.length > 0 && (
          <details className="w-full max-w-full rounded-md border border-border-default bg-bg-base p-3">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-[10px] font-mono uppercase tracking-wider text-text-muted">
              <span className="flex items-center gap-2">
                <Link2 className="w-3 h-3" />
                Grounding sources
              </span>
              <ChevronDown className="h-3.5 w-3.5 transition-transform details-open:rotate-180" />
            </summary>
            <div className="mt-3 space-y-2">
              {message.sources.map((source) => (
                <div key={source.id} className="rounded-md border border-border-default bg-bg-surface px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="min-w-0 break-words text-xs font-medium text-white">{source.label}</span>
                    <span className="text-[10px] font-mono uppercase text-text-muted">{source.sourceType}</span>
                  </div>
                  <p className="mt-1 text-xs text-text-secondary">{source.excerpt}</p>
                  <p className="mt-2 break-all text-[10px] font-mono text-text-muted">{source.path}</p>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
