# Legacy Direct Export

Use this compatibility path only when the selected delivery mode is **Legacy Direct Export**: the user explicitly asks `ppt-master` itself to export PPTX, or the native editable rebuild path is unavailable.

## Contract

- A completed SVG draft must exist.
- Produce only the requested compatibility PPTX.
- Warn that converter-oriented export may flatten structure, reduce editability, or render differently from the browser preview.
- Run the three commands below individually. Confirm each succeeds before starting the next; never bundle them into one shell invocation.

## 1. Split speaker notes

```bash
python3 ${SKILL_DIR}/scripts/total_md_split.py <project_path>
```

## 2. Finalize SVG

```bash
python3 ${SKILL_DIR}/scripts/finalize_svg.py <project_path>
```

Never use `cp` as a substitute: finalization embeds icons and images, applies crops, flattens text, and normalizes rounded rectangles.

## 3. Export PPTX

```bash
python3 ${SKILL_DIR}/scripts/svg_to_pptx.py <project_path> -s final
```

Always export from `svg_final/` with `-s final`, never directly from `svg_output/`. The only documented optional export selector is `--only native|legacy`; do not add ad-hoc flags to the post-processing commands.
