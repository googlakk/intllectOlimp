import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.env.INIT_CWD || join(process.cwd(), "..");
const failures = [];

const read = (path) => readFileSync(join(root, path), "utf8");
const requireFile = (path) => {
  if (!existsSync(join(root, path))) {
    failures.push(`Missing required file: ${path}`);
    return "";
  }
  return read(path);
};

const requireIncludes = (path, content, expected) => {
  if (!content.includes(expected)) {
    failures.push(`${path} must include ${JSON.stringify(expected)}`);
  }
};

const sectionFor = (content, header) => {
  const start = content.indexOf(header);
  if (start < 0) {
    return "";
  }
  const next = content.indexOf("\n[", start + header.length);
  return content.slice(start, next < 0 ? undefined : next);
};

const config = requireFile(".codex/config.toml");
const agentsGuide = requireFile("AGENTS.md");
const systemDoc = requireFile("docs/codex-agent-system.md");
const factory = requireFile("factory.yaml");

try {
  execFileSync("python3", [
    "-c",
    "import pathlib, tomllib; [tomllib.loads(p.read_text()) for p in pathlib.Path('.codex').rglob('*.toml')]",
  ], {
    cwd: root,
    stdio: ["ignore", "pipe", "pipe"],
  });
} catch (error) {
  failures.push(`Invalid TOML in .codex: ${error.message}`);
}

for (const server of ["openaiDeveloperDocs", "context7", "linear", "figma"]) {
  const header = `[mcp_servers.${server}]`;
  const section = sectionFor(config, header);
  requireIncludes(".codex/config.toml", config, header);
  requireIncludes(`.codex/config.toml ${header}`, section, "default_tools_approval_mode");
  requireIncludes(`.codex/config.toml ${header}`, section, "startup_timeout_sec");
  requireIncludes(`.codex/config.toml ${header}`, section, "tool_timeout_sec");
}

for (const server of ["openaiDeveloperDocs", "context7"]) {
  const header = `[mcp_servers.${server}]`;
  requireIncludes(`.codex/config.toml ${header}`, sectionFor(config, header), "required = true");
}

for (const server of ["supabase", "supabase_plain", "supabase_work_kylymedu_stage", "supabase_clients_clienta_app_stage", "supabase_personal_lab_dev", "stitch"]) {
  const header = `[mcp_servers.${server}]`;
  requireIncludes(`.codex/config.toml ${header}`, sectionFor(config, header), "enabled = false");
}

requireIncludes(".codex/config.toml [mcp_servers.pencil]", sectionFor(config, "[mcp_servers.pencil]"), "enabled = false");

requireIncludes(".codex/config.toml", config, "max_concurrent_threads_per_session = 6");
requireIncludes(".codex/config.toml", config, "[browser_use.default_origin_policy]");
requireIncludes("AGENTS.md", agentsGuide, "Do not auto-merge or auto-deliver");
requireIncludes("docs/codex-agent-system.md", systemDoc, "Quality Rule");
requireIncludes("factory.yaml", factory, "sandbox_mode: read-only");
requireIncludes("factory.yaml", factory, "approval_policy: on-request");
requireIncludes("factory.yaml", factory, "pnpm run check:architecture");
requireIncludes("factory.yaml", factory, "pnpm run test:run");
requireIncludes("factory.yaml", factory, "node scripts/src/capture-browser-evidence.mjs");

const agentFiles = [
  "intellect-planner.toml",
  "intellect-product.toml",
  "intellect-design.toml",
  "intellect-prompt.toml",
  "intellect-qa.toml",
  "intellect-reviewer.toml",
];

for (const file of agentFiles) {
  const path = `.codex/agents/${file}`;
  const agent = requireFile(path);
  requireIncludes(path, agent, "developer_instructions");
  requireIncludes(path, agent, "sandbox_mode");
}

let mcpList = "";
try {
  mcpList = execFileSync("codex", ["mcp", "list"], {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
} catch (error) {
  failures.push(`Unable to run codex mcp list: ${error.message}`);
}

for (const server of ["context7", "linear", "figma"]) {
  if (mcpList && !mcpList.includes(server)) {
    failures.push(`MCP server is not visible to Codex: ${server}`);
  }
}

if (mcpList && !mcpList.includes("openaiDeveloperDocs")) {
  failures.push(
    "OpenAI Developer Docs MCP is project-configured but not visible in this live Codex session; restart Codex or run codex mcp list in a fresh session to confirm.",
  );
}

for (const forbidden of [
  "supabase",
  "supabase_plain",
  "supabase_work_kylymedu_stage",
  "supabase_clients_clienta_app_stage",
  "supabase_personal_lab_dev",
  "stitch",
  "pencil",
]) {
  const line = mcpList.split("\n").find((row) => row.trim().startsWith(forbidden));
  if (line && /\senabled\s/.test(line)) {
    failures.push(`Forbidden MCP server is enabled in this project: ${forbidden}`);
  }
}

if (failures.length > 0) {
  console.error("Agent system check failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Agent system check passed.");
