# Corpus

Drop your knowledge documents in this folder. The ingest step (`make ingest`)
reads every `.md` and `.txt` file under `corpus/` (recursively), chunks them,
embeds the chunks, and saves the index to `data/index.pkl`.

## Format

- One document per file. Filename is shown as the citation in Discord, so use
  human-readable names (e.g. `blackhole-policy.md`, `freeze-procedure.md`).
- Plain Markdown or plain text. No special frontmatter required.
- Paragraphs separated by blank lines work best — chunking respects paragraph
  boundaries.
- Keep individual paragraphs roughly under 500 characters where possible. Long
  paragraphs still work but make less precise citations.

## After editing

```sh
make ingest
make run
```

The bot will reload the new index next time it starts.

## Replace the example

`example-rules.md` in this folder is a placeholder demonstrating the format.
Delete it once you have your real content.
