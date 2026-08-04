/**
 * Validate the parts of Markdown that a translation is not allowed to alter.
 * Prose is intentionally not compared.  Links, frontmatter keys, list and
 * heading structure, and fenced code are immutable source structure.
 */
export function assertTranslatedMarkdownStructure(english: string, translated: string): void {
  const englishCode = fencedBlocks(english);
  const translatedCode = fencedBlocks(translated);
  if (englishCode.length !== translatedCode.length || englishCode.some((block, index) => block !== translatedCode[index])) {
    throw new Error("translation changed a fenced code block");
  }
  const englishFrontmatter = frontmatterShape(english);
  const translatedFrontmatter = frontmatterShape(translated);
  if (englishFrontmatter !== translatedFrontmatter) throw new Error("translation changed frontmatter structure");
  const englishShape = markdownShape(english);
  const translatedShape = markdownShape(translated);
  if (englishShape !== translatedShape) throw new Error("translation changed Markdown structure");
  if (/\[\^\w+\]/u.test(translated)) throw new Error("translation must not add CommonMark footnotes");
}

function fencedBlocks(value: string): readonly string[] {
  const lines = value.replaceAll("\r\n", "\n").split("\n");
  const blocks: string[] = [];
  let block: string[] | undefined;
  let marker = "";
  for (const line of lines) {
    const opening = /^( {0,3})(`{3,}|~{3,})(.*)$/u.exec(line);
    if (block === undefined && opening !== null) {
      block = [line];
      marker = opening[2]!;
      continue;
    }
    if (block !== undefined) {
      block.push(line);
      if (new RegExp(`^ {0,3}${marker[0] === "`" ? "`" : "~"}{${marker.length},}\\s*$`, "u").test(line)) {
        blocks.push(block.join("\n"));
        block = undefined;
        marker = "";
      }
    }
  }
  if (block !== undefined) throw new Error("translation contains an unterminated fenced code block");
  return blocks;
}

function frontmatterShape(value: string): string {
  const normalized = value.replaceAll("\r\n", "\n");
  const match = /^---\n([\s\S]*?)\n---(?:\n|$)/u.exec(normalized);
  if (match === null) return "";
  return match[1]!.split("\n").map((line) => {
    const separator = line.indexOf(":");
    return separator < 0 ? line.trim() : `${line.slice(0, separator).trim()}:`;
  }).join("\n");
}

function markdownShape(value: string): string {
  const lines = value.replaceAll("\r\n", "\n").split("\n");
  let inCode = false;
  const output: string[] = [];
  for (const line of lines) {
    const fence = /^( {0,3})(`{3,}|~{3,})/u.exec(line);
    if (fence !== null) {
      inCode = !inCode;
      output.push(`fence:${fence[2]![0]}:${fence[2]!.length}`);
      continue;
    }
    if (inCode) {
      output.push("code");
      continue;
    }
    if (line.trim() === "") {
      output.push("blank");
      continue;
    }
    const heading = /^( {0,3})(#{1,6})(?:\s+|$)/u.exec(line);
    if (heading !== null) {
      output.push(`heading:${heading[2]!.length}`);
      continue;
    }
    const quote = /^( {0,3}> ?)/u.exec(line);
    if (quote !== null) {
      output.push(`quote:${quote[1]!.trim().length}`);
      continue;
    }
    const list = /^(\s*)(?:(?:[-+*])|(?:\d+[.)]))\s+/u.exec(line);
    if (list !== null) {
      output.push(`list:${list[1]!.length}:${line.trimStart().startsWith("[ ]") ? "task" : "item"}`);
      continue;
    }
    if (/^\s*\|?.*\|.*\|\s*$/u.test(line) && /\|\s*:?-{3,}:?\s*(?:\||$)/u.test(line)) {
      output.push("table");
      continue;
    }
    const inline = line
      .replace(/\[[^\]]*\]\(([^)]+)\)/gu, "[link:$1]")
      .replace(/`[^`]*`/gu, "`code`")
      .replace(/(\*\*|__|~~|\*|_)/gu, "$1")
      .replace(/[^\[\]()*_`~]+/gu, "x");
    output.push(`paragraph:${inline}`);
  }
  return output.join("\n");
}
