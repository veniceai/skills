---
name: venice-sandbox-new-tab
description: Open a rendered HTML sandbox artifact in a new browser tab from inside its sandboxed iframe. Covers the anchor-not-button rule, preparing the href on pointerdown and contextmenu before the native menu builds, the no-preventDefault rule, blob and data-URI targets, the left-click escalation chain when popups are blocked, opaque-origin failures, and the self-contained artifact constraints the snapshot depends on.
---

# Sandbox: open artifact in new tab

Artifacts render inside a sandboxed iframe. Producing a new tab from one is not a `window.open` call — it is a link the browser chrome can act on. This skill covers the working structure and the failure modes that make the naive version look like a broken button.

No HTTP request is involved anywhere in this skill. The only surface is DOM events and URL APIs.

## Use when

- An artifact needs an "open in new tab" control.
- `window.open` returns `null`, silently fails, or opens a blank tab.
- A right-click context menu is swallowed by an artifact.
- A user reports the control working in one browser and not another.
- An artifact needs to be shareable or reopenable as a live copy rather than a static image.

## Surface

| Event / API | Target | Notes |
|---|---|---|
| `pointerdown` | the anchor | Fires before the menu. Prepare the href here. |
| `contextmenu` | the anchor | Do not cancel. The native menu carries "Open link in new tab". |
| `click` | the anchor | Prepare href if still empty, then let default navigation run. |
| `URL.createObjectURL` | a `Blob` of the snapshot | Cheap for large documents. Opaque origin. |
| `URL.revokeObjectURL` | previous blob | Deferred ~30s. Each preparation leaks one otherwise. |
| `window.open` | `''`, then `document.write` | Left-click fallback. Returns `null` when blocked. |
| `location.href` | blob or data URI | Final fallback. Navigates in place. |

## Quick start

Markup is an anchor. A `<button>` cannot carry a link target, so it never gets the menu item.

```html
<a id="tabbtn" href="#" target="_blank" rel="noopener">right click → open in new tab</a>
```

```js
const tabbtn = document.getElementById('tabbtn');
let lastUrl = null;

function prepHref() {
  const html = '<!DOCTYPE html>' + document.documentElement.outerHTML;
  try {
    const old = lastUrl;
    lastUrl = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
    tabbtn.href = lastUrl;
    if (old) setTimeout(() => { try { URL.revokeObjectURL(old); } catch (e) {} }, 30000);
    return true;
  } catch (e) {
    try {
      tabbtn.href = 'data:text/html;charset=utf-8,' + encodeURIComponent(html);
      return true;
    } catch (e2) { return false; }
  }
}

tabbtn.addEventListener('pointerdown', prepHref);
tabbtn.addEventListener('contextmenu', prepHref);
tabbtn.addEventListener('click', () => {
  if (!tabbtn.href || tabbtn.href.endsWith('#')) prepHref();
});
```

Test locally by serving the artifact file and opening it in the target browser:

```bash
python3 -m http.server 8000
# then open http://localhost:8000/artifact.html and right click the control
```

## Parameters

### Required

- Element — an `<a>` with `href` present and `target="_blank"`. Not a `<button>`, not a div.
- A prepared href before the menu is constructed. `pointerdown` covers both gestures; `contextmenu` is the safety net.

### Optional

- `rel="noopener"` — recommended on the anchor. It is safe here because the anchor route does not depend on a return value.
- Snapshot source — default `document.documentElement.outerHTML`. Narrow it to a container if the page carries chrome you do not want copied.
- Revoke delay — default 30s. Raise it if the target is likely to be slow to load.
- Status line — a small element reporting which route ran, so a failure is diagnosable rather than silent.

## Result

Right click opens the native context menu with a live "Open link in new tab" item; the browser opens a working copy of the artifact in a new tab. Left click opens the same copy where popups are permitted.

The copy is a fresh document. Module state, counters and in-memory collections start empty — only `localStorage` survives. Label that in the UI rather than implying the session carries over.

## Errors

| Symptom | Cause | Fix |
|---|---|---|
| Nothing happens, no menu | `preventDefault()` on `contextmenu` | Drop it; let the native menu appear |
| Menu appears, no link item | `<button>`, or `href` still `#` | Use an anchor; prepare href on `pointerdown` |
| Tab opens blank | Blob blocked by opaque origin | Use the `window.open('')` + `document.write` route |
| `null` returned on a successful open | `'noopener'` passed to `window.open` | Omit it when you need the return value |
| Works in one browser, not another | Strict popup policy | The native menu route sidesteps popup blocking |
| Second click shows a stale page | Previous object URL not revoked | Revoke on a timer |

## Gotchas

- `window.open(url, '_blank', 'noopener')` returns `null` **even on success**, so a null-check fires the fallback on a successful call and the tab never appears. This is the single most common way to break this.
- Prepare the href on `pointerdown`, not only on `contextmenu`. Some platforms raise the menu without a prior pointer event.
- The snapshot must survive serialisation: inline all CSS and JS, no cross-origin fetches, no external fonts.
- Content must be deterministic or seeded, or a reopened copy reshuffles into something else.
- Persist state in `localStorage`. Anything in module scope is lost in the copy.
- Cap and prune DOM growth. A snapshot of a runaway DOM is slow to open.
- Never build the snapshot on every render. It is needed on exactly two gesture events.
- Left click is still subject to popup blocking. If you support it, escalate in order — write into a blank window, then blob, then programmatic anchor click, then in-place navigation — and report which ran.
- Cross-links: [`venice-create-video`](../venice-create-video/SKILL.md) and [`venice-video`](../venice-video/SKILL.md) for artifacts that queue renders; [`venice-api-overview`](../venice-api-overview/SKILL.md) for base-URL and key conventions if the artifact also calls the API.
