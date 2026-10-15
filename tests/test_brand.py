"""The website, README and film must share the extracted ses palette."""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_brand_tokens_match_css_and_film():
    tokens = json.loads((ROOT / "brand/tokens.json").read_text())
    css = (ROOT / "brand/tokens.css").read_text()
    rust = (ROOT / "marketing/film/src/identity.rs").read_text()
    for key, color in tokens["colors"].items():
        assert re.fullmatch(r"#[a-f0-9]{6}", color)
        assert f"--ses-{key}: {color};" in css
        assert f'"{color}"' in rust
    for font in tokens["fonts"].values():
        assert font in css and font in rust


def test_identity_svgs_are_accessible_and_need_no_fonts():
    ns = {"svg": "http://www.w3.org/2000/svg"}
    for path in (ROOT / "brand").glob("*.svg"):
        svg = ET.parse(path).getroot()
        assert svg.attrib["role"] == "img"
        assert svg.find("svg:title", ns).text
        assert not svg.findall(".//svg:text", ns), "GitHub SVGs need outlined lettering"
        assert svg.findall(".//svg:path", ns)
