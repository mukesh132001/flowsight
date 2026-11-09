"""One colour system for the Excel pack, the deck and the dashboard.

Categorical slots and status colours follow a colour-blind-validated reference palette
(slots 1-3 pass every check in light and dark mode). Status colours always travel with an
icon and a word, never colour alone.
"""

COLORS = {
    "ink": "#0b0b0b",
    "ink_2": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "surface": "#fcfcfb",
    "header": "#184f95",           # blue ramp step 600 - table headers
    "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "negative": "#e34948",          # diverging pole for outflows
    "deemph": "#c3c2b7",            # de-emphasis gray for context bars
    "div_pos": "#2a78d6", "div_mid": "#f0efec", "div_neg": "#e34948",
    "rag": {
        "GREEN": {"solid": "#0ca30c", "fill": "#dcf3dc", "text": "#006300"},
        "AMBER": {"solid": "#fab219", "fill": "#fff1cc", "text": "#7a4f00"},
        "RED": {"solid": "#d03b3b", "fill": "#f9dcdc", "text": "#a32424"},
        "INFO": {"solid": "#898781", "fill": "#f0efec", "text": "#52514e"},
    },
}

RAG_LABEL = {"GREEN": "✓ On track", "AMBER": "▲ Watch", "RED": "✕ Off track", "INFO": "– Info"}
