"""A consistent matplotlib theme applied inside every E2B sandbox.

Charts are generated as PNGs by LLM-written matplotlib code. Left to matplotlib's
defaults they look dated and inconsistent (the classic tab10 blue, heavy black
spines, no title styling). This module sets rcParams once per sandbox kernel so
every chart shares one clean, accessible look without the model having to style
anything itself.

Palette is the validated, colorblind-safe categorical set from the data-viz
design system (worst adjacent CVD ΔE 24.2, well clear of the ≥12 target). Charts
render on the light chart surface (#fcfcfb) because a PNG has a fixed background;
the frontend presents them on a matching light plate.
"""

# Categorical slots, in the CVD-safety-optimised order. Do not re-order.
CATEGORICAL_COLORS = [
    "#2a78d6",  # blue
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
    "#e87ba4",  # magenta
    "#eb6834",  # orange
]

# Executed once in the sandbox kernel; rcParams persist for all later chart code.
CHART_THEME_BOOTSTRAP = f"""
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from cycler import cycler

    _ANALYTIKA_COLORS = {CATEGORICAL_COLORS!r}
    plt.rcParams.update({{
        "figure.figsize": (7.0, 4.5),
        "figure.dpi": 110,
        "figure.facecolor": "#fcfcfb",
        "figure.autolayout": True,
        "axes.facecolor": "#fcfcfb",
        "savefig.facecolor": "#fcfcfb",
        "savefig.bbox": "tight",
        "axes.edgecolor": "#c3c2b7",
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#e1e0d9",
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": "#0b0b0b",
        "axes.titlepad": 12,
        "axes.titlelocation": "left",
        "axes.labelsize": 10.5,
        "axes.labelcolor": "#52514e",
        "axes.labelpad": 6,
        "xtick.color": "#898781",
        "ytick.color": "#898781",
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "text.color": "#0b0b0b",
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
        "font.size": 10.5,
        "axes.prop_cycle": cycler(color=_ANALYTIKA_COLORS),
        "legend.frameon": False,
        "legend.fontsize": 9.5,
        "lines.linewidth": 2.0,
        "lines.markersize": 6,
        "patch.edgecolor": "#fcfcfb",
        "patch.linewidth": 0.6,
        "scatter.edgecolors": "#fcfcfb",
    }})
except Exception as _theme_err:
    print("[chart_theme] could not apply theme:", _theme_err)
"""
