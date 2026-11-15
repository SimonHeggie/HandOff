"""Comp-IO public identity. Keep all user-facing product naming here.

The installed Blender module remains ``blend_psd_tools`` for compatibility
with existing .blend files and saved add-on preferences.
"""
NAME = "Comp-IO"
SUBTITLE = "Layered Asset Interchange & Publishing for Blender"
TAGLINE = "One render. Every deliverable."
SHORT_DESCRIPTION = (
    "Render once; publish layered PSD/PSB, OCA, Spine-ready artwork, "
    "image sequences and production assets from Blender's compositor."
)
OVERVIEW = (
    f"{NAME} is a free, open-source Blender add-on extending the compositor "
    "with layered document interchange and repeatable asset publishing. "
    "Prepare editable artwork for animators, developers, illustrators and "
    "marketing teams without manually rebuilding every deliverable."
)
STATUS = "Alpha - under active development"
VERSION_INFO = (0, 7, 50)
VERSION = '.'.join(map(str, VERSION_INFO))
LOG_PREFIX = '[' + NAME + ']'

AUTHOR = "Simon Heggie"
GITHUB = "https://github.com/SimonHeggie"
LINKEDIN = "https://www.linkedin.com/in/simon-heggie-94a1ba40/"
