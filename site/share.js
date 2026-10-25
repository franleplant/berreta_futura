(() => {
  const script = document.currentScript;
  const scope = document.querySelector(".piece");
  if (!scope || !navigator.clipboard) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "share";
  button.hidden = true;
  document.body.append(button);

  const words = (text) => text.trim().split(/\s+/).filter(Boolean);
  const part = (text) =>
    encodeURIComponent(text).replace(
      /[-,&]/g,
      (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`
    );

  const inword = /[\p{L}\p{N}_'’]/u;

  const grow = (range) => {
    const wide = range.cloneRange();
    const head = wide.startContainer;
    const tail = wide.endContainer;
    if (head.nodeType === 3) {
      while (
        wide.startOffset > 0 &&
        inword.test(head.textContent[wide.startOffset - 1])
      ) {
        wide.setStart(head, wide.startOffset - 1);
      }
    }
    if (tail.nodeType === 3) {
      while (
        wide.endOffset < tail.textContent.length &&
        inword.test(tail.textContent[wide.endOffset])
      ) {
        wide.setEnd(tail, wide.endOffset + 1);
      }
    }
    return wide;
  };

  const fragment = ({ text, split }) => {
    const all = words(text);
    if (all.length <= 10 && !split) return part(all.join(" "));
    const half = Math.min(5, Math.floor(all.length / 2));
    return `${part(all.slice(0, half).join(" "))},${part(all.slice(all.length - half).join(" "))}`;
  };

  let picked = { text: "", split: false };

  const place = (rect) => {
    button.textContent = script.dataset.copy;
    button.hidden = false;
    const left =
      window.scrollX + rect.left + rect.width / 2 - button.offsetWidth / 2;
    const room = document.documentElement.clientWidth - button.offsetWidth - 8;
    button.style.top = `${Math.max(8, window.scrollY + rect.top - button.offsetHeight - 10)}px`;
    button.style.left = `${Math.max(8, Math.min(left, room))}px`;
  };

  const offer = () => {
    const selection = document.getSelection();
    if (!selection || selection.isCollapsed || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    if (!scope.contains(range.commonAncestorContainer)) return;
    const wide = grow(range);
    const raw = wide.toString();
    if (words(raw).length < 3) return;
    picked = { text: words(raw).join(" "), split: /\n/.test(raw.trim()) };
    selection.removeAllRanges();
    selection.addRange(wide);
    place(wide.getBoundingClientRect());
  };

  document.addEventListener("selectionchange", () => {
    const selection = document.getSelection();
    if (!selection || selection.isCollapsed) button.hidden = true;
  });
  document.addEventListener("mouseup", () => window.setTimeout(offer, 0));
  document.addEventListener("touchend", () => window.setTimeout(offer, 0));
  document.addEventListener("keyup", (event) => {
    if (event.shiftKey) offer();
  });
  button.addEventListener("mousedown", (event) => event.preventDefault());
  button.addEventListener("click", async () => {
    const here = window.location.href.split("#")[0];
    try {
      await navigator.clipboard.writeText(`${here}#:~:text=${fragment(picked)}`);
      button.textContent = script.dataset.done;
    } catch {
      button.textContent = script.dataset.failed;
    }
  });
})();
