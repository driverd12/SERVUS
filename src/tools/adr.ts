import { z } from "zod";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { logEvent, truncate } from "../utils.js";

export const adrCreateSchema = z.object({
  title: z.string().min(1),
  status: z.string().min(1),
});

export function createAdr(input: z.infer<typeof adrCreateSchema>) {
  const args = ["scripts/new_adr.py", "--title", input.title, "--status", input.status];
  const result = spawnSync("python3", args, {
    encoding: "utf8",
    cwd: process.cwd(),
    maxBuffer: 1024 * 1024,
  });

  const stderr = truncate(result.stderr ?? "");
  const stdout = (result.stdout ?? "").trim();
  const ok = result.status === 0;
  logEvent("adr.create", { ok, status: result.status, stdout: truncate(stdout) });

  let pathValue: string | null = null;
  if (stdout) {
    const lines = stdout.split(/\r?\n/).filter(Boolean);
    pathValue = lines[lines.length - 1] ?? null;
  }

  return {
    path: pathValue ? path.resolve(pathValue) : null,
    ok,
    stderr_trunc: stderr || undefined,
  };
}
