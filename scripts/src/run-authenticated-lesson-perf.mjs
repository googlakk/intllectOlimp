import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { URL } from "node:url";

function readDotEnv(root) {
  const values = {};
  try {
    const text = readFileSync(resolve(root, ".env"), "utf8");
    for (const line of text.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
      const [key, ...rest] = trimmed.split("=");
      values[key.trim()] = rest.join("=").trim().replace(/^['"]|['"]$/g, "");
    }
  } catch {
    // The caller can still provide variables through process.env.
  }
  return values;
}

function parseArgs(argv) {
  const args = {
    classroomName: process.env.LESSON_PERF_CLASSROOM_NAME || "Perf 7",
    grade: Number(process.env.LESSON_PERF_GRADE || 7),
    login: process.env.LESSON_PERF_LOGIN || "perf.student.7",
    name: process.env.LESSON_PERF_STUDENT_NAME || "Perf Student 7",
    password: process.env.LESSON_PERF_PASSWORD || `Perf${randomBytes(8).toString("hex")}A1!`,
    url: process.env.LESSON_PERF_URL || "http://127.0.0.1:5173/learn/1/2",
    smokeArgs: [],
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--") continue;
    if (arg === "--url") {
      args.url = argv[index + 1];
      args.smokeArgs.push(arg, argv[++index]);
    } else if (arg === "--login") args.login = argv[++index];
    else if (arg === "--student-name") args.name = argv[++index];
    else if (arg === "--classroom-name") args.classroomName = argv[++index];
    else if (arg === "--grade") args.grade = Number(argv[++index]);
    else if (arg === "--help" || arg === "-h") {
      console.log([
        "Usage: pnpm run perf:lesson:browser:auth -- --url http://127.0.0.1:5173/learn/1/2",
        "",
        "Creates or resets a reusable perf student, changes the temporary password,",
        "then runs the strict lesson shell browser smoke. Passwords are not printed.",
      ].join("\n"));
      process.exit(0);
    } else {
      args.smokeArgs.push(arg);
    }
  }
  if (!args.smokeArgs.includes("--url")) args.smokeArgs.push("--url", args.url);
  if (!args.smokeArgs.includes("--require-shell")) args.smokeArgs.push("--require-shell");
  return args;
}

function originFor(url) {
  const parsed = new URL(url);
  return `${parsed.protocol}//${parsed.host}`;
}

function requestedTopicId(url) {
  const match = new URL(url).pathname.match(/\/learn\/\d+\/(\d+)$/);
  return match ? Number(match[1]) : null;
}

function setSmokeArg(args, name, value) {
  const index = args.smokeArgs.indexOf(name);
  if (index >= 0) args.smokeArgs[index + 1] = value;
  else args.smokeArgs.push(name, value);
  args.url = value;
}

async function requestJson(origin, path, { token, method = "GET", body } = {}) {
  const response = await fetch(`${origin}/api${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail || payload);
    throw new Error(`${method} ${path} failed: ${response.status} ${detail}`);
  }
  return payload;
}

async function login(origin, loginName, password) {
  return requestJson(origin, "/auth/login", {
    method: "POST",
    body: { login: loginName, password },
  });
}

async function canOpenLessonManifest(origin, token, topicId) {
  if (!topicId) return false;
  try {
    await requestJson(origin, `/lessons/${topicId}/manifest`, { token });
    return true;
  } catch {
    return false;
  }
}

async function lessonManifestProbe(origin, token, topicId) {
  if (!topicId) return { ok: false, detail: "missing-topic" };
  try {
    await requestJson(origin, `/lessons/${topicId}/manifest`, { token });
    return { ok: true, detail: "ok" };
  } catch (error) {
    return { ok: false, detail: String(error.message || error).slice(0, 220) };
  }
}

async function main() {
  const workspaceRoot = process.env.INIT_CWD || resolve(process.cwd(), "..");
  const envFile = readDotEnv(workspaceRoot);
  const adminLogin = process.env.BETA_ADMIN_LOGIN || envFile.BETA_ADMIN_LOGIN || "admin";
  const adminPassword = process.env.BETA_ADMIN_PASSWORD || envFile.BETA_ADMIN_PASSWORD || "";
  if (!adminPassword) throw new Error("BETA_ADMIN_PASSWORD is required to prepare an authenticated perf student.");

  const args = parseArgs(process.argv.slice(2));
  const origin = originFor(args.url);
  const adminSession = await login(origin, adminLogin, adminPassword);
  const adminToken = adminSession.access_token;

  const classrooms = await requestJson(origin, "/accounts/classrooms", { token: adminToken });
  let classroom = classrooms.find((item) => item.grade === args.grade && item.name === args.classroomName)
    || classrooms.find((item) => item.grade === args.grade);
  if (!classroom) {
    classroom = await requestJson(origin, "/accounts/classrooms", {
      token: adminToken,
      method: "POST",
      body: {
        name: args.classroomName,
        grade: args.grade,
        academic_year: "2026",
      },
    });
  }

  let student = null;
  for (const item of classrooms.some((row) => row.id === classroom.id) ? classrooms : [classroom, ...classrooms]) {
    const students = await requestJson(origin, `/accounts/classrooms/${item.id}/students`, { token: adminToken });
    student = students.find((row) => row.login === args.login);
    if (student) break;
  }

  let temporaryPassword = "";
  if (student) {
    const reset = await requestJson(origin, `/accounts/${student.profile_id}/reset-password`, {
      token: adminToken,
      method: "POST",
    });
    temporaryPassword = reset.temporary_password;
  } else {
    const created = await requestJson(origin, "/accounts/students", {
      token: adminToken,
      method: "POST",
      body: {
        classroom_id: classroom.id,
        login: args.login,
        display_name: args.name,
      },
    });
    temporaryPassword = created.temporary_password;
  }

  const studentSession = await login(origin, args.login, temporaryPassword);
  await requestJson(origin, "/auth/change-password", {
    token: studentSession.access_token,
    method: "POST",
    body: { new_password: args.password },
  });
  const finalStudentSession = await login(origin, args.login, args.password);
  const requestedTopic = requestedTopicId(args.url);
  if (!(await canOpenLessonManifest(origin, finalStudentSession.access_token, requestedTopic))) {
    const studentId = finalStudentSession.user?.id;
    if (!studentId) throw new Error("Prepared perf student session does not include student id.");
    const map = await requestJson(origin, `/curriculum/students/${studentId}/map?refresh=true`, {
      token: finalStudentSession.access_token,
    });
    let topic = null;
    const diagnostics = [];
    for (const item of map.topics || []) {
      if (item.lesson_status !== "published" || item.state === "locked") continue;
      const probe = await lessonManifestProbe(origin, finalStudentSession.access_token, item.id);
      diagnostics.push({
        topic_id: item.id,
        subject_id: item.subject_id,
        state: item.state,
        lesson_status: item.lesson_status,
        ok: probe.ok,
        detail: probe.detail,
      });
      if (probe.ok) {
        topic = item;
        break;
      }
    }
    if (!topic) {
      throw new Error(`No accessible published lesson found for the perf student. Candidates: ${JSON.stringify(diagnostics.slice(0, 8))}`);
    }
    setSmokeArg(args, "--url", `${origin}/learn/${topic.subject_id}/${topic.id}`);
  }

  const result = spawnSync("pnpm", ["run", "perf:lesson:browser", "--", ...args.smokeArgs], {
    cwd: workspaceRoot,
    stdio: "inherit",
    env: {
      ...process.env,
      LESSON_PERF_LOGIN: args.login,
      LESSON_PERF_PASSWORD: args.password,
      LESSON_PERF_REQUIRE_SHELL: "1",
    },
  });
  process.exit(result.status ?? 1);
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
