---
name: Anthropic workspace headers
description: Anthropic API key scope behavior relevant to direct Messages API calls.
---

An Anthropic API key that is not scoped to a workspace requires the target workspace ID in the `anthropic-workspace-id` request header. A valid key alone is not sufficient for Messages API requests.

**Why:** The API returned a 400 invalid request error during a real lesson-generation call, explicitly stating that an unscoped key must include the workspace header.

**How to apply:** Keep the workspace ID in a non-secret environment variable and pass it as the SDK's default header. Never log or expose the API key.