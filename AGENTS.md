# Project Workflow

Use a visible CLI Plan for work with multiple deliverables, external evidence,
material risk, or publication. Keep one step active and reconcile it before
handoff. Small, reversible, single-step tasks may proceed directly.

Before creating a document, define final artifacts, validation, and cleanup.
After TeX/PDF compilation, delete `.aux`, `.log`, `.out`, `.toc`, `.fls`,
`.fdb_latexmk`, and `.synctex.gz`; do not commit compiler intermediates.

State data dates and sources. Separate source facts, translations, inferences,
and decisions. Run project-specific validation plus `git diff --check` before
committing. Preserve existing user changes and do not perform destructive or
external actions without authorization.
