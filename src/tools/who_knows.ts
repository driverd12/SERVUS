import { z } from "zod";
import { Storage } from "../storage.js";
import { consultOpenAI, consultGemini } from "./consult.js";
import { truncate } from "../utils.js";

export const whoKnowsSchema = z.object({
  query: z.string().min(1),
  tags: z.array(z.string()).optional(),
  consult: z.boolean().optional(),
});

export async function whoKnows(storage: Storage, input: z.infer<typeof whoKnowsSchema>) {
  const matches = storage.searchNotes({
    query: input.query,
    tags: input.tags,
    limit: 10,
  });

  const providers = {
    openai: { enabled: Boolean(process.env.OPENAI_API_KEY) },
    gemini: { enabled: Boolean(process.env.GEMINI_API_KEY) },
  };

  const consultResponses: Array<Record<string, unknown>> = [];

  if (input.consult) {
    const prompt = buildConsultPrompt(input.query, matches);
    if (providers.openai.enabled) {
      const response = await consultOpenAI({ prompt });
      consultResponses.push({ provider: "openai", ...sanitizeProvider(response) });
    }
    if (providers.gemini.enabled) {
      const response = await consultGemini({ prompt });
      consultResponses.push({ provider: "gemini", ...sanitizeProvider(response) });
    }
  }

  return {
    matches,
    providers,
    consult_responses: consultResponses.length ? consultResponses : undefined,
  };
}

function buildConsultPrompt(query: string, matches: Array<{ text: string; source: string | null }>) {
  const snippets = matches
    .slice(0, 5)
    .map((match, index) => `#${index + 1} (${match.source ?? "unknown"}) ${truncate(match.text, 600)}`)
    .join("\n\n");
  return [
    "Use the following memory snippets to answer the user question.",
    "If the answer is not in the snippets, say so plainly.",
    `Question: ${query}`,
    "---",
    snippets || "(no local matches)",
  ].join("\n");
}

function sanitizeProvider(result: { enabled: boolean; ok?: boolean; text?: string; model?: string; error?: string }) {
  return {
    enabled: result.enabled,
    ok: result.ok,
    model: result.model,
    text: result.text ? truncate(result.text, 2000) : undefined,
    error: result.error ? truncate(result.error, 2000) : undefined,
  };
}
