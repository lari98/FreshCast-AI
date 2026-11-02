# Design tokens: "Aubergine & Teal"

The dashboard palette replaced the earlier blue/green scheme. Every colour is a CSS token in
`apps/dashboard/app/globals.css`; components never use literal colours.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#faf5ee` | `#160d1c` | page |
| `--surface` | `#ffffff` | `#21142a` | cards |
| `--surface-2` | `#f4ecf3` | `#2b1b36` | tinted panels |
| `--text` | `#24122b` | `#f6ecf8` | body text |
| `--muted` | `#5d4a63` | `#c7b0cf` | secondary text |
| `--accent` | `#7a2e8e` | `#e0a3f0` | actions, links, selected tab |
| `--accent-text` | `#ffffff` | `#2a0f33` | text on accent |
| `--accent-2` | `#0e8f7d` | `#4fd1bb` | borders, gradients, graphics (never text) |
| `--saffron` | `#f2a93b` | `#ffc36b` | highlight stripe |

## Contrast (computed with the WCAG 2.x relative-luminance formula)

| Pair | Light | Dark | Target |
|---|---|---|---|
| text / bg | 16.18 | 16.48 | 4.5 |
| text / surface | 17.55 | 15.25 | 4.5 |
| muted / bg | 7.38 | 9.51 | 4.5 |
| muted / surface-2 | 6.91 | 8.03 | 4.5 |
| accent / bg | 7.42 | 9.62 | 4.5 |
| accent / surface | 8.05 | 8.90 | 4.5 |
| accent-text / accent | 8.05 | 8.78 | 4.5 |
| accent-2 / bg (graphics) | 3.69 | 10.08 | 3.0 |

Status colours stay distinguishable without colour alone (text labels and icons accompany them).
This is an engineering check, not a formal accessibility conformance claim.
