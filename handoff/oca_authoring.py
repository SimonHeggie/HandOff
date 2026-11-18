"""Explicit OCA authoring, distinct from transparency already baked by Blender."""
import math
from pathlib import Path


def properties(owner):
    def value(name,default):return getattr(owner,'handoff_oca_'+name,owner.get('handoff_oca_'+name,default))
    result=dict(opacity=float(value('opacity',1)),frameOpacity=float(value('frame_opacity',1)),
        inheritAlpha=bool(value('inherit_alpha',False)),blend=str(value('blend','SOURCE')),
        isolate=bool(value('isolate',False)),sourceLayer=str(value('source_layer','')),
        external=str(value('external_document','')),sourceID=str(value('external_id','')),timeOffset=int(value('time_offset',0)),
        keepIndependent=bool(value('keep_independent',False)),offset=list(value('offset',(0,0))))
    for key in ('opacity','frameOpacity'):
        if not math.isfinite(result[key]) or not 0<=result[key]<=1:raise ValueError('OCA '+key+' must be in 0..1')
    return result


def capture(scene,source_layers,collection_path):
    import bpy
    views=[v for v in source_layers if v is not None]
    owners=[properties(v) for v in views]
    if len(owners)>1 and any(v!=owners[0] for v in owners[1:]):raise ValueError('OCA authoring properties differ across combined source View Layers')
    values=owners[0] if owners else {}
    if values.get('external'):values['external']=bpy.path.abspath(values['external'])
    groups={}
    for name in collection_path.split('/'):
        collection=bpy.data.collections.get(name)
        if collection:groups[name]=properties(collection)
    return dict(oca_authored=values,oca_authored_groups=groups,
        oca_authoring_scene=scene.name,oca_authoring_views=[v.name for v in views],
        oca_authoring_sources=[(getattr(v,'id_data',scene).name,v.name) for v in views])


def capture_frame(entry):
    import bpy
    result=dict(entry)
    scene=bpy.data.scenes.get(entry.get('oca_authoring_scene',''))
    if scene:
        views=[bpy.data.scenes.get(owner).view_layers.get(name) for owner,name in entry.get('oca_authoring_sources',[(scene.name,n) for n in entry.get('oca_authoring_views',[])]) if bpy.data.scenes.get(owner)]
        result.update(capture(scene,views,entry.get('collection_path','')))
    return result


_REGISTERED=[]

def register():
    import bpy
    from bpy.props import FloatProperty,BoolProperty,StringProperty,IntProperty,EnumProperty,FloatVectorProperty
    from xml.etree import ElementTree as ET
    modes=ET.parse(Path(__file__).parent/'compatibility/blend_modes.xml').getroot().findall('./modes/mode')
    enum=[('SOURCE','From Source','Keep existing suffix/group blend handling')]+[(n.get('oca'),n.get('oca').replace('_',' ').title(),'Explicit OCA paint blend; target application support varies') for n in modes]
    # These are optional publishing instructions. They never modify rendered alpha.
    factories=dict(opacity=lambda:FloatProperty(name='Export Opacity',min=0,max=1,default=1,options=set(),description='Additional editable OCA layer/group opacity; rendered source alpha is retained'),
      frame_opacity=lambda:FloatProperty(name='Frame Opacity',min=0,max=1,default=1,description='Additional OCA frame opacity; can be keyframed independently of rendered transparency'),
      inherit_alpha=lambda:BoolProperty(name='Inherit Alpha',default=False),
      blend=lambda:EnumProperty(name='OCA Blend',items=enum,default='SOURCE'),
      isolate=lambda:BoolProperty(name='Isolate Group',default=False),
      source_layer=lambda:StringProperty(name='Source View Layer',description='Explicit OCA clone source; choose a uniquely connected source View Layer. Leave empty to use verified linked GP data'),
      external_document=lambda:StringProperty(name='Nested OCA Document',subtype='FILE_PATH',description='Publish this input as a standard external OCA document layer; referenced assets are copied into the project'),
      external_id=lambda:StringProperty(name='Source Layer ID',description='Optional layer UUID inside the nested document; empty imports the whole document'),
      time_offset=lambda:IntProperty(name='Time Offset',default=0,description='Shift a clone/nested source by this many frames'),
      offset=lambda:FloatVectorProperty(name='Reference Offset (px)',size=2,default=(0,0),description='Translation of the referenced source in document pixels'),
      keep_independent=lambda:BoolProperty(name='Keep Independent',default=False,description='Keep this View Layer as independent artwork instead of automatic linked GP clone conversion'))
    for kind in (bpy.types.ViewLayer,bpy.types.Collection):
        for key,factory in factories.items():
            name='handoff_oca_'+key
            if not hasattr(kind,name):setattr(kind,name,factory());_REGISTERED.append((kind,name))
    bpy.types.Scene.handoff_oca_background_color=FloatVectorProperty(name='OCA Background',size=4,subtype='COLOR_GAMMA',min=0,max=1,default=(0,0,0,0),description='Independent OCA document background; alpha zero is transparent')
    _REGISTERED.append((bpy.types.Scene,'handoff_oca_background_color'))
    class HANDOFF_PT_oca_layer(bpy.types.Panel):
        bl_label='HandOff — OCA Authoring';bl_idname='HANDOFF_PT_oca_layer';bl_space_type='PROPERTIES';bl_region_type='WINDOW';bl_context='view_layer';bl_options={'DEFAULT_CLOSED'}
        def draw(self,context):
            layout=self.layout;view=context.view_layer
            for prop in ('opacity','frame_opacity','inherit_alpha','blend','keep_independent'):layout.prop(view,'handoff_oca_'+prop)
            layout.prop_search(view,'handoff_oca_source_layer',context.scene,'view_layers')
            layout.prop(view,'handoff_oca_external_document')
            if view.handoff_oca_external_document:layout.prop(view,'handoff_oca_external_id')
            if view.handoff_oca_external_document or view.handoff_oca_source_layer:
                layout.prop(view,'handoff_oca_time_offset');layout.prop(view,'handoff_oca_offset')
            layout.prop(context.scene,'handoff_oca_background_color')
    class HANDOFF_PT_oca_collection(bpy.types.Panel):
        bl_label='HandOff — OCA Group';bl_idname='HANDOFF_PT_oca_collection';bl_space_type='PROPERTIES';bl_region_type='WINDOW';bl_context='collection';bl_options={'DEFAULT_CLOSED'}
        @classmethod
        def poll(cls,context):return context.collection is not None
        def draw(self,context):
            for prop in ('opacity','inherit_alpha','blend','isolate'):self.layout.prop(context.collection,'handoff_oca_'+prop)
    for cls in (HANDOFF_PT_oca_layer,HANDOFF_PT_oca_collection):bpy.utils.register_class(cls);_REGISTERED.append(cls)


def unregister():
    import bpy
    for item in reversed(_REGISTERED):
        if isinstance(item,tuple):
            kind,name=item
            if hasattr(kind,name):delattr(kind,name)
        else:bpy.utils.unregister_class(item)
    _REGISTERED.clear()


def refresh_frames(job):
    """Refresh independent OCA metadata on retry, without touching cached pixels."""
    import bpy
    current=job.get('manifest',[]);saved={}
    try:
        for captured in job.get('oca_frames',[]):
            for entry in current:
                for owner,_ in entry.get('oca_authoring_sources',[]):
                    scene=bpy.data.scenes.get(owner)
                    if scene:
                        saved.setdefault(owner,scene.frame_current)
                        if scene.frame_current!=captured['frame']:scene.frame_set(captured['frame'])
            old=captured.get('manifest',[])
            if len(old)!=len(current):raise ValueError('OCA source layout changed; render again')
            for snapshot,entry in zip(old,current):
                updated=capture_frame(entry)
                for key in ('oca_authored','oca_authored_groups','oca_authoring_scene','oca_authoring_sources','oca_authoring_views','oca_source_id'):
                    if key in updated:snapshot[key]=updated[key]
    finally:
        for owner,frame in saved.items():
            scene=bpy.data.scenes.get(owner)
            if scene and scene.frame_current!=frame:scene.frame_set(frame)
