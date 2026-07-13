"""The response envelope every tool returns.

An Envelope is a pure, testable object (headline / data / facts / caveats / meta,
plus optional figure and a private `values` dict of raw numbers for unit tests). The
server serialises it to MCP content: one text block + one PNG image block.
"""
from dataclasses import dataclass, field

import pandas as pd

import core

try:  # Image is only needed when actually serving; keep imports test-friendly
    from fastmcp.utilities.types import Image
except Exception:  # pragma: no cover
    Image = None


@dataclass
class Envelope:
    headline: str
    facts: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    data: pd.DataFrame | None = None          # small (<=10 rows), pre-formatted cells
    caveats: list = field(default_factory=list)
    fig: object | None = None                 # a plotly figure; rendered to PNG on serialise
    values: dict = field(default_factory=dict)  # raw numbers for tests; NOT shown to the LLM
    is_error: bool = False

    # -- text rendering ------------------------------------------------------
    def to_text(self) -> str:
        parts = [f"HEADLINE: {self.headline}"]
        if self.data is not None and len(self.data):
            parts.append("\nDATA:\n" + _df_to_md(self.data))
        if self.facts:
            parts.append("\nFACTS:\n" + "\n".join(f"- {f}" for f in self.facts))
        parts.append("\nCAVEATS:\n" + (
            "\n".join(f"- {c}" for c in self.caveats) if self.caveats else "- none"))
        if self.meta:
            parts.append("\nMETA:\n" + "\n".join(f"- {k}: {v}" for k, v in self.meta.items()))
        return "\n".join(parts)

    # -- MCP content (text, plus an image block only when there is a figure) --
    def to_content(self):
        text = self.to_text()
        if self.fig is not None and Image is not None:
            png = core.render_png(self.fig)
            return [text, Image(data=png, format="png")]
        return text   # bare string -> a single TextContent block (no JSON wrapping)


def _df_to_md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |",
             "| " + " | ".join("---" for _ in cols) + " |"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def error_envelope(message, valid_options=None, meta=None):
    """A graceful, self-correcting error: an answer the LLM can act on, not an exception."""
    facts = []
    if valid_options:
        facts.append("Valid options: " + ", ".join(str(o) for o in valid_options))
    return Envelope(headline=message, facts=facts, meta=meta or {}, is_error=True)
