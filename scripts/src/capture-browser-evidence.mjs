import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const root = process.env.INIT_CWD || process.cwd();
const evidenceDir = join(root, "evidence", "factory");
const receiptPath = join(evidenceDir, "browser-receipt.json");
const apiSmokePath = join(evidenceDir, "api-smoke.txt");

mkdirSync(evidenceDir, { recursive: true });

const url = process.env.HARNESS_VISUAL_URL || "";
const receipt = {
  timestamp: new Date().toISOString(),
  status: url ? "pending-browser-tool-run" : "skipped-no-HARNESS_VISUAL_URL",
  url,
  note: url
    ? "Run the Codex browser tool against this URL and save desktop/mobile screenshots to evidence/factory."
    : "Set HARNESS_VISUAL_URL to make visual evidence mandatory for UI/design lanes.",
  expectedScreenshots: ["evidence/factory/desktop.png", "evidence/factory/mobile.png"],
};

writeFileSync(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`);
writeFileSync(apiSmokePath, `browser evidence: ${receipt.status}\n`);
console.log(`Browser evidence receipt written: ${receiptPath}`);
