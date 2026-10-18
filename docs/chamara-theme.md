# Chamara Sticker ERP theme

Reference: https://chamarasticker.lk/, inspected in a browser on 18 October 2026.

- Header red: `#c8261e`; utility strip red: `#c10000`.
- Dark section: `#0c0305`; body text: `#333333`; white surfaces.
- Body font: Roboto. Navigation and headings: Source Sans Pro.
- Shared theme: `src/chamara-theme.css`, loaded after the module styles.
- Green status indicators still mean success or completion; they are independent of brand colors.

The public website supplied these brand assets, stored locally to avoid hotlinking:

- `public/brand/chamara-sticker-logo.png`: https://chamarasticker.lk/wp-content/uploads/2018/12/cropped-CHAMARA-STICKER-LOGO.png
- `public/brand/chamara-header.jpg`: https://chamarasticker.lk/wp-content/uploads/2018/12/chamara-sticker-header-back.jpg

Roboto and Source Sans Pro font files were obtained from Google Fonts and are loaded by `src/brand-fonts.css`. Their license files are included in `public/brand/`. `font-0` through `font-3` are Roboto weights 400, 500, 600, and 700; `font-4` through `font-6` are Source Sans Pro weights 400, 600, and 700.

The app retains its ERP navigation and workflow layout while using the website's logo, masthead, colors, typefaces, and compact rectangular controls. The favicon is a simple CS monogram for small browser tabs.
