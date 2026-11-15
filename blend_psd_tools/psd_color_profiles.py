"""Embed colour-space information in PSD/PSB image resources.

PNG8/16 caches saved as display-referred images normally use sRGB encoding.
EXR32 caches are scene-linear HDR: a linear RGB profile is needed instead.
Never attach display sRGB to linear EXR data.
"""

try:
    from .branding import LOG_PREFIX
except ImportError:
    from branding import LOG_PREFIX
import os
from pathlib import Path


def attach_document_profile(psd, depth, job, source=None):
    from psd_tools.constants import Resource
    from psd_tools.psd.image_resources import ImageResource
    profile = None
    info = ''
    extension = str(job.get('extension', '.png')).lower()
    if depth in (8, 16) and extension == '.png':
        if source is not None:
            # Honour an ICC profile already embedded in Blender's cache.
            from PIL import Image
            with Image.open(source) as png:
                profile = png.info.get('icc_profile')
        if profile:
            info = 'embedded source PNG ICC profile'
        else:
            from PIL import ImageCms
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
            info = 'sRGB IEC61966-2.1 (display-referred PNG)'
    elif depth == 32 and extension == '.exr':
        # The bundled profile matches standard Blender scene-linear Rec.709
        # primaries, D65. A custom OCIO config can select a different gamut.
        if os.environ.get('OCIO'):
            print(f'{LOG_PREFIX} COLOR WARNING: OCIO override detected. The '
                  '32-bit EXR gamut is unknown, so no RGB ICC profile was assigned.', flush=True)
        else:
            profile = (Path(__file__).resolve().parent / 'profiles' / 'linear_srgb_d65.icc').read_bytes()
            info = 'linear RGB (Rec.709/sRGB primaries, D65) for 32-bit HDR'
    else:
        print(f'{LOG_PREFIX} COLOR WARNING: no automatic ICC profile for '
              f'{depth}-bit {extension} cache. Linear data must be colour-converted '
              'before assigning a display profile.', flush=True)
    if profile:
        if profile[36:40] != b'acsp':
            raise ValueError('Invalid ICC profile bytes')
        psd.image_resources[Resource.ICC_PROFILE] = ImageResource(key=Resource.ICC_PROFILE, data=profile)
        print(f'{LOG_PREFIX} PSD ICC:', info, '| bytes:', len(profile), flush=True)
    return info
