"""HandOff public identity. Keep all user-facing product naming here.

The installable package is ``handoff``; legacy RNA/operator identifiers remain
compatible with existing saved Blender projects.
"""
NAME = "HandOff"
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
VERSION_INFO = (0, 7, 53)
VERSION = '.'.join(map(str, VERSION_INFO))
LOG_PREFIX = '[' + NAME + ']'

AUTHOR = "Simon Heggie"
GITHUB = "https://github.com/SimonHeggie/HandOff"
LINKEDIN = "https://www.linkedin.com/in/simon-heggie-94a1ba40/"
