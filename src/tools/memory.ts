import { z } from "zod";
import { Storage } from "../storage.js";

export const memoryAppendSchema = z.object({
  text: z.string().min(1),
  tags: z.array(z.string()).optional(),
  related_paths: z.array(z.string()).optional(),
  source: z.string().optional(),
});

export const memorySearchSchema = z.object({
  query: z.string().min(1).optional(),
  tags: z.array(z.string()).optional(),
  limit: z.number().int().min(1).max(50).optional(),
});

export function appendMemory(storage: Storage, input: z.infer<typeof memoryAppendSchema>) {
  return storage.insertNote({
    text: input.text,
    tags: input.tags,
    related_paths: input.related_paths,
    source: input.source,
  });
}

export function searchMemory(storage: Storage, input: z.infer<typeof memorySearchSchema>) {
  const limit = input.limit ?? 10;
  if (!input.query && (!input.tags || input.tags.length === 0)) {
    return [];
  }
  return storage.searchNotes({
    query: input.query,
    tags: input.tags,
    limit,
  });
}
