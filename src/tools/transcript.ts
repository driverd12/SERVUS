import { z } from "zod";
import { Storage } from "../storage.js";
import { consultOpenAI, consultGemini, ProviderResult } from "./consult.js";

export const transcriptAppendSchema = z.object({
  session_id: z.string().min(1),
  source_client: z.string().min(1),
  kind: z.string().min(1),
  text: z.string().min(1),
});

export const transcriptSummarizeSchema = z.object({
  session_id: z.string().min(1),
  provider: z.enum(["openai", "gemini", "auto"]).optional(),
});

export function appendTranscript(
  storage: Storage,
  input: z.infer<typeof transcriptAppendSchema>
) {
  return storage.insertTranscript({
    session_id: input.session_id,
    source_client: input.source_client,
    kind: input.kind,
    text: input.text,
  });
}

export async function summarizeTranscript(
  storage: Storage,
  input: z.infer<typeof transcriptSummarizeSchema>
) {
  const transcripts = storage.getTranscriptsBySession(input.session_id);
  if (transcripts.length === 0) {
    return { enabled: false, reason: "no transcripts for session" };
  }

  const preferred = input.provider ?? "auto";
  const summaryPrompt = buildSummaryPrompt(transcripts.map((t) => t.text).join("\n\n"));

  let result: ProviderResult | null = null;
  let failure: ProviderResult | null = null;

  if (preferred === "openai" || preferred === "auto") {
    result = await consultOpenAI({ prompt: summaryPrompt });
    if (result.enabled && result.ok) {
      return storeSummary(storage, input.session_id, result.text ?? "");
    }
    if (result.enabled && !result.ok) {
      failure = result;
    }
  }

  if (preferred === "gemini" || preferred === "auto") {
    result = await consultGemini({ prompt: summaryPrompt });
    if (result.enabled && result.ok) {
      return storeSummary(storage, input.session_id, result.text ?? "");
    }
    if (result.enabled && !result.ok) {
      failure = result;
    }
  }

  if (failure) {
    return { enabled: true, ok: false, error: failure.error };
  }

  return { enabled: false, reason: "missing API key" };
}

function storeSummary(storage: Storage, sessionId: string, text: string) {
  const note = storage.insertNote({
    text,
    tags: ["summary", "transcript"],
    source: `transcript:${sessionId}`,
  });
  return { enabled: true, ok: true, note_id: note.id };
}

function buildSummaryPrompt(content: string) {
  return [
    "Summarize the following transcript. Be concise and factual.",
    "Include key decisions, action items, and open questions.",
    "---",
    content,
  ].join("\n");
}
