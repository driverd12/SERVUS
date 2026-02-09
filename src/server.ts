import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { CallToolRequestSchema, ListToolsRequestSchema, Tool } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";
import { Storage } from "./storage.js";
import { appendMemory, memoryAppendSchema, memorySearchSchema, searchMemory } from "./tools/memory.js";
import {
  appendTranscript,
  summarizeTranscript,
  transcriptAppendSchema,
  transcriptSummarizeSchema,
} from "./tools/transcript.js";
import { adrCreateSchema, createAdr } from "./tools/adr.js";
import { consultSchema, consultOpenAI, consultGemini } from "./tools/consult.js";
import { whoKnows, whoKnowsSchema } from "./tools/who_knows.js";
import { startStdioTransport } from "./transports/stdio.js";
import { startHttpTransport } from "./transports/http.js";
import { truncate } from "./utils.js";

const storage = new Storage("./data/hub.sqlite");
storage.init();

const server = new Server(
  {
    name: "mcp-playground-hub",
    version: "0.1.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

type ToolEntry = {
  schema: z.ZodTypeAny;
  tool: Tool;
  handler: (input: any) => Promise<unknown> | unknown;
};

const toolRegistry = new Map<string, ToolEntry>();

function registerTool(name: string, description: string, schema: z.ZodTypeAny, handler: ToolEntry["handler"]) {
  const tool: Tool = {
    name,
    description,
    inputSchema: zodToJsonSchema(schema, { name }) as Tool["inputSchema"],
  };
  toolRegistry.set(name, { schema, tool, handler });
}

registerTool("memory.append", "Append a memory note.", memoryAppendSchema, (input) =>
  appendMemory(storage, input)
);

registerTool("memory.search", "Search memory notes.", memorySearchSchema, (input) =>
  searchMemory(storage, input)
);

registerTool("transcript.append", "Append a transcript entry.", transcriptAppendSchema, (input) =>
  appendTranscript(storage, input)
);

registerTool(
  "transcript.summarize",
  "Summarize transcripts for a session and store as a memory note.",
  transcriptSummarizeSchema,
  (input) => summarizeTranscript(storage, input)
);

registerTool("adr.create", "Create an ADR file using scripts/new_adr.py.", adrCreateSchema, (input) =>
  createAdr(input)
);

registerTool("who_knows", "Search memory and optionally consult providers.", whoKnowsSchema, (input) =>
  whoKnows(storage, input)
);

registerTool("consult.openai", "Consult OpenAI for an answer.", consultSchema, (input) =>
  consultOpenAI(input)
);

registerTool("consult.gemini", "Consult Gemini for an answer.", consultSchema, (input) =>
  consultGemini(input)
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: Array.from(toolRegistry.values()).map((entry) => entry.tool),
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const entry = toolRegistry.get(name);
  if (!entry) {
    return {
      content: [{ type: "text", text: `Unknown tool: ${name}` }],
      isError: true,
    };
  }
  try {
    const parsed = entry.schema.parse(args ?? {});
    const result = await entry.handler(parsed);
    return {
      content: [{ type: "text", text: JSON.stringify(result) }],
    };
  } catch (error) {
    const message = truncate(error instanceof Error ? error.message : String(error));
    return {
      content: [{ type: "text", text: message }],
      isError: true,
    };
  }
});

async function main() {
  const args = process.argv.slice(2);
  const httpEnabled = args.includes("--http") || process.env.MCP_HTTP === "1";

  if (httpEnabled) {
    const port = Number(getArgValue(args, "--http-port") ?? process.env.MCP_HTTP_PORT ?? 8787);
    const host = getArgValue(args, "--http-host") ?? process.env.MCP_HTTP_HOST ?? "127.0.0.1";
    const allowedOriginsEnv =
      process.env.MCP_HTTP_ALLOWED_ORIGINS ?? "http://localhost,http://127.0.0.1";
    const allowedOrigins = allowedOriginsEnv.split(",").map((origin) => origin.trim()).filter(Boolean);

    await startHttpTransport(server, {
      port,
      host,
      allowedOrigins,
      bearerToken: process.env.MCP_HTTP_BEARER_TOKEN ?? null,
    });
  } else {
    await startStdioTransport(server);
  }
}

function getArgValue(args: string[], flag: string): string | undefined {
  const index = args.indexOf(flag);
  if (index === -1) {
    return undefined;
  }
  return args[index + 1];
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
