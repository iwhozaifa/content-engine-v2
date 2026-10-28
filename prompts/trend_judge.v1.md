+++
task = "trend_judge"
tools = []
+++
These posts from one creator are performing above that creator's normal level. The numbers were computed in
code; don't recompute them. Decide which posts carry a rich topic: a substantive idea the creator below could
transform into their own short (not just a trend, meme, giveaway or personal news).

## Creator brand (Content DNA)
{{brand}}

## Topic labels already in use (reuse one when it is the same topic, so recurrence can be counted)
{{labels}}

## Posts
{{posts}}

For every post (by its "n"), return:
- rich_topic: true only if there is a real, transferable idea that fits the brand's pillars.
- rich_reason: one line on why (or why not).
- topic_label: 2–5 words naming the topic, reusing an existing label when it's the same topic.
- evergreen: true if it will still matter in 3 months.
- substance: 0–10, how much real insight the post has (from title and description).
