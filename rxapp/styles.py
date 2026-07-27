"""Centralised design tokens for the WiseWombat UI.

Import `from rxapp import styles` and reference as `styles.TOKEN_NAME`.
Never hard-code hex values in component files - add a token here instead.

The CSS layer (assets/custom.css) handles Radix component overrides;
these constants are for explicit inline styles where CSS cannot reach.
"""

# ── Text ────────────────────────────────────────────────────────────────
TEXT_PRIMARY   = "#111827"   # headings, body
TEXT_SECONDARY = "#374151"   # labels, table cells
TEXT_MUTED     = "#6b7280"   # helper text, meta
TEXT_FAINT     = "#9ca3af"   # placeholders, timestamps

# ── Backgrounds ─────────────────────────────────────────────────────────
BG_PAGE        = "#f5f6f8"   # outer page / content area background
BG_SURFACE     = "#ffffff"   # cards, panels, sidebar
BG_SUBTLE      = "#f3f4f6"   # code bg, category badge fill
BG_HOVER       = "#f0f1f2"   # neutral hover (nav items, header buttons)
BG_ROW_HOVER   = "#f8f9fa"   # table row hover

# ── Borders ─────────────────────────────────────────────────────────────
BORDER_DEFAULT = "#e4e5e7"   # cards, dividers, inputs
BORDER_MUTED   = "#d1d5db"   # category badges, subtle outlines
BORDER_STRONG  = "#c7c8ca"   # hover state borders

# ── Teal palette (primary accent) ───────────────────────────────────────
TEAL_50        = "#f0fdfa"   # very light teal (asset row hover, count card)
TEAL_100       = "#ccfbf1"   # light teal (nav active bg, icon circles, teal badges)
TEAL_300       = "#5eead4"   # teal border (user message bubble, badge outlines)
TEAL_600       = "#0d9488"   # primary teal (icons, active nav border)
TEAL_700       = "#0f766e"   # dark teal text (active nav label, counts)
TEAL_ACCENT    = "teal"      # Radix color_scheme name

TEAL_TOOL_BG   = "rgba(13, 148, 136, 0.07)"   # tool call card background
TEAL_MSG_BG    = "rgba(13, 148, 136, 0.12)"   # user chat bubble background

# Aliases for icon circle (login page + sidebar brand)
TEAL_ICON_BG   = TEAL_100
TEAL_ICON_FG   = TEAL_600

# ── Navigation ──────────────────────────────────────────────────────────
NAV_TEXT_ACTIVE   = TEAL_700       # active nav item text/icon
NAV_TEXT_INACTIVE = "#444c56"      # inactive nav item text/icon
NAV_BG_ACTIVE     = TEAL_100       # active nav item background
NAV_BORDER_ACTIVE = TEAL_600       # active nav item left border

# ── Status: green ───────────────────────────────────────────────────────
GREEN_600      = "#16a34a"   # success text, agent-ready dot, upcoming count
GREEN_BG       = "#f0fff4"   # upcoming stat card background
GREEN_BORDER   = "#86efac"   # upcoming stat card border

# ── Status: orange ──────────────────────────────────────────────────────
ORANGE_600     = "#ea580c"   # due-soon text, approval icon
ORANGE_BG      = "#fff8f5"   # due-soon stat card background
ORANGE_BORDER  = "#fdba74"   # due-soon stat card border

ORANGE_APPROVAL_BORDER = "#fb923c"                              # approval card border
ORANGE_APPROVAL_BG     = "color-mix(in srgb, #ea580c 6%, transparent)"  # approval card fill

# ── Status: red ─────────────────────────────────────────────────────────
RED_600        = "#dc2626"   # overdue text, error
RED_BG         = "#fff5f5"   # overdue stat card background
RED_BORDER     = "#fca5a5"   # overdue stat card border

# ── Status: dark variants (CSS override / accessible text on colored bg) ────
GREEN_800      = "#166534"   # dark green text for green badges/callouts
RED_800        = "#991b1b"   # dark red text for red badges
TEAL_900       = "#115e59"   # very dark teal text for teal badges

# ── Shadows ─────────────────────────────────────────────────────────────
SHADOW_CARD    = "0 4px 24px 0 rgba(0,0,0,0.07)"   # login card / floating panel

# ── Reusable badge style dicts ──────────────────────────────────────────
BADGE_TEAL = {
    "background": TEAL_100,
    "color": TEAL_700,
    "border": f"1px solid {TEAL_300}",
}
BADGE_CATEGORY = {
    "background": BG_SUBTLE,
    "color": TEXT_SECONDARY,
    "border": f"1px solid {BORDER_MUTED}",
}
