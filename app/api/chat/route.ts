import { NextResponse } from "next/server";

export const runtime = "nodejs";

type Msg = { role: "system" | "user" | "assistant"; content: string };

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const messages: Msg[] = body?.messages ?? [];
    const model: string | undefined = body?.model;

    if (!Array.isArray(messages) || messages.length === 0) {
      return NextResponse.json({ error: "messages[] is required" }, { status: 400 });
    }

    // Mode A: Azure AI Foundry (services.ai.azure.com)
    // Use when you pass model like: "foundry:DeepSeek-R1-0528"
    if (model && model.startsWith("foundry:")) {
      const foundryModel = model.replace("foundry:", "").trim();
      const endpointRaw = process.env.AZURE_AI_FOUNDRY_ENDPOINT || "";
      const endpoint = endpointRaw
        .replace(/\/models\/?$/i, "")
        .replace(/\/+$/, "");
      const key = process.env.AZURE_AI_FOUNDRY_KEY || "";

      if (!endpoint || !key) {
        return NextResponse.json(
          { error: "Missing AZURE_AI_FOUNDRY_ENDPOINT or AZURE_AI_FOUNDRY_KEY" },
          { status: 500 }
        );
      }

      const res = await fetch(
        `${endpoint}/models/chat/completions?api-version=2024-05-01-preview`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "api-key": key,
          },
          body: JSON.stringify({
            model: foundryModel,
            messages,
            max_tokens: body?.max_tokens ?? 900,
            temperature: body?.temperature ?? 0.3,
          }),
        }
      );

      const data = await res.json().catch(() => ({}));
      return NextResponse.json(data, { status: res.status });
    }

    // Mode B: Azure OpenAI deployment (cognitiveservices.azure.com)
    const azEndpoint = process.env.AZURE_OPENAI_ENDPOINT || "";
    const azKey = process.env.AZURE_OPENAI_KEY || "";
    const apiVersion = process.env.AZURE_OPENAI_API_VERSION || "2025-01-01-preview";
    const deployment = process.env.AZURE_OPENAI_DEPLOYMENT || "model-router";

    if (!azEndpoint || !azKey) {
      return NextResponse.json(
        { error: "Missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_KEY" },
        { status: 500 }
      );
    }

    const res = await fetch(
      `${azEndpoint}/openai/deployments/${deployment}/chat/completions?api-version=${apiVersion}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "api-key": azKey,
        },
        body: JSON.stringify({
          messages,
          max_tokens: body?.max_tokens ?? 900,
          temperature: body?.temperature ?? 0.3,
        }),
      }
    );

    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? "Server error" }, { status: 500 });
  }
}