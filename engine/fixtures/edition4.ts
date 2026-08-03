import { copyFile, mkdir, readFile } from "node:fs/promises";
import { dirname, extname, join, resolve } from "node:path";

import { parse } from "yaml";

import { newArtifactId, type ArtifactId } from "../contracts/index.ts";
import {
  RENDERER_CONTRACT_VERSION,
  type RenderManifest,
  type StagedFile,
} from "../renderer-adapter/index.ts";

export const EDITION_4_ID = "004-the-systems-around-the-model";

type Mapping = Record<string, unknown>;

type FixtureEntry = {
  readonly artifactId: ArtifactId;
  readonly source: string;
  readonly target: string;
  readonly kind: string;
};

export type Edition4Fixture = {
  readonly manifest: RenderManifest;
  readonly entries: readonly FixtureEntry[];
  readonly selectedArtArtifactIds: readonly ArtifactId[];
  readonly sourceFigureArtifactIds: readonly ArtifactId[];
};

/** Read-only inventory of the exact already-selected Edition 4 image files. */
export async function edition4SelectedArtPaths(
  projectRoot: string,
): Promise<readonly string[]> {
  const root = resolve(projectRoot);
  const editionTarget = `editions/${EDITION_4_ID}/edition.yaml`;
  const edition = await readYaml(join(root, editionTarget));
  const editionRoot = dirname(editionTarget);
  const paths = new Set<string>();
  for (const article of objectArray(edition.articles, "edition.articles")) {
    const opener = mapping(article.opener_art, "article.opener_art");
    paths.add(requiredString(opener, "path"));
    const tail = optionalString(article.tail_art_path);
    if (tail !== undefined) paths.add(tail);
  }
  for (const plate of objectArray(edition.closing_plates, "edition.closing_plates")) {
    paths.add(requiredString(plate, "art_path"));
  }
  const cover = mapping(edition.cover, "edition.cover");
  const selectedCover = `${editionRoot}/${requiredString(cover, "art_path")}`;
  paths.add(selectedCover);
  if (paths.size !== 13) {
    throw new Error(`edition 4 inventory expected 13 selected art files, found ${paths.size}`);
  }
  if ([...paths].some((path) => path.includes("candidate-") && path !== selectedCover)) {
    throw new Error("edition 4 inventory selected an unapproved cover candidate");
  }
  return [...paths];
}

export async function stageEdition4Fixture(
  projectRoot: string,
  artifactRoot: string,
): Promise<Edition4Fixture> {
  const root = resolve(projectRoot);
  const ownedRoot = resolve(artifactRoot);
  const editionTarget = `editions/${EDITION_4_ID}/edition.yaml`;
  const edition = await readYaml(join(root, editionTarget));
  const paths = new Map<string, string>();
  const artPaths = new Set<string>();
  const figurePaths = new Set<string>();
  const editionRoot = dirname(editionTarget);

  add(paths, editionTarget, "edition_manifest");
  add(paths, `${editionRoot}/${requiredString(edition, "editorial")}`, "editorial");
  add(paths, requiredString(edition, "art_direction_path"), "art_direction");

  const sourceIds = stringArray(edition.sources, "edition.sources");
  const articles = objectArray(edition.articles, "edition.articles");
  for (const article of articles) {
    add(paths, requiredString(article, "manuscript"), "article");
    const opener = mapping(article.opener_art, "article.opener_art");
    const openerPath = requiredString(opener, "path");
    add(paths, openerPath, "selected_art");
    artPaths.add(openerPath);
    const tail = optionalString(article.tail_art_path);
    if (tail !== undefined) {
      add(paths, tail, "selected_art");
      artPaths.add(tail);
    }
    for (const figure of objectArray(article.figures ?? [], "article.figures")) {
      const sourceId = requiredString(figure, "source_id");
      const assetId = requiredString(figure, "asset_id");
      const recordTarget = `library/sources/${sourceId}/record.yaml`;
      const record = await readYaml(join(root, recordTarget));
      const media = findMediaAsset(record, assetId);
      const sourceRoot = `library/sources/${sourceId}`;
      const rawRoot = `${sourceRoot}/raw/${media.captureId}`;
      add(paths, `${rawRoot}/manifest.json`, "source_media_manifest");
      const target = media.artifactPath.startsWith(`media/derived/${media.captureId}/`)
        ? `${sourceRoot}/${media.artifactPath}`
        : `${rawRoot}/artifacts/${media.artifactPath}`;
      if (media.artifactPath.startsWith(`media/derived/${media.captureId}/`)) {
        add(
          paths,
          `${sourceRoot}/media/${media.captureId}.curation.json`,
          "source_media_curation",
        );
      }
      add(paths, target, "source_figure");
      figurePaths.add(target);
    }
  }

  for (const plate of objectArray(edition.closing_plates, "edition.closing_plates")) {
    const path = requiredString(plate, "art_path");
    add(paths, path, "selected_art");
    artPaths.add(path);
  }

  for (const sourceId of sourceIds) {
    add(paths, `library/sources/${sourceId}/record.yaml`, "source_record");
    add(paths, `library/sources/${sourceId}/extracted.md`, "source_extraction");
  }

  const translationRoot = `editions/${EDITION_4_ID}/translations/es`;
  const translationTarget = `${translationRoot}/edition.yaml`;
  const translation = await readYaml(join(root, translationTarget));
  add(paths, translationTarget, "translation_manifest");
  const translatedEditorial = mapping(translation.editorial, "translation.editorial");
  add(
    paths,
    `${translationRoot}/${requiredString(translatedEditorial, "path")}`,
    "translation",
  );
  for (const article of objectArray(translation.articles, "translation.articles")) {
    add(
      paths,
      `${translationRoot}/${requiredString(article, "manuscript")}`,
      "translation",
    );
  }

  const cover = mapping(edition.cover, "edition.cover");
  const selectedCover = `${editionRoot}/${requiredString(cover, "art_path")}`;
  add(paths, selectedCover, "selected_art");
  artPaths.add(selectedCover);

  for (const target of [
    "design/covers/canto-vivo/design.toml",
    "design/covers/canto-vivo/references/en.png",
    "design/covers/canto-vivo/references/es.png",
    "design/covers/canto-vivo/back-references/en.png",
    "design/covers/canto-vivo/back-references/es.png",
  ]) {
    add(paths, target, "cover_design");
  }

  if (artPaths.size !== 13) {
    throw new Error(`edition 4 fixture expected 13 selected art files, found ${artPaths.size}`);
  }
  if (figurePaths.size !== 7) {
    throw new Error(`edition 4 fixture expected 7 source figures, found ${figurePaths.size}`);
  }
  if ([...artPaths].some((path) => path.includes("candidate-") && path !== selectedCover)) {
    throw new Error("edition 4 fixture selected an unapproved cover candidate");
  }

  const entries: FixtureEntry[] = [];
  for (const [target, kind] of paths) {
    const artifactId = newArtifactId();
    const payload = join(ownedRoot, artifactId, "payload");
    await mkdir(dirname(payload), { recursive: true });
    await copyFile(join(root, target), payload);
    entries.push({ artifactId, source: payload, target, kind });
  }
  const byTarget = new Map(entries.map((entry) => [entry.target, entry]));
  const inputs: StagedFile[] = entries.map((entry) => ({
    artifactId: entry.artifactId,
    sourcePath: entry.source,
    targetPath: entry.target,
  }));
  return {
    entries,
    selectedArtArtifactIds: [...artPaths].map((path) => requiredEntry(byTarget, path).artifactId),
    sourceFigureArtifactIds: [...figurePaths].map((path) => requiredEntry(byTarget, path).artifactId),
    manifest: {
      schemaVersion: 1,
      rendererContractVersion: RENDERER_CONTRACT_VERSION,
      operation: "render_edition",
      editionId: EDITION_4_ID,
      primaryLanguage: "en",
      languages: ["en", "es"],
      publicationName: "Berreta Futura",
      renderer: "weasyprint",
      artifactRoot: ownedRoot,
      inputs,
      metadata: {
        fixture: "released-edition-4",
        imageGenerationAllowed: false,
      },
    },
  };
}

function add(paths: Map<string, string>, target: string, kind: string): void {
  const normalized = target.replaceAll("\\", "/").replace(/^\.\//, "");
  if (normalized.startsWith("/") || normalized.split("/").includes("..")) {
    throw new Error(`unsafe fixture path: ${target}`);
  }
  paths.set(normalized, paths.get(normalized) ?? kind);
}

async function readYaml(path: string): Promise<Mapping> {
  return mapping(parse(await readFile(path, "utf8")), path);
}

function mapping(value: unknown, label: string): Mapping {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be a mapping`);
  }
  return value as Mapping;
}

function objectArray(value: unknown, label: string): Mapping[] {
  if (!Array.isArray(value)) {
    throw new Error(`${label} must be a list`);
  }
  return value.map((item, index) => mapping(item, `${label}[${index}]`));
}

function stringArray(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !item)) {
    throw new Error(`${label} must be a list of strings`);
  }
  return value as string[];
}

function requiredString(row: Mapping, key: string): string {
  const value = row[key];
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${key} must be a non-empty string`);
  }
  return value;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function findMediaAsset(
  record: Mapping,
  assetId: string,
): { readonly captureId: string; readonly artifactPath: string } {
  for (const review of objectArray(record.media_reviews ?? [], "record.media_reviews")) {
    const captureId = requiredString(review, "capture_id");
    for (const asset of objectArray(review.assets ?? [], "media_review.assets")) {
      if (asset.id === assetId) {
        return { captureId, artifactPath: requiredString(asset, "artifact_path") };
      }
    }
  }
  throw new Error(`source record does not contain figure ${assetId}`);
}

function requiredEntry(
  entries: ReadonlyMap<string, FixtureEntry>,
  target: string,
): FixtureEntry {
  const entry = entries.get(target);
  if (entry === undefined) {
    throw new Error(`fixture entry is missing: ${target}`);
  }
  return entry;
}

export function mediaTypeForFixture(path: string): string {
  switch (extname(path).toLowerCase()) {
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    case ".png":
      return "image/png";
    case ".md":
      return "text/markdown";
    case ".toml":
      return "application/toml";
    case ".yaml":
    case ".yml":
      return "application/yaml";
    default:
      return "application/octet-stream";
  }
}
