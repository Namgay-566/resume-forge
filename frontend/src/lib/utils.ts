import { createCn } from "cn/config"

/** Class merging that knows the design system's custom scales (see index.css @theme).
 * Without this, `text-h2` would be read as a text *color* and silently cancel
 * `text-muted-foreground` (or vice versa) when classes are merged. */
export const cn = createCn({
  extend: {
    classGroups: {
      "font-size": [{ text: ["display", "h1", "h2", "h3", "h4"] }],
      shadow: [{ shadow: ["xs", "sm", "md", "lg", "xl"] }],
    },
  },
})
