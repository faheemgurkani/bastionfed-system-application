import { NextResponse } from "next/server";

const backendBase =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
    /\/$/,
    "",
  );

export async function GET() {
  try {
    const r = await fetch(`${backendBase}/health`, { cache: "no-store" });
    if (!r.ok) {
      return NextResponse.json({ demo_mode: false });
    }
    const data = (await r.json()) as { demo_mode?: unknown };
    return NextResponse.json({ demo_mode: Boolean(data.demo_mode) });
  } catch {
    return NextResponse.json({ demo_mode: false });
  }
}
