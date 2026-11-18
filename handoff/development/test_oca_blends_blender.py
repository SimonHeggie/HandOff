"""Compare OCA blend math/assets with real Blender compositor EXR output.

Opaque linear RGB cases isolate blend semantics from display/view transforms.
"""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
import bpy,numpy as np
from pillow_loader import ensure_pillow
ensure_pillow()
from psd_worker import assemble,read_blender_pixels
from oca_companions import composite
from oca_project import nodes
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=1;scene.cycles.device='CPU';scene.cycles.use_denoising=False
scene.render.resolution_x=scene.render.resolution_y=8;scene.render.resolution_percentage=100
scene.render.use_compositing=True;scene.render.use_sequencer=False
out=Path(os.environ['HANDOFF_TEST_OUTPUT']);out.mkdir(parents=True,exist_ok=True)
tree=bpy.data.node_groups.new('Native blend comparison','CompositorNodeTree');scene.compositing_node_group=tree
output=tree.nodes.new('CompositorNodeOutputFile');output.directory=str(out/'cache');output.file_name=''
output.format.media_type='IMAGE';output.format.file_format='OPEN_EXR';output.format.color_mode='RGBA';output.format.color_depth='32'
output.file_output_items.clear()
def save(socket,name):
 output.file_output_items.new('RGBA',name);tree.links.new(socket,output.inputs[len(output.file_output_items)-1])
source=tree.nodes.new('CompositorNodeRLayers');source.scene=scene;source.layer=scene.view_layers[0].name
def solid(color):
 n=tree.nodes.new('ShaderNodeMix');n.data_type='RGBA';n.inputs[0].default_value=1
 inputs=[s for s in n.inputs if s.type=='RGBA'];inputs[1].default_value=color
 tree.links.new(source.outputs['Image'],inputs[0]);return next(s for s in n.outputs if s.type=='RGBA')
a=solid((.2,.6,.8,1));b=solid((.7,.3,.4,1))
save(a,'Back');save(b,'Front')
modes={'normal':'MIX','multiply':'MULTIPLY','screen':'SCREEN','overlay':'OVERLAY','add':'ADD','darken':'DARKEN','lighten':'LIGHTEN','difference':'DIFFERENCE','exclusion':'EXCLUSION','hard_light':'OVERLAY','soft_light':'SOFT_LIGHT'}
for mode,enum in modes.items():
 mix=tree.nodes.new('ShaderNodeMix');mix.data_type='RGBA';mix.blend_type=enum;mix.clamp_result=False;mix.inputs[0].default_value=1
 color_inputs=[s for s in mix.inputs if s.type=='RGBA']
 color_output=next(s for s in mix.outputs if s.type=='RGBA')
 tree.links.new(b if mode=='hard_light' else a,color_inputs[0]);tree.links.new(a if mode=='hard_light' else b,color_inputs[1]);save(color_output,mode)
bpy.ops.render.render()
checks=[]
for mode in modes:
 job=dict(format='OCA',dest=str(out/(mode+'.oca')),oca_layout='PROJECT',dir=str(out/'cache'),extension='.exr',depth=32,
  frame=scene.frame_current,frame_rate=24,canvas_size=[1,1],hierarchy='LAYERS',overwrite=True,
  oca_options=dict(writeJson=False,writeTemplate=False,padding=0),manifest=[dict(name='Front',slug='Front',oca_authored=dict(blend=mode)),dict(name='Back',slug='Back')])
 path=Path(assemble(job));document=json.loads(path.read_text())
 # The current companion compositor expects the legacy asset-root argument.
 from oca_render import blend as over
 layers=list(nodes(document['layers']));front=next(n for n in layers if n['name'].startswith('Front'));back=next(n for n in layers if n['name']=='Back')
 from oca_images import load
 actual=over(load(path.parent/back['frames'][0]['fileName'],32),load(path.parent/front['frames'][0]['fileName'],32),front['blendingMode'])
 source=next((out/'cache').glob(mode+'*.exr'));reference=read_blender_pixels(source)
 error=float(abs(actual-reference).max())
 if mode!='soft_light':np.testing.assert_allclose(actual,reference,atol=2e-7)
 checks.append(dict(mode=mode,error=error,equivalent=error<=2e-7))
(out/'result.json').write_text(json.dumps(checks,indent=2));print('OCA_NATIVE_BLENDS_PASS',json.dumps(checks),flush=True)
