import { mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { performance } from "node:perf_hooks";
import { createRequire } from "node:module";
import { URL } from "node:url";

const require = createRequire(import.meta.url);

function parseArgs(argv) {
  const args = {
    login: process.env.LESSON_PERF_LOGIN || "",
    maxFcpMs: Number(process.env.LESSON_PERF_MAX_FCP_MS || 1500),
    maxInpMs: Number(process.env.LESSON_PERF_MAX_INP_MS || 200),
    maxLcpMs: Number(process.env.LESSON_PERF_MAX_LCP_MS || 2500),
    maxShellMs: Number(process.env.LESSON_PERF_MAX_SHELL_MS || 1000),
    maxTransferBytes: Number(process.env.LESSON_PERF_MAX_TRANSFER_BYTES || 1500000),
    maxTtfbMs: Number(process.env.LESSON_PERF_MAX_TTFB_MS || 300),
    outDir: "output/playwright",
    password: process.env.LESSON_PERF_PASSWORD || "",
    requireShell: process.env.LESSON_PERF_REQUIRE_SHELL === "1",
    timeoutMs: 15000,
    url: process.env.LESSON_PERF_URL || "http://127.0.0.1:5173/learn/1/2",
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--") continue;
    if (arg === "--url") args.url = argv[++index];
    else if (arg === "--out-dir") args.outDir = argv[++index];
    else if (arg === "--timeout-ms") args.timeoutMs = Number(argv[++index]);
    else if (arg === "--login") args.login = argv[++index];
    else if (arg === "--password") args.password = argv[++index];
    else if (arg === "--max-fcp-ms") args.maxFcpMs = Number(argv[++index]);
    else if (arg === "--max-inp-ms") args.maxInpMs = Number(argv[++index]);
    else if (arg === "--max-lcp-ms") args.maxLcpMs = Number(argv[++index]);
    else if (arg === "--max-shell-ms") args.maxShellMs = Number(argv[++index]);
    else if (arg === "--max-transfer-bytes") args.maxTransferBytes = Number(argv[++index]);
    else if (arg === "--max-ttfb-ms") args.maxTtfbMs = Number(argv[++index]);
    else if (arg === "--require-shell") args.requireShell = true;
    else if (arg === "--help" || arg === "-h") {
      console.log([
        "Usage: pnpm run perf:lesson:browser -- --url http://127.0.0.1:5173/learn/1/2",
        "",
        "Useful strict lesson shell run:",
        "LESSON_PERF_LOGIN=... LESSON_PERF_PASSWORD=... pnpm run perf:lesson:browser -- --require-shell",
      ].join("\n"));
      process.exit(0);
    }
  }
  return args;
}

function originFor(url) {
  const parsed = new URL(url);
  return `${parsed.protocol}//${parsed.host}`;
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch (_error) {
    try {
      const resolved = require.resolve("playwright", { paths: [process.cwd()] });
      return await import(resolved);
    } catch (error) {
      throw new Error(
        [
          "Playwright is required for browser perf smoke.",
          "Install it for the scripts workspace: pnpm --filter @workspace/scripts add -D playwright",
          "Then run: pnpm run perf:lesson:browser -- --url http://127.0.0.1:5173/learn/1/2",
          `Original resolver error: ${error.message}`,
        ].join("\n"),
      );
    }
  }
}

function summarizeResources(resources) {
  const byType = {};
  for (const resource of resources) {
    byType[resource.initiatorType] = (byType[resource.initiatorType] || 0) + 1;
  }
  const transferSize = resources.reduce((total, item) => total + (item.transferSize || 0), 0);
  const encodedBodySize = resources.reduce((total, item) => total + (item.encodedBodySize || 0), 0);
  const scripts = resources
    .filter((item) => item.initiatorType === "script")
    .map((item) => ({
      name: item.name.split("/").pop(),
      duration_ms: Math.round(item.duration),
      transfer_size: item.transferSize || 0,
      encoded_body_size: item.encodedBodySize || 0,
    }))
    .sort((left, right) => right.encoded_body_size - left.encoded_body_size)
    .slice(0, 8);
  return {
    count: resources.length,
    by_type: byType,
    transfer_size: transferSize,
    encoded_body_size: encodedBodySize,
    largest_scripts: scripts,
  };
}

function summarizeResponseHeaders(responses) {
  const pick = (response) => ({
    url: response.url().replace(/\?.*$/, "").split("/").slice(-2).join("/"),
    status: response.status(),
    cache_control: response.headers()["cache-control"] || null,
  });
  return {
    documents: responses
      .filter((response) => response.request().resourceType() === "document")
      .map(pick)
      .slice(0, 3),
    scripts: responses
      .filter((response) => response.request().resourceType() === "script")
      .map(pick)
      .filter((item) => item.cache_control)
      .slice(0, 8),
    fetches: responses
      .filter((response) => response.request().resourceType() === "fetch")
      .map(pick)
      .filter((item) => item.url.includes("api/") || item.cache_control)
      .slice(0, 8),
  };
}

function checkThresholds(report, args) {
  const checks = [];
  const addCheck = (name, actual, limit, ok, severity = "fail") => {
    checks.push({ name, actual, limit, ok, severity });
  };
  addCheck("ttfb_ms", report.navigation.ttfb_ms, args.maxTtfbMs, report.navigation.ttfb_ms <= args.maxTtfbMs);
  if (report.paint.first_contentful_paint_ms !== null) {
    addCheck(
      "first_contentful_paint_ms",
      report.paint.first_contentful_paint_ms,
      args.maxFcpMs,
      report.paint.first_contentful_paint_ms <= args.maxFcpMs,
    );
  }
  if (report.paint.largest_contentful_paint_ms !== null) {
    addCheck(
      "largest_contentful_paint_ms",
      report.paint.largest_contentful_paint_ms,
      args.maxLcpMs,
      report.paint.largest_contentful_paint_ms <= args.maxLcpMs,
    );
  }
  if (report.interaction.interaction_to_next_paint_ms !== null) {
    addCheck(
      "interaction_to_next_paint_ms",
      report.interaction.interaction_to_next_paint_ms,
      args.maxInpMs,
      report.interaction.interaction_to_next_paint_ms <= args.maxInpMs,
    );
  }
  addCheck(
    "resource_transfer_size",
    report.resources.transfer_size,
    args.maxTransferBytes,
    report.resources.transfer_size <= args.maxTransferBytes,
    report.authenticated ? "fail" : "warn",
  );
  if (args.requireShell || report.authenticated) {
    addCheck("lesson_shell_visible", report.shell_status, "visible", report.shell_status === "visible");
    addCheck(
      "shell_visible_after_domcontentloaded_ms",
      report.shell_visible_after_domcontentloaded_ms,
      args.maxShellMs,
      report.shell_visible_after_domcontentloaded_ms !== null
        && report.shell_visible_after_domcontentloaded_ms <= args.maxShellMs,
    );
  }
  const failed = checks.filter((check) => !check.ok && check.severity === "fail");
  const warnings = checks.filter((check) => !check.ok && check.severity === "warn");
  return {
    status: failed.length ? "fail" : warnings.length ? "warn" : "pass",
    checks,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const { chromium } = await loadPlaywright();
  const workspaceRoot = process.env.INIT_CWD || resolve(process.cwd(), "..");
  const outDir = resolve(workspaceRoot, args.outDir);
  mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    reducedMotion: "reduce",
  });
  if (args.login && args.password) {
    const loginResponse = await context.request.post(`${originFor(args.url)}/api/auth/login`, {
      data: { login: args.login, password: args.password },
    });
    if (!loginResponse.ok()) {
      throw new Error(`Perf login failed: ${loginResponse.status()} ${await loginResponse.text()}`);
    }
    const session = await loginResponse.json();
    await context.addInitScript((authSession) => {
      window.localStorage.setItem("intellect_auth_session", JSON.stringify(authSession));
    }, session);
  }
  await context.addInitScript(() => {
    window.__lessonPerfVitals = {
      interactions: [],
      largestContentfulPaint: null,
    };
    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          window.__lessonPerfVitals.largestContentfulPaint = {
            startTime: entry.startTime,
            size: entry.size || 0,
            element: entry.element?.tagName || null,
          };
        }
      }).observe({ type: "largest-contentful-paint", buffered: true });
    } catch {
      // LCP is unavailable in some browser contexts.
    }
    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.interactionId) continue;
          window.__lessonPerfVitals.interactions.push({
            duration: entry.duration,
            interactionId: entry.interactionId,
            name: entry.name,
            startTime: entry.startTime,
          });
        }
      }).observe({ type: "event", buffered: true, durationThreshold: 0 });
    } catch {
      // Event Timing / INP is unavailable in some browser contexts.
    }
  });
  const page = await context.newPage();
  const started = performance.now();
  const errors = [];
  const responses = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("response", (response) => {
    responses.push(response);
  });

  let domcontentloadedMs = null;
  let shellVisibleMs = null;
  let shellStatus = "missing";
  try {
    await page.goto(args.url, { waitUntil: "domcontentloaded", timeout: args.timeoutMs });
    domcontentloadedMs = Math.round(performance.now() - started);
    const shellStarted = performance.now();
    const shell = page.getByTestId("lesson-step-viewport");
    await shell.waitFor({ state: "visible", timeout: args.timeoutMs });
    shellVisibleMs = Math.round(performance.now() - shellStarted);
    shellStatus = "visible";
    const box = await shell.boundingBox();
    if (box) {
      await page.mouse.click(box.x + Math.min(24, box.width / 2), box.y + Math.min(24, box.height / 2));
    }
  } catch (error) {
    shellStatus = `missing: ${error.message}`;
  }
  await page.waitForLoadState("networkidle", { timeout: args.timeoutMs }).catch(() => undefined);

  const metrics = await page.evaluate(() => {
    const navigation = performance.getEntriesByType("navigation")[0]?.toJSON?.() || null;
    const paintEntries = performance.getEntriesByType("paint").map((entry) => entry.toJSON());
    const resources = performance.getEntriesByType("resource").map((entry) => entry.toJSON());
    const viewport = document.querySelector('[data-testid="lesson-step-viewport"]');
    const progressbar = document.querySelector('[role="progressbar"]');
    const bodyText = document.body?.innerText?.slice(0, 800) || "";
    const vitals = window.__lessonPerfVitals || {};
    const interactionDurations = (vitals.interactions || []).map((entry) => entry.duration || 0);
    return {
      current_url: window.location.href,
      title: document.title,
      navigation,
      paints: paintEntries,
      resources,
      vitals: {
        largest_contentful_paint: vitals.largestContentfulPaint || null,
        interaction_to_next_paint: interactionDurations.length ? Math.max(...interactionDurations) : null,
        interactions: vitals.interactions || [],
      },
      body_preview: bodyText,
      shell: viewport
        ? {
            text_length: viewport.textContent?.trim().length || 0,
            rect: viewport.getBoundingClientRect().toJSON(),
          }
        : null,
      progressbar: progressbar
        ? {
            value: progressbar.getAttribute("aria-valuenow"),
            max: progressbar.getAttribute("aria-valuemax"),
          }
        : null,
    };
  });

  const nav = metrics.navigation || {};
  const firstPaint = metrics.paints.find((paint) => paint.name === "first-paint");
  const contentfulPaint = metrics.paints.find((paint) => paint.name === "first-contentful-paint");
  const report = {
    url: args.url,
    current_url: metrics.current_url,
    title: metrics.title,
    measured_at: new Date().toISOString(),
    authenticated: Boolean(args.login && args.password),
    shell_status: shellStatus,
    domcontentloaded_wall_ms: domcontentloadedMs,
    shell_visible_after_domcontentloaded_ms: shellVisibleMs,
    navigation: {
      ttfb_ms: Math.round((nav.responseStart || 0) - (nav.requestStart || 0)),
      dom_content_loaded_ms: Math.round(nav.domContentLoadedEventEnd || 0),
      load_event_ms: Math.round(nav.loadEventEnd || 0),
      transfer_size: nav.transferSize || 0,
      encoded_body_size: nav.encodedBodySize || 0,
    },
    paint: {
      first_paint_ms: firstPaint ? Math.round(firstPaint.startTime) : null,
      first_contentful_paint_ms: contentfulPaint ? Math.round(contentfulPaint.startTime) : null,
      largest_contentful_paint_ms: metrics.vitals.largest_contentful_paint
        ? Math.round(metrics.vitals.largest_contentful_paint.startTime)
        : null,
      largest_contentful_paint_element: metrics.vitals.largest_contentful_paint?.element || null,
    },
    interaction: {
      interaction_to_next_paint_ms: metrics.vitals.interaction_to_next_paint === null
        ? null
        : Math.round(metrics.vitals.interaction_to_next_paint),
      observed_events: metrics.vitals.interactions.slice(0, 10),
    },
    shell: metrics.shell,
    body_preview: metrics.body_preview,
    progressbar: metrics.progressbar,
    resources: summarizeResources(metrics.resources || []),
    cache_headers: summarizeResponseHeaders(responses),
    console_errors: errors.slice(0, 10),
  };
  report.budget = {
    max_ttfb_ms: args.maxTtfbMs,
    max_fcp_ms: args.maxFcpMs,
    max_lcp_ms: args.maxLcpMs,
    max_inp_ms: args.maxInpMs,
    max_shell_ms: args.maxShellMs,
    max_transfer_bytes: args.maxTransferBytes,
    require_shell: args.requireShell,
  };
  report.result = checkThresholds(report, args);

  const outputPath = join(outDir, "lesson-perf-smoke.json");
  writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`);
  await page.screenshot({ path: join(outDir, "lesson-perf-smoke.png"), fullPage: false });
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
  console.log(`Lesson perf smoke written: ${outputPath}`);
  if (report.result.status === "fail") {
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
