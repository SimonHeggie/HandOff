"""Direct XML-backed tag mappings for Comp-IO.

No bpy, no network access, no scene changes. The worker and Blender UI share
this API; destination names are created on copies of the export manifest.
"""
from functools import lru_cache
from pathlib import Path
import re
import xml.etree.ElementTree as ET

REGISTRY_VERSION = 1
ROOT = Path(__file__).resolve().parent / 'compatibility'
PROFILES = ('AUTO', 'SPINE', 'GENERATOR', 'OCA', 'PASSTHROUGH')

@lru_cache(maxsize=1)
def registry():
    root = ET.parse(ROOT / 'tags.xml').getroot()
    if root.tag != 'tagRegistry' or root.get('schema') != 'explicit-tag-mapping-v1':
        raise ValueError('Unrecognised bundled tags.xml schema')
    behaviors = {b.get('id'): b for b in root.findall('./behaviors/behavior')}
    if len(behaviors) != 26:
        raise ValueError('Incomplete bundled tag registry')
    rules = []
    for entry in root.findall('./sourceTokens/token'):
        form = entry.attrib['template']
        # Only explicit XML patterns may be parsed: no substring based guessing.
        pat = re.escape(form).replace(r'\{value\}', r'(?P<value>[^\]\r\n]+)')
        if form.startswith('.'):
            pat = pat + r'(?=\.|$)'
        rules.append((re.compile(pat, re.I), entry.get('profile'), entry.get('behavior'), form))
    rules.sort(key=lambda r: (-len(r[3]), r[3]))
    return behaviors, rules

@lru_cache(maxsize=1)
def blend_registry():
    root = ET.parse(ROOT / 'blend_modes.xml').getroot()
    if root.tag != 'blendModeRegistry':
        raise ValueError('Invalid blend registry')
    return {e.get('oca'): e for e in root.findall('./modes/mode')}


def effective_profile(selected, output_format):
    if selected not in PROFILES:
        selected = 'AUTO'
    if selected == 'AUTO':
        # Legacy choice from <=0.7.9. Removed from the UI: no implicit rewriting.
        return 'PASSTHROUGH'
    return selected


def find_tokens(text):
    """Return nonoverlapping explicit tokens (start, end, text, behavior, origin, value).
    Values are parsed only where XML declares a {value} placeholder.
    """
    _, rules = registry()
    found = []
    for pattern, source, behavior, template in rules:
        for match in pattern.finditer(text):
            if any(not (match.end() <= prior[0] or match.start() >= prior[1]) for prior in found):
                continue
            found.append((match.start(), match.end(), match.group(0), behavior,
                          source, match.groupdict().get('value')))
    return sorted(found)


@lru_cache(maxsize=1)
def generator_asset_regex():
    root = ET.parse(ROOT / 'tags.xml').getroot()
    rule = root.find("./generatorGrammar/rule[@id='generator-spec']")
    if rule is None:
        raise ValueError('Missing Generator filename grammar')
    return re.compile(rule.attrib['regex'], re.I)


def _emission(behavior, profile, source_text, value):
    behaviors, _ = registry()
    for target in behaviors[behavior].findall('target'):
        if target.get('profile') != profile.lower():
            continue
        equivalence = target.get('equivalence', 'none')
        template = target.get('emit')
        if not template or equivalence in ('none', 'metadata'):
            return None, equivalence
        if '{' in template:
            if value is None:
                # For optional Spine parameters, emit the non-parametric tag.
                if profile == 'SPINE' and template.startswith('['):
                    return '[' + template[1:].split(':',1)[0] + ']', equivalence
                return None, equivalence
            template = template.replace('{name}', value).replace('{number}', value).replace('{mode}', value).replace('{degrees}', value).replace('{pattern}', value).replace('{value}', value)
        return template, equivalence
    return None, 'none'


def translate_label(display_name, source_name, profile, scope='layer'):
    """Translate a COPY of an output name; never change scene names.

    display_name is the existing exporter group/layer name (including -A split
    if required), source_name contains the authored tag syntax.
    Returns (translated_name, list_of_explicit_warnings).
    """
    if profile == 'AUTO':
        profile = 'SPINE'
    if profile == 'PASSTHROUGH':
        # Preserve manual directives, while retaining already calculated
        # group split identities in the display name.
        suffixes = [t[2] for t in find_tokens(source_name) if t[2] not in display_name]
        return (display_name + ((' ' if display_name and suffixes[0].startswith('[') else '') + ''.join(suffixes) if suffixes else ''), [])
    token_list = find_tokens(source_name)
    label = display_name
    extras = []
    warnings = []
    for _, _, literal, behavior, origin, value in token_list:
        if literal in label:
            label = label.replace(literal, '')
        # Existing Blender .ignore is an export-selection instruction; the
        # 0.7.7 source filter continues to handle inclusion unchanged.
        if behavior == 'exclude' and origin == 'blender':
            continue
        if behavior == 'merge' and profile == 'SPINE' and scope != 'group':
            warnings.append(f'{literal}: Spine [merge] operates on groups; layer conversion not safe, original tag preserved')
            replacement = literal
        elif origin.upper() == profile:
            replacement = literal
        else:
            replacement, strength = _emission(behavior, profile, literal, value)
            if replacement is None:
                warnings.append(f'{literal}: no safe {profile} conversion for {behavior}; original tag preserved')
                replacement = literal
            elif strength in ('approximation', 'partial'):
                warnings.append(f'{literal}: {profile} conversion is {strength} ({replacement})')
        if replacement not in extras:
            extras.append(replacement)
    # Generator specifications are expressions, not dot-tags. Their exact
    # recognition pattern comes from XML; do not infer file syntax from prose.
    if profile != 'GENERATOR':
        for match in generator_asset_regex().finditer(source_name):
            warnings.append(f'{match.group(0)}: Photoshop Generator asset instruction has no safe {profile} name-tag equivalent; original text preserved')
    # Unrecognised square brackets may be vendor extensions; never delete them.
    known_spans = [(begin,end) for begin,end,*_ in token_list]
    for match in re.finditer(r'\[[A-Za-z!][^\]\r\n]*\]', source_name):
        if not any(a <= match.start() and match.end() <= b for a,b in known_spans):
            warnings.append(f'{match.group(0)}: unknown tag; preserved unchanged')
    label = label.strip(' \t')
    for extra in extras:
        if extra.startswith('[') or extra.startswith('_'):
            label += (' ' if label else '') + extra
        else:
            label += extra
    return label or 'Layer', warnings


def preview(name, selected_profile, fmt, scope='layer'):
    chosen = effective_profile(selected_profile, fmt)
    # Names for preview are the actual socket or collection names; no scene mutation.
    return translate_label(name, name, chosen, scope)


def check():
    behaviors, rules = registry()
    return len(behaviors), len(rules), len(blend_registry())
