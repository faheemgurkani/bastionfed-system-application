import { NextResponse } from 'next/server';
import { MOCK_FL_CLIENTS } from '@/lib/mock-data';
import type { FLClient } from '@/lib/types';

export const dynamic = 'force-dynamic';

/** Emit mock FL client updates every 4 seconds over SSE to simulate live participation/round changes. */
const SSE_EMIT_INTERVAL_MS = 4000;

export async function GET(request: Request) {
  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();
      const clients = MOCK_FL_CLIENTS.map((c) => ({ ...c }));

      const interval = setInterval(() => {
        const idx = Math.floor(Math.random() * clients.length);
        const client = clients[idx]!;
        const update: Partial<FLClient> = { id: client.id };

        switch (Math.floor(Math.random() * 4)) {
          case 0:
            update.participationPct = Math.min(100, Math.max(0, client.participationPct + (Math.random() > 0.5 ? 1 : -1) * Math.floor(Math.random() * 3)));
            break;
          case 1:
            update.lastRound = client.lastRound + (client.status !== 'OFFLINE' ? 1 : 0);
            break;
          case 2:
            if (client.status === 'OFFLINE' && Math.random() > 0.7) {
              update.status = 'ACTIVE';
              update.participationPct = 85 + Math.floor(Math.random() * 15);
              update.lastRound = clients.filter(c => c.status !== 'OFFLINE').reduce((max, c) => Math.max(max, c.lastRound), 0);
            } else if (client.status === 'ACTIVE' && Math.random() > 0.9) {
              update.status = 'DEGRADED';
              update.participationPct = Math.max(70, client.participationPct - Math.floor(Math.random() * 15));
            }
            break;
          case 3:
            if (client.status === 'DEGRADED' && Math.random() > 0.8) {
              update.status = 'ACTIVE';
              update.participationPct = Math.min(100, client.participationPct + Math.floor(Math.random() * 20));
            }
            break;
        }

        if (Object.keys(update).length > 1) {
          Object.assign(client, update);
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(update)}\n\n`));
        }
      }, SSE_EMIT_INTERVAL_MS);

      request.signal.addEventListener('abort', () => {
        clearInterval(interval);
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  });
}
