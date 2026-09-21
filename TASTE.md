# Product Taste

The product should feel calm, practical, and teacher-first. Prefer dense but
readable workflows over marketing composition. Avoid decorative dashboards,
generic AI sparkle, vague success messages, and hidden failure states.

## Interface

- Use clear hierarchy, compact spacing, and predictable navigation.
- Make teacher workflows efficient for repeated daily use.
- Show generated content provenance and errors plainly.
- Keep controls familiar: buttons for commands, tabs for views, inputs for
  values, toggles for binary settings.

## Engineering

- Prefer small, reversible changes with tests.
- Preserve existing API behavior unless a bug is proven.
- Keep LLM behavior schema-bound and explicit about uncertainty.
- Treat parsing failures as product states, not crashes.
