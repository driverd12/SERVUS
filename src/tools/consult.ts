import { z } from "zod";
import { logEvent, truncate } from "../utils.js";

export const consultSchema = z.object({
  prompt: z.string().min(1),
  model: z.string().optional(),
});

export type ProviderResult = {
  enabled: boolean;
  ok?: boolean;
  model?: string;
  text?: string;
  error?: string;
};

export async function consultOpenAI(input: z.infer<typeof consultSchema>): Promise<ProviderResult> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    return { enabled: false };
  }
  const model = input.model ?? process.env.OPENAI_MODEL ?? "gpt-4.1-mini";
  try {
    const response = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        input: input.prompt,
      }),
    });
    const payload = await response.json();
    const text = extractOpenAIText(payload);
    logEvent("consult.openai", { ok: response.ok, model });
    if (!response.ok) {
      return {
        enabled: true,
        ok: false,
        model,
        error: truncate(JSON.stringify(payload)),
      };
    }
    return {
      enabled: true,
      ok: true,
      model,
      text,
    };
  } catch (error) {
    logEvent("consult.openai", { ok: false, error: String(error) });
    return {
      enabled: true,
      ok: false,
      model,
      error: truncate(String(error)),
    };
  }
}

export async function consultGemini(input: z.infer<typeof consultSchema>): Promise<ProviderResult> {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return { enabled: false };
  }
  const model = input.model ?? process.env.GEMINI_MODEL ?? "gemini-1.5-flash";
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ parts: [{ text: input.prompt }] }],
      }),
    });
    const payload = await response.json();
    const text = extractGeminiText(payload);
    logEvent("consult.gemini", { ok: response.ok, model });
    if (!response.ok) {
      return {
        enabled: true,
        ok: false,
        model,
        error: truncate(JSON.stringify(payload)),
      };
    }
    return {
      enabled: true,
      ok: true,
      model,
      text,
    };
  } catch (error) {
    logEvent("consult.gemini", { ok: false, error: String(error) });
    return {
      enabled: true,
      ok: false,
      model,
      error: truncate(String(error)),
    };
  }
}

function extractOpenAIText(payload: any): string {
  const output = payload?.output;
  if (!Array.isArray(output)) {
    return "";
  }
  for (const item of output) {
    const content = item?.content;
    if (Array.isArray(content)) {
      for (const block of content) {
        if (block?.type === "output_text" && typeof block.text === "string") {
          return block.text;
        }
      }
    }
  }
  return "";
}

function extractGeminiText(payload: any): string {
  const candidate = payload?.candidates?.[0];
  const part = candidate?.content?.parts?.[0];
  if (part && typeof part.text === "string") {
    return part.text;
  }
  return "";
}
