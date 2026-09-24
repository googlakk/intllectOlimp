# Visual lesson pilot: Square Garden

Route: `/visual/square-roots`. Discoverable from student `/learn` and teacher `/dashboard/lessons`.

This is an authored, public sample lesson, not the automatic lesson generator. It does not publish or replace course content. Progress is stored on this device under a versioned, user-scoped localStorage key (guest has a separate key). Course grades and skill evidence are not changed. The UI states this boundary. No server/database changes are needed.

Eight scenes: garden brief, build a 16 m² square, reverse side/area reasoning, adjustable model, predict √25, diagnose √16 misconceptions, independently find the side for 49 m², review answers and explore bounds for √20. Wrong answers have feedback and retries; scenes can be skipped without earning a solved-task result. No timer or automatic audio/video playback. Motion respects reduced-motion settings.

## Asset provenance

Built-in imagegen tool, one successful generation; no quota error. No video generation was requested from a provider. Mathematical diagrams use exact SVG geometry and are independent from decorative art.

Project asset: `artifacts/intellect-learning-platform/public/images/lessons/square-garden.png`.

Final generation prompt:

> Use case: illustration-story. Asset type: hero illustration for an interactive school mathematics lesson about designing a square garden and understanding square roots. Create a beautiful editorial architectural miniature of a square garden on a small floating cutaway earth island, neat square paving, lush small trees and shrubs around its perimeter, a tiny glass greenhouse, warm sunlight, tactile clay and paper textures, sophisticated inviting educational storybook 3D style. Wide landscape composition, entire island visible, plain soft cream background. No people, no text, no letters, no equations, no logos, no watermark. Decorative story illustration only, exact mathematical diagrams are drawn separately in the app.

## Verification

- Model tests: wrong-to-correct attempts, idempotent correct response, negative roots, invalid storage, schema versions, exact restoration, recomputed correctness.
- Browser: complete all three tasks; retry incorrect and negative answers; reload and return to a solved task; reset; skipped tasks remain unsolved; keyboard slider; all eight scenes at 375 px without horizontal overflow; reduced motion.
- Screenshots in `output/playwright/garden-desktop.png`, `garden-model.png`, `garden-mobile-intro.png`, `garden-mobile-project.png`.

The existing publication-quality test had stale text expectations from earlier wording changes; expectations now match the current Russian copy without changing publication logic.
