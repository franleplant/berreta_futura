# Bundled publication fonts

These fonts are committed so PDF output is reproducible across machines.

## Inter 4.1

Source: <https://github.com/rsms/inter/releases/tag/v4.1>

Files used: Regular, Medium, SemiBold, and Bold static TTFs from the official release archive. License: SIL Open Font License 1.1; see `inter/LICENSE.txt`.

## Source Serif 4.005

Source: <https://github.com/adobe-fonts/source-serif/releases/tag/4.005R>

Files used: Small Text Regular, Italic, and Bold plus Display Semibold static TTFs from the official desktop release archive. License: SIL Open Font License 1.1; see `source-serif-4/LICENSE.md`.

## Geist Mono 1.7.2

Source: <https://github.com/vercel/geist-font/releases/tag/v1.7.2>

Files used: Regular, Medium, and SemiBold static TTFs. Serves `pre`/`code` as "Magazine Mono". License: SIL Open Font License 1.1; see `geist-mono/OFL.txt`.

The renderer resolves these files relative to the installed `magazine` package. Never replace this with a lookup in `/Library/Fonts`, a user font directory, or a network font service.
