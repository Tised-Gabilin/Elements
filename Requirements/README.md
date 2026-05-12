# Requirements Folder Contract

This folder holds requirement inputs and reusable technical design patterns for new Mistral app projects.

## Inputs

- `Initial Research.md` (optional at project initialization): app-specific research and strategy input.
- If this file is not present during initialization, the operator can add it manually later.
- `app_icon/`: folder reserved for icon source assets and export variants.

## Expected Agent Outputs

Agents should parse `Initial Research.md` and produce:

- `Business.md`: positioning, competitors, pricing, regions, localization, and rollout strategy.
- `Architecture.md`: technical architecture, stack, data model, modules, and implementation plan.
- `UseCases.md`: primary use cases for product, QA, and go-to-market messaging.
- `UX.md`: UX principles, core flows, interaction patterns, and links to design tools.

## Default Technical Pattern Files

- `Purchase.md`: baseline in-app purchase technical design template.
- This file is always part of the template and should remain available across projects.

## Conventions

- Keep files in markdown format.
- Keep app icon source files and export assets inside `app_icon/`.
- Prefer explicit headings and short actionable sections.
- Keep app-specific assumptions in `Initial Research.md` and derived output files, not in reusable templates.