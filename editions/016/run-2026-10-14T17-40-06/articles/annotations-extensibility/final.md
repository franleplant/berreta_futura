---
source_ids:
- annotations-extensibility-bb6f0748
content_mode: article
label: ARTICLE
---

Browser annotations already work on your site without code changes: people select part of a page, add a comment, and send it to Codex or ChatGPT Work. The Browser Annotation API lets your website shape that exchange. You decide what counts as one object, attach context the page doesn't show, open annotations from your own buttons, preview changes with custom controls, make shapes inside a canvas selectable, and switch Annotation mode on or off. The API lives at `document.oai.annotation` in the ChatGPT desktop app's built-in browser (DevDay 2026 release and later), on secure, top-level pages such as HTTPS or localhost. Feature-detect each method. In ChatGPT Enterprise and Edu workspaces, an admin must allow **Site annotation customizations**.

## Ground rules

When enabled, the browser installs the API before your page's scripts run. No readiness event or polling is needed. Methods return synchronously, and registration handles are ready immediately; only a surface's `hitTest` can return a promise.

## What gets selected

Mark a region with `oai-annotation-container` and its selectable descendants with `oai-annotatable`. Pointing anywhere inside a marked target selects the whole of it:

```html
<section oai-annotation-container>
  <article id="chart-card" oai-annotatable="Q3 Revenue">
    <h2>Q3 Revenue</h2>
    <p>$120,000 this quarter</p>
    <button type="button">More info</button>
  </article>
</section>
```

The optional value is a name shown to the user and the model. The container defines where the rules apply; an `oai-annotatable` attribute on its own changes nothing. Within a container, the nearest marked target wins. Unmarked areas inside it create a webpage annotation, and areas outside every container keep the default behavior.

`oai-annotation-container-text` lets people drag to select text instead. If both attributes are on one element, text selection takes precedence. The selection follows the page's normal rules and can extend beyond the container, but it doesn't enter iframes.

## Context the page doesn't show

`oai-annotation-metadata` on a marked target adds a small, flat JSON object: up to six properties, with string, finite number, boolean, or `null` values, and up to 2,048 bytes serialized. Nested objects and arrays aren't supported, and the browser ignores invalid metadata. Include only context you intend to share with both the user and the model.

## Opening an annotation from your UI

Call `document.oai.annotation.request(target, options)` directly from a user interaction, such as a button press. The target is a connected, visible element or a DOM `Range`. Awaiting a network request first can lose that interaction, and site-initiated requests may require user permission.

Options are `mode`, `enterAnnotationMode`, `metadata`, and `initialComment` (up to 240 UTF-16 code units). The returned `accepted` boolean means the browser received and validated the request. It doesn't confirm that the editor opened or that the person saved or sent anything. Opening an annotation doesn't send a message; only the user can submit it.

A `Range` must hold nonempty visible text, at most 20,000 UTF-16 code units. Text ranges use only the default editor; `mode: "advanced"` is rejected and metadata is ignored.

## Custom controls

`registerControls()` attaches up to 12 controls (`color`, `range`, `select`, `toggle`) to one or more elements. A control can preview an application property, such as a spacing token, or collect a choice, such as an email tone. On hosted sites in ChatGPT the controls appear automatically; the manual **Adjust** button exists only in Codex or on localhost.

Name controls by what they change, such as "Page background", not by the current value, such as "Warm ivory". `currentValue` is the baseline for before-and-after changes and resets; `defaultValue` takes precedence over it as the starting state. For select controls, your callback receives `option.value`, but ChatGPT receives the visible `option.label`.

Changes arrive as a bubbling `oaiannotationcontrolchange` event whose `action` is `preview`, `preview-original`, or `reset`. Apply the supplied value for every action, make handlers reversible and safe to repeat, and save only through your application's normal flow. `dispose()` removes the registration but doesn't undo your preview changes; restoring ordinary rendering is your job. Invalid definitions and exceeded limits throw synchronously, and a rejected update preserves the previous registration.

## Canvas objects

`registerSurface()` takes the host element and a `hitTest` that returns an object with a stable `id`, or `null` for empty space. You can add `name`, `role`, `metadata`, `rect`, and a `renderSelection` callback for your own hover and selection drawing. Surfaces aren't supported inside an iframe.

The browser allows 250 milliseconds before falling back to DOM selection. It permits one `hitTest` in flight and holds that slot until the promise settles, even after cancellation or a timeout, so dropping a canceled worker response can block later picking. Call `invalidate()` after moving objects or changing zoom. Control events on canvas objects carry `detail.virtualTarget`; route by that captured identity, not the current selection.

## Annotation mode

`toggle()` requests a change; its `{ accepted }` result acknowledges the request, not a confirmed mode change. Read state from `isActive()` and the `oaiannotationmodechange` event. No initial event is sent, so initialize your UI from the getter. Annotation mode captures page clicks: hold **Space** to use page controls. No attribute lets clicks pass through.

## Testing

Exercise each feature in the desktop app's built-in browser: selections, requests, previews and resets, canvas picks after cancellation, and saved annotations. Then open the site in a browser without the API and verify that normal interactions still work.

Annotations bring the person's selection and feedback into the conversation; site tools ([WebMCP](https://learn.chatgpt.com/codex/webmcp)) let the agent act on it.
