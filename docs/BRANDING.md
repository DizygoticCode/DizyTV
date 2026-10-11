# DizyTV branding

The DizyTV mark carries the existing DizyChat palette and bold lettering into a retro CRT television, with **DIZY TV** inside the screen.

## Project asset

- **Master:** [dizytv-logo.png](../assets/branding/dizytv-logo.png)
- **Background:** transparent PNG; retain the alpha channel.
- **README display:** 280 pixels wide.
- **Brand colours:** muted green, charcoal and cream, based on the DizyChat reference.
- **Use:** README, desktop window branding and Android launcher/app branding. Native build scripts generate Windows ICO and Mac ICNS assets from this master; all three platform package jobs have passed. Small-icon legibility and launcher presentation still need physical-device checks.

## Reference and generation

The reference was [DizyChat's existing logo](https://github.com/DizygoticCode/dizychat-server/blob/main/public/logo.svg), blob `35065bd18c78ffc0a9877d35791fe9fcb864dff5`. It was rendered as a PNG reference without changing its design.

The new mark was created on 11 October 2026 using the built-in image-generation tool with a transparent background. It is a raster master with a vector-like illustration style, not an editable vector source.

## Generation prompt

```text
Use case: logo-brand.
Asset type: the DizyTV project logo for a GitHub README and native application branding.
Primary request: Create one polished DIZY TV logo based on the supplied DizyChat brand reference, placing the new lettering INSIDE a retro television.
Input image 1 is a BRAND STYLE REFERENCE, not a finished edit target. Preserve its recognisable bold, chunky uppercase lettering, cream/off-white, muted green and charcoal palette, and green horizontal-bar motif. Replace all CHAT wording with TV.
Subject and composition: a front-facing compact vintage CRT television with a softly rounded rectangular cabinet, a curved rectangular screen, simple tuning knobs and a speaker grille on the right, small feet and two short antenna rods. Inside the screen place the exact text "DIZY" above "TV" in very large, clean, bold uppercase block letters. The complete wordmark must read "DIZY TV", correctly spelled D-I-Z-Y T-V. Cream letters with a subtle dark outline, green horizontal accents above and below the lettering, and a charcoal/green television cabinet. Keep the lettering dominant and easy to read at README size.
Style: crisp, clean vector-like brand illustration with restrained dimensional detail, balanced outlines and rounded edges. Not a photo, not a busy scene. One self-contained logo, centred in a square image with even transparent margins and comfortable clearance around antenna and feet. Retain the muted green/cream/charcoal brand colours from the reference.
Background: genuine transparent alpha outside the television; no white rectangle, no checkerboard baked into the pixels, no backdrop, no floor or cast shadow.
Constraints: only the text "DIZY TV"; no CHAT, slogans, watermarks, extra logos, extra panels or alternate versions.
```
