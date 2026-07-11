# Mind Frontier Studio v28 — Interface Redesign

The existing single-page stack is reorganized into an application shell without
changing backend endpoints or existing element IDs.

## Navigation

- Overview
- Create
- YouTube
- Atlas
- Automation
- Projects
- More (automatically appears for unmatched modules)

## Behavior

- Existing panels are moved into routed views after page load.
- Existing JavaScript listeners continue to work because original elements and IDs are preserved.
- The active view is stored locally.
- URL hashes support direct navigation.
- `Ctrl/Cmd + K` opens quick navigation.
- `Alt + 1–9` switches views.
- Mobile navigation uses an off-canvas sidebar.

## Files

- `static/app-shell.js`
- `static/app-shell.css`
