import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const text: string = body?.text ?? "";
    const voice: string = body?.voice ?? "alloy";

    if (!text || typeof text !== "string") {
      return NextResponse.json({ error: "text is required" }, { status: 400 });
    }

    const endpoint = process.env.AZURE_TTS_ENDPOINT || "";
    const key = process.env.AZURE_TTS_KEY || "";
    const deployment = process.env.AZURE_TTS_DEPLOYMENT || "tts-hd";
    const apiVersion = process.env.AZURE_TTS_API_VERSION || "2025-03-01-preview";

    if (!endpoint || !key) {
      return NextResponse.json(
        { error: "Missing AZURE_TTS_ENDPOINT or AZURE_TTS_KEY" },
        { status: 500 }
      );
    }

    const res = await fetch(
      `${endpoint}/openai/deployments/${deployment}/audio/speech?api-version=${apiVersion}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "api-key": key,
        },
        body: JSON.stringify({
          model: deployment,
          voice,
          input: text,
          format: "mp3",
        }),
      }
    );

    const audio = Buffer.from(await res.arrayBuffer());
    return new NextResponse(audio, {
      status: res.status,
      headers: { "Content-Type": "audio/mpeg" },
    });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? "Server error" }, { status: 500 });
  }
}