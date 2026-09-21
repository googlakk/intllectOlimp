import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '../..');
const frontendPageMaxLines = 220;

/** @typedef {{ file: string, line: number, rule: string, text: string }} Violation */

/** @type {Violation[]} */
const violations = [];

/**
 * @param {string} dir
 * @param {Set<string>} extensions
 * @returns {string[]}
 */
function walk(dir, extensions) {
  /** @type {string[]} */
  const files = [];
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === 'dist' || entry === '__pycache__') continue;
    const path = join(dir, entry);
    const stats = statSync(path);
    if (stats.isDirectory()) {
      files.push(...walk(path, extensions));
    } else if (extensions.has(path.slice(path.lastIndexOf('.')))) {
      files.push(path);
    }
  }
  return files;
}

/**
 * @param {string} file
 * @param {number} line
 * @param {string} rule
 * @param {string} text
 */
function addViolation(file, line, rule, text) {
  violations.push({
    file: relative(root, file),
    line,
    rule,
    text: text.trim(),
  });
}

function checkBackendServices() {
  const serviceDir = join(root, 'backend/services');
  for (const file of walk(serviceDir, new Set(['.py']))) {
    const lines = readFileSync(file, 'utf-8').split(/\r?\n/);
    lines.forEach((line, index) => {
      if (line.includes('from fastapi') || line.includes('import fastapi') || line.includes('HTTPException')) {
        addViolation(file, index + 1, 'backend-services-no-fastapi', line);
      }
    });
  }
}

function checkApplicationErrors() {
  const dirs = ['backend/services', 'backend/ktp'];
  const directExceptionPattern = /^\s*class\s+\w*Error\s*\(\s*Exception\s*\)\s*:/;
  for (const dir of dirs) {
    for (const file of walk(join(root, dir), new Set(['.py']))) {
      const lines = readFileSync(file, 'utf-8').split(/\r?\n/);
      lines.forEach((line, index) => {
        if (directExceptionPattern.test(line)) {
          addViolation(
            file,
            index + 1,
            'application-errors-use-application-error',
            line,
          );
        }
      });
    }
  }
}

function checkRouteErrorMapping() {
  const routeDir = join(root, 'backend/routes');
  const manualMappingPattern = /HTTPException\s*\(\s*status_code\s*=\s*exc\.status_code\s*,\s*detail\s*=\s*exc\.detail/;
  for (const file of walk(routeDir, new Set(['.py']))) {
    const lines = readFileSync(file, 'utf-8').split(/\r?\n/);
    lines.forEach((line, index) => {
      if (manualMappingPattern.test(line)) {
        addViolation(
          file,
          index + 1,
          'routes-use-raise-http-error-helper',
          line,
        );
      }
    });
  }
}

/**
 * @param {string} line
 */
function isAllowedAny(line) {
  return line.includes('step="any"') || line.includes("step='any'");
}

function checkFrontendAny() {
  const dirs = [
    'artifacts/intellect-learning-platform/src/pages',
    'artifacts/intellect-learning-platform/src/features',
    'artifacts/intellect-learning-platform/src/components/blocks',
    'artifacts/intellect-learning-platform/src/components/layout',
  ];
  const anyPattern = /\bany\b/;
  for (const dir of dirs) {
    for (const file of walk(join(root, dir), new Set(['.ts', '.tsx']))) {
      const lines = readFileSync(file, 'utf-8').split(/\r?\n/);
      lines.forEach((line, index) => {
        if (anyPattern.test(line) && !isAllowedAny(line)) {
          addViolation(file, index + 1, 'frontend-no-explicit-any', line);
        }
      });
    }
  }
}

function checkFrontendPagesAreRoutesOnly() {
  const pagesDir = join(root, 'artifacts/intellect-learning-platform/src/pages');
  for (const file of walk(pagesDir, new Set(['.ts']))) {
    addViolation(
      file,
      1,
      'frontend-pages-route-components-only',
      'Move page-owned model/data/helpers into src/features/<domain>.',
    );
  }
}

function checkLessonBlockClassification() {
  const srcDir = join(root, 'artifacts/intellect-learning-platform/src');
  const allowedFile = join(srcDir, 'lib/lessonBlocks.ts');
  for (const file of walk(srcDir, new Set(['.ts', '.tsx']))) {
    const lines = readFileSync(file, 'utf-8').split(/\r?\n/);
    lines.forEach((line, index) => {
      if (file !== allowedFile && line.includes('ASSESSMENT_COMPONENTS')) {
        addViolation(
          file,
          index + 1,
          'frontend-centralize-lesson-block-classification',
          'Use src/lib/lessonBlocks.ts instead of local assessment component lists.',
        );
      }
      if (line.includes('assessmentComponents')) {
        addViolation(
          file,
          index + 1,
          'frontend-centralize-lesson-block-classification',
          'Use isAssessmentBlock/isObjectiveAssessmentBlock from src/lib/lessonBlocks.ts.',
        );
      }
    });
  }
}

function checkFrontendPageQueryKeys() {
  const pagesDir = join(root, 'artifacts/intellect-learning-platform/src/pages');
  const literalQueryKeyPattern = /\.(?:invalidateQueries|setQueryData)\s*\(\s*(?:\{\s*queryKey\s*:\s*)?\[/;
  for (const file of walk(pagesDir, new Set(['.tsx']))) {
    const lines = readFileSync(file, 'utf-8').split(/\r?\n/);
    lines.forEach((line, index) => {
      if (literalQueryKeyPattern.test(line)) {
        addViolation(
          file,
          index + 1,
          'frontend-pages-use-feature-cache-policy',
          'Move React Query cache keys into a feature workflow/model helper.',
        );
      }
    });
  }
}

function checkFrontendPageSize() {
  const pagesDir = join(root, 'artifacts/intellect-learning-platform/src/pages');
  for (const file of walk(pagesDir, new Set(['.tsx']))) {
    const lineCount = readFileSync(file, 'utf-8').split(/\r?\n/).length;
    if (lineCount > frontendPageMaxLines) {
      addViolation(
        file,
        frontendPageMaxLines + 1,
        'frontend-pages-stay-thin',
        `Route pages should stay under ${frontendPageMaxLines} lines; move workflow/model/views into src/features/<domain>.`,
      );
    }
  }
}

checkBackendServices();
checkApplicationErrors();
checkRouteErrorMapping();
checkFrontendAny();
checkFrontendPagesAreRoutesOnly();
checkLessonBlockClassification();
checkFrontendPageQueryKeys();
checkFrontendPageSize();

if (violations.length > 0) {
  console.error('Architecture guardrails failed:');
  for (const violation of violations) {
    console.error(
      `- ${violation.rule}: ${violation.file}:${violation.line} :: ${violation.text}`,
    );
  }
  process.exit(1);
}

console.log('Architecture guardrails passed.');
