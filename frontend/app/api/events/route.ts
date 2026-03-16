import { NextResponse } from 'next/server';
import { MOCK_ALERTS } from '@/lib/mock-data';
import { Alert } from '@/lib/types';

export const dynamic = 'force-dynamic';

/** Emit mock alert every 5 seconds over SSE. */
const SSE_EMIT_INTERVAL_MS = 5000;

export async function GET(request: Request) {
  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();
      
      const interval = setInterval(() => {
        const randomAlert = MOCK_ALERTS[Math.floor(Math.random() * MOCK_ALERTS.length)];
        const newAlert: Alert = {
          ...randomAlert,
          id: `ALT-${Math.floor(Math.random() * 10000)}`,
          timestamp: new Date().toISOString(),
        };
        
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(newAlert)}\n\n`));
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
      'Connection': 'keep-alive',
    },
  });
}
