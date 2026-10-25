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

  const fragment = (text) => {
    const all = words(text);
    if (all.length <= 10) return part(all.join(" "));
    return `${part(all.slice(0, 5).join(" "))},${part(all.slice(-5).join(" "))}`;
  };

  let picked = "";

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
    const text = words(selection.toString()).join(" ");
    if (words(text).length < 3) return;
    picked = text;
    place(range.getBoundingClientRect());
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
