# Grade 7 visual samples

Two authored samples selected from the teacher's uploaded curriculum on 2026-09-24:

- Physics: topic 233, «Плотность». Route `/visual/density`, title «Мастерская невидимого».
- History: topic 164, «Хозяйство в эпоху Караханидов». Route `/visual/silk-road`, title «Один день на Шёлковом пути».

Each contains seven scenes, two generated illustrations, an interactive exploration and three questions. The shared shell saves answers and position locally under separate lesson/user/version keys, validates stored data, keeps failed responses retryable, and does not count repeated submissions of a solved question. Laboratory controls reset when leaving their scene; answered questions and position persist. These are publicly accessible authored samples, not published course lessons or automatic generation. No course rows, grades, authentication or backend behavior were changed.

History references are available in the final scene: UNESCO Silk Roads World Heritage listing, UNESCO History of Central Asian Civilizations IV, and the open-access archaeobotanical study of Qarakhanid Paykend (DOI 10.1007/s12231-021-09531-6). All historical scenes and hypothetical situations are explicitly labeled teaching reconstructions, not evidence or exact city plans.

## Images

All four assets were generated with the built-in imagegen tool. No quota error occurred. No video provider was used. Files are saved in `artifacts/intellect-learning-platform/public/images/lessons/`.

### density-workshop.png — final prompt

Use case illustration-story. Landscape editorial storybook 3D clay-and-paper miniature for a grade7 physics lesson about density. A beautifully lit small scientist's workshop on an isolated cream backdrop, wooden workbench with two equal size solid cubes one pale wood one copper, precise balance scales, glass measuring cylinder, notebook without lettering. Inviting warm sunlight with cool teal shadows, tactile materials, sophisticated educational aesthetic, no people, no text, no numerals, no labels, no watermark. Full miniature composition with breathing space. Decorative introductory scene; exact measurements drawn separately by software.

### density-closeup.png — final prompt

Use case illustration-story. Wide close-up editorial educational clay-and-paper 3D illustration, warm wooden science workshop with teal lamp, same inviting tactile style as physics density lesson. Focus on a solid copper cube beside a smaller equal-material copper cube and an accurate looking glass measuring cylinder with clear water on a wooden bench. Plain notebook and brass balance in softly blurred background. Copper cubes visibly solid, no cutouts or hollow boxes, no floating objects. Soft sunlight, cream and deep teal palette. No letters, no labels, no text, no numerals, no equations, no watermark. Decorative illustration of comparing amounts of same material; exact values overlaid separately in software.

### karakhanid-city.png — final prompt

Use case illustration-story. Wide landscape tactile clay and paper editorial 3D illustration for grade7 history lesson economy of Karakhanid Central Asia 10th to12th centuries. Bird's eye miniature of an imagined Central Asian oasis town in a river valley near distant mountains, adobe walled settlement with modest fired brick tower, workshops and covered market, irrigation channel feeding rectangular green fields, sheep pasture and yurts outside walls, small camel caravan on road. Warm ochre terracotta, sage vegetation, cream sky, soft morning light. Historically restrained, no giant blue Timurid domes, no European castles, no modern objects, no text, no labels. This is an explicitly artistic educational reconstruction of economic activities, not a specific archaeological site's exact plan. Rich detail but clear readable composition.

### karakhanid-market.png — final prompt

Use case illustration-story. Wide editorial storybook tactile miniature 3D illustration for grade7 history economy Karakhanid Central Asia 10th-12th centuries. Close street view of a modest adobe town bazaar, a potter shaping clay at a simple wheel with earthenware jars, a wool textile seller and folded woven cloths, baskets of grain, a merchant with a loaded camel near gate, restrained period robes. Warm ochre cream sage, soft morning sun. Consistent sophisticated clay-and-paper educational aesthetic, rich but uncluttered. No modern objects, no giant blue Timurid domes, no European medieval buildings, no text, no lettering, no watermarks. An imagined artistic reconstruction, not a photographic historical document.

## Verification

Frontend tests cover density computation, conversion, proportional mass/volume, invalid values, answer correction, persistence validation, lesson isolation and question contracts. Browser checks cover the two three-question flows, wrong-to-correct response, keyboard slider recalculation, city area selection, irrigation toggle and reload restoration. Responsive screens are checked at 375 px. Typecheck, architecture guardrails and frontend production build pass.
