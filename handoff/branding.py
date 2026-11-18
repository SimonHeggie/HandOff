"""HandOff public identity. Keep all user-facing product naming here.

The installed Blender package is ``handoff``. Historical projects may still
contain old custom-property and metadata keys, which remain readable.
"""
NAME = "HandOff"
SUBTITLE = "Automated asset production, interchange and deployment for Blender"
TAGLINE = "Hit render, go home."
SHORT_DESCRIPTION = (
    "Prepare layered artwork, animation, asset packages and production "
    "deliverables automatically when rendering from Blender."
)
OVERVIEW = (
    f"{NAME} is a Blender add-on for producing editable art sources and "
    "repeatable asset deliveries. The long-term scope includes game and "
    "server deployment, marketing outputs and web services."
)
STATUS = "Alpha - under active development"
VERSION_INFO = (0, 7, 53)
VERSION = '.'.join(map(str, VERSION_INFO))
LOG_PREFIX = '[' + NAME + ']'

AUTHOR = "Simon Heggie"
GITHUB = "https://github.com/SimonHeggie/HandOff"
LINKEDIN = "https://www.linkedin.com/in/simon-heggie-94a1ba40/"
