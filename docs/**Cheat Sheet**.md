**Cheat Sheet**

**Build + Run (recommended STDIO)**
```bash
cd /Users/dan.driver/Cursor_projects/python/SERVUS
nvm use 22
npm install
npm run build
npm run start:stdio
```

**Run (HTTP mode)**
```bash
cd /Users/dan.driver/Cursor_projects/python/SERVUS
nvm use 22
npm run build
npm run start:http
```

**Env (local defaults)**
- Token and origins live in `/Users/dan.driver/Cursor_projects/python/SERVUS/.env`.
- Defaults are in `/Users/dan.driver/Cursor_projects/python/SERVUS/.env.example`.
- Required for HTTP:
  - `MCP_HTTP_BEARER_TOKEN`
  - `MCP_HTTP_ALLOWED_ORIGINS`

**Where data lives**
- SQLite: `/Users/dan.driver/Cursor_projects/python/SERVUS/data/hub.sqlite` plus `-wal` and `-shm`.

**Migration (no‑loss)**
1. Stop the server process.
2. Move `/Users/dan.driver/Cursor_projects/python/SERVUS/data/` and `/Users/dan.driver/Cursor_projects/python/SERVUS/.env` to the new machine.
3. `npm install` → `npm run build` → `npm run start:stdio` or `npm run start:http`.

**Tools**
- `memory.append`, `memory.search`
- `transcript.append`, `transcript.summarize`
- `adr.create`
- `who_knows`
- `consult.openai`, `consult.gemini`

---

**Client Setup (Generic)**
- **STDIO**: configure client to run  
  `node /Users/dan.driver/Cursor_projects/python/SERVUS/dist/server.js`
- **HTTP**: configure client to connect to  
  `http://127.0.0.1:8787`  
  and send `Authorization: Bearer <token>`  
  and an `Origin` header matching `MCP_HTTP_ALLOWED_ORIGINS`.

---

**Cursor IDE**
1. Open Settings.
2. Search for `MCP` or `Model Context Protocol`.
3. Add a server with command:  
   `node /Users/dan.driver/Cursor_projects/python/SERVUS/dist/server.js`  
4. Save and restart the MCP list if prompted.

**Codex IDE (desktop app)**
1. Open Settings.
2. Search for `MCP` or `Tools`.
3. Add a server with command:  
   `node /Users/dan.driver/Cursor_projects/python/SERVUS/dist/server.js`

**VS Code Copilot Chat**
1. Open VS Code Settings.
2. Search for `MCP`.
3. Add a server using STDIO with command:  
   `node /Users/dan.driver/Cursor_projects/python/SERVUS/dist/server.js`  
If your VS Code build doesn’t show MCP settings, it likely doesn’t support MCP yet.

**ChatGPT website**
- Not supported. The web UI does not allow configuring local MCP servers or connecting to `127.0.0.1`.

**Gemini website**
- Not supported. The web UI does not allow configuring local MCP servers or connecting to `127.0.0.1`.

If you want, tell me which client you’re using right now and I’ll give the exact UI clicks or config snippet for that version.