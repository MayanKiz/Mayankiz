#!/usr/bin/env python3
"""Add a bottom-to-top reveal and a brief recurring glitch to a generated gh-ascii SVG."""
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

source, destination = map(Path, sys.argv[1:3])
svg = source.read_text(encoding="utf-8")
root = ET.fromstring(svg)
ns = {"svg": "http://www.w3.org/2000/svg"}
texts = root.findall(".//svg:text", ns)
if not texts:
    raise SystemExit(f"No SVG text elements found in {source}")

# Reveal the lower text rows first, progressing upward. Header text is included too.
rules = [
    """
    @keyframes print-up {
      0% { opacity: 0; transform: translateY(5px); }
      100% { opacity: 1; transform: translateY(0); }
    }
    @keyframes glitch {
      0%, 94%, 100% { filter: none; transform: translate(0, 0); }
      95% { filter: drop-shadow(2px 0 #ff3158) drop-shadow(-2px 0 #00e5ff); transform: translate(1px, 0); }
      96% { filter: drop-shadow(-2px 0 #ff3158) drop-shadow(2px 0 #00e5ff); transform: translate(-1px, 0); }
      97% { filter: none; transform: translate(0, 0); }
    }
    text {
      opacity: 0;
      animation-name: print-up;
      animation-duration: 0.12s;
      animation-timing-function: steps(2, end);
      animation-fill-mode: forwards;
    }
    """
]
count = len(texts)
for i, _ in enumerate(texts):
    # First SVG text is revealed last, so rows build upward from the bottom.
    delay = (count - i - 1) * 0.055
    rules.append(f"text:nth-of-type({i + 1}) {{ animation-delay: {delay:.3f}s; }}")
rules.append(
    f"text {{ animation-name: print-up, glitch; animation-duration: 0.12s, 4s; "
    f"animation-delay: var(--print-delay, 0s), {count * 0.055 + 0.2:.3f}s; "
    f"animation-timing-function: steps(2, end), steps(1, end); "
    f"animation-fill-mode: forwards, both; animation-iteration-count: 1, infinite; }}"
)
style = ET.Element("{http://www.w3.org/2000/svg}style")
style.text = "\n".join(rules)
root.insert(0, style)

# Explicit per-element delay makes the bottom-to-top sequence independent of CSS selectors.
for i, element in enumerate(texts):
    delay = (count - i - 1) * 0.055
    element.set("style", f"--print-delay:{delay:.3f}s")

ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
destination.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
