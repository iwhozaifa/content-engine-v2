+++
task = "similarity_judge"
tools = []
+++
Check one script for material lifted from its source. A deterministic check already found shared word runs
(listed below). Judge whether the script copies the source's wording, examples, stories, numbers or distinctive
structure. Shared common phrases ("the problem is", tool names) are fine.

## Script
{{script}}

## Source outline and key points
{{source}}

## Shared word runs found in code
{{runs}}

Return a verdict (OK, Review or Too close), each lifted item with its type and the script line, and up to 3 short
rewrite hints.
