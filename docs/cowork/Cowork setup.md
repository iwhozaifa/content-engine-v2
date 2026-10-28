# Using Claude Cowork for the engine

Cowork is the no-terminal way to run the same steps, and the browser-based way to read YouTube like a person would, with no API keys. Claude Code and Cowork both read the same command files, so the behaviour is identical.

## One-time setup (10 min)

1. In the Claude desktop app, open **Cowork** and give it access to your content engine folder (the one holding `CLAUDE.md`, `tools/engine.py`, `Aliyan_AI_Content_DNA.md` and `.claude/commands/`).
2. Make sure the **Notion** connector is on and can see the Content Engine page.
3. Turn on **Claude in Chrome** (the browser extension) so Cowork can open pages. Stay logged in to YouTube in that Chrome profile; it doesn't need to be your main account.
4. Optional: save the three prompts below as reusable tasks or skills in Cowork, so each is one click.

## Prompts to paste

**Add URLs**
```
Follow CLAUDE.md, then .claude/commands/add-url.md for these URLs: <paste URLs>.
Fetch with `.venv/bin/python tools/fetch.py <urls>` first. Only for links it can't fetch, or if you can't run commands here, open the URL in Chrome instead. Read title, channel, upload date, views, likes and comment count from the page (expand the description for the date). For the transcript, open "...more" then "Show transcript" and copy it; if there is none, use the description and set Transcript source = Browser or None. Pause 3–6 seconds between page actions and use one tab at a time.
```

**Write scripts**
```
Follow CLAUDE.md, then .claude/commands/write.md for every Approved idea.
If you can't run python3 here, do the judgement part of the originality check, set Similarity flag = Not checked, and list the scripts so I can run engine.py later in Claude Code.
```

**Revise**
```
Follow CLAUDE.md, then .claude/commands/revise.md for every script marked Needs revision.
```

## Good to know

- Browsing is slower than an API: roughly 30–60 seconds per URL. That's fine for manual mode. Creator scanning in phase 2 uses the same approach.
- Automated browsing is against YouTube's terms in principle. The human pace and small volume keep the risk low, but it isn't zero.
- Cowork only runs while the laptop is on and the app is open.
