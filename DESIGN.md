# Cascade — Design System

> Cascade is a developer-facing AI-workflow tool. The aesthetic is a focused,
> high-contrast **developer console**: a calm dark surface, one electric accent,
> and monospace for anything machine-generated (logs, JSON, run output).
> Reference points: Linear, Vercel, Resend, Railway.

## Principles
1. Content first, chrome second. Dividers are 1px and low-contrast.
2. One accent hue, used sparingly — primary actions + active state only.
3. Status is color-coded and consistent everywhere (queued / running / ok / failed).
4. Monospace = machine output. Sans = human UI.
5. Motion is fast and subtle (120–180ms). Nothing bounces.

## Color tokens (dark — default theme)
```
--bg:           #0B0D10   /* app background            */
--surface:      #14171C   /* cards, panels             */
--surface-2:    #1B1F26   /* insets, hover, inputs     */
--border:       #262B33   /* 1px hairlines             */
--text:         #E6E9EF   /* primary text              */
--text-muted:   #9AA4B2   /* secondary text            */
--text-faint:   #5C6675   /* timestamps, tertiary      */
--accent:       #6E8BFF   /* primary action, link, active */
--accent-hover: #899FFF
/* status */
--ok:      #3FB950
--running: #6E8BFF
--queued:  #9AA4B2
--failed:  #F85149
--warn:    #D29922
```

## Typography
- **UI:** Inter (system-ui fallback). Weights 400 / 500 / 600.
- **Mono:** "JetBrains Mono", ui-monospace, SFMono-Regular. Logs, JSON, run IDs, code.
- Scale (px): 12 meta · 13 body-sm · 14 body · 16 subhead · 20 h2 · 28 h1.
- Line-height 1.5 body / 1.3 headings. Headings get letter-spacing -0.01em.

## Spacing & layout
- 4px base scale: 4 · 8 · 12 · 16 · 24 · 32 · 48.
- Max content width 1200px. App sidebar 240px.
- Radius: 8px cards · 6px inputs/buttons · 4px tags.
- Elevation comes from surface tokens + borders, **not** drop shadows.

## Components
- **Buttons:** primary (accent bg, `#0B0D10` text), secondary (surface-2 bg + border), ghost (text only). 36px tall, 13–14px medium.
- **Inputs:** surface-2 bg, 1px border, 2px accent focus ring. 36px tall.
- **Cards / panels:** surface bg, 1px border, 8px radius, 16–24px padding.
- **Status pill:** colored dot + label, mapped to the status tokens.
- **Log / JSON viewer:** mono 13px on surface-2, one line per entry, timestamps in `--text-faint`.
- **Step node (builder):** card with a type glyph, name, drag handle, status dot.

## Motion
- Transitions 120–180ms ease-out. A status change pulses the dot once.
- Streaming log lines fade in over one line-height; never shift layout.

## Don'ts (flag these in QA)
- No decorative gradients, glassmorphism, or shadows-on-everything.
- No emoji as UI icons. Never more than one accent hue.
- No layout shift when logs stream in.
