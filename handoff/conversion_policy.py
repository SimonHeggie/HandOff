"""Read the same feature capability CSV used by the exporter and manual."""
import csv
from functools import lru_cache
from pathlib import Path

PATH=Path(__file__).parent/'compatibility/vector_features.csv'
REPRESENTATIONS=frozenset({'NATIVE_EDITABLE','NATIVE_WITH_EFFECTS','SHARED_SMART_OBJECT',
    'EMBEDDED_SMART_OBJECT','LINKED_SMART_OBJECT','RASTER_WITH_SOURCE','APPROXIMATED','PARTIAL','SKIPPED','FAILED'})

@lru_cache(maxsize=1)
def capabilities():
    with PATH.open(encoding='utf-8',newline='') as stream:rows=list(csv.DictReader(stream))
    if len({r['feature'] for r in rows})!=len(rows):raise ValueError('Duplicate conversion feature')
    return {row['feature']:row for row in rows}

def automatic_eligible(feature,target='photoshop'):
    """Conservative eligibility for new native mappings, not SVG source links."""
    try:row=capabilities()[feature]
    except (OSError,ValueError,KeyError):return False
    return row['psd_writer']=='implemented' and row['reader_validation']=='passed' and row.get(target+'_validation')=='passed'

def record(job,obj,representation,reason='',**extra):
    if representation not in REPRESENTATIONS:raise ValueError('Unknown publication representation')
    report=dict(source_object=obj.get('name',''),source=obj.get('source_metadata',{}),
        source_collections=obj.get('collection_parts',[]),representation=representation,
        source_view_layer=job.get('_publication_view_layer',''),
        source_scene=obj.get('source_metadata',{}).get('scene_name',job.get('source_scene','')),
        output_format=job.get('format','PSD'),target=('PSD'
            if job.get('format','PSD') in ('PSD','PSB') else 'GENERIC_SVG'),
        destination_layer=obj.get('name',''),reason=reason,
        source_feature=obj.get('svg_kind','GP' if 'layers' in obj else 'raster'),
        source_svg=job.get('_publication_source_svg',''),features_preserved=[],
        features_approximated=[],features_lost=[],validation='target editor unverified',
        shared_instance=obj.get('svg_instance',{}).get('key',''))
    report.update(extra)
    job.setdefault('_publication',[]).append(report)
    try:
        from .branding import LOG_PREFIX
    except ImportError:
        from branding import LOG_PREFIX
    print(LOG_PREFIX,'PUBLISH:',report['source_object'] or report['destination_layer'],
          representation,'|',reason,flush=True)
    return report
