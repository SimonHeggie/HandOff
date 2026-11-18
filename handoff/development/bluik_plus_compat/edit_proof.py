"""Prove shared imported GP edits affect two actual rendered instances."""
import json
import bpy,numpy as np
from bpy_extras.object_utils import world_to_camera_view


def run(scene,objects,out,frame=0):
    clone=next(o for o in objects if o.get('oca_source_id') and o.type=='GREASEPENCIL' and not any(m.type=='GREASE_PENCIL_TIME' for m in o.modifiers))
    source=next(o for o in objects if o.get('oca_layer_id')==clone['oca_source_id'])
    assert clone.data==source.data
    scene.frame_set(frame);proof=bpy.data.scenes.new('OCA shared edit proof')
    proof.render.engine='CYCLES';proof.cycles.device='CPU';proof.cycles.samples=1;proof.cycles.use_denoising=False
    proof.render.resolution_x=scene.render.resolution_x;proof.render.resolution_y=scene.render.resolution_y;proof.render.resolution_percentage=100
    proof.render.film_transparent=True;proof.view_settings.view_transform='Standard';proof.render.use_compositing=False
    proof.frame_start=scene.frame_start;proof.frame_end=scene.frame_end
    proof.render.image_settings.file_format='PNG';proof.render.image_settings.color_mode='RGBA'
    proof.collection.objects.link(scene.camera);proof.camera=scene.camera
    copies=[]
    for original in (source,clone):
        obj=original.copy();obj.animation_data_clear();obj.hide_render=False;obj.hide_viewport=False
        proof.collection.objects.link(obj);copies.append(obj)
    proof.frame_set(frame)
    drawing=next(f.drawing for layer in source.data.layers for f in layer.frames if f.frame_number==frame and len(f.drawing.strokes))
    point=drawing.strokes[0].points[0];old=point.position.copy()
    def render(name):
        proof.render.filepath=str(out/name);bpy.ops.render.render(scene=proof.name,write_still=True)
        im=bpy.data.images.load(proof.render.filepath,check_existing=False);w,h=im.size
        pixels=np.empty(w*h*4,np.float32);im.pixels.foreach_get(pixels);bpy.data.images.remove(im)
        return pixels.reshape(h,w,4)[::-1].copy()
    try:
        before=render('edit-before.png')
        points=[p.position.copy() for p in drawing.strokes[0].points]
        boxes=[]
        for obj in copies:
            coords=[world_to_camera_view(proof,proof.camera,obj.matrix_world@p) for p in points]
            xs=[c.x*proof.render.resolution_x for c in coords];ys=[(1-c.y)*proof.render.resolution_y for c in coords]
            boxes.append((max(0,int(min(xs))-5),max(0,int(min(ys))-5),min(proof.render.resolution_x,int(max(xs))+6),min(proof.render.resolution_y,int(max(ys))+6)))
        point.position.x+=.03
        if hasattr(drawing,'tag_positions_changed'):drawing.tag_positions_changed()
        source.data.update_tag();after=render('edit-after.png')
        changed=np.any(abs(after-before)>1e-6,axis=2)
        counts=[int(changed[t:b,l:r].sum()) for l,t,r,b in boxes]
        assert all(count>0 for count in counts),(counts,boxes)
        (out/'shared-edit-proof.json').write_text(json.dumps(dict(source=source.name,clone=clone.name,shared_data=source.data.name,changed_pixels_per_instance=counts,boxes=boxes),indent=2))
    finally:
        point.position=old
        if hasattr(drawing,'tag_positions_changed'):drawing.tag_positions_changed()
        source.data.update_tag()
        for obj in copies:bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.scenes.remove(proof)
    return counts


def prove_time_offset(scene,objects,out):
    clone=next(o for o in objects if o.type=='GREASEPENCIL' and any(m.type=='GREASE_PENCIL_TIME' for m in o.modifiers))
    source=next(o for o in objects if o.get('oca_layer_id')==clone['oca_source_id'])
    modifier=next(m for m in clone.modifiers if m.type=='GREASE_PENCIL_TIME');offset=int(clone.get('oca_time_offset',modifier.offset))
    assert offset>0 and source.data==clone.data
    source_frame=0;target_frame=source_frame+offset;scene.frame_set(target_frame)
    proof=bpy.data.scenes.new('OCA time-offset proof');proof.collection.objects.link(scene.camera);proof.camera=scene.camera
    proof.render.engine='CYCLES';proof.cycles.device='CPU';proof.cycles.samples=1;proof.cycles.use_denoising=False
    proof.render.resolution_x=scene.render.resolution_x;proof.render.resolution_y=scene.render.resolution_y;proof.render.resolution_percentage=100
    proof.render.film_transparent=True;proof.render.use_compositing=False;proof.view_settings.view_transform='Standard'
    proof.frame_start=scene.frame_start;proof.frame_end=scene.frame_end
    proof.render.image_settings.file_format='OPEN_EXR';proof.render.image_settings.color_mode='RGBA';proof.render.image_settings.color_depth='32'
    evaluated=clone.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated_modifier=next(m for m in evaluated.modifiers if m.type=='GREASE_PENCIL_TIME')
    (out/'time-offset-state.json').write_text(json.dumps(dict(mode=modifier.mode,raw_offset=modifier.offset,evaluated_offset=evaluated_modifier.offset,source_frame=source_frame,instance_frame=target_frame),indent=2))
    frozen=None
    candidate=clone.copy();candidate.animation_data_clear();candidate.hide_render=False;candidate.hide_viewport=False
    candidate.matrix_world=evaluated.matrix_world.copy()
    for m in candidate.modifiers:
        if m.type=='GREASE_PENCIL_TIME':m.offset=evaluated_modifier.offset
    proof.collection.objects.link(candidate)
    for m in candidate.modifiers:
        if m.type=='GREASE_PENCIL_OPACITY':m.color_factor=1
    def render(frame,name):
        proof.frame_set(frame);proof.render.filepath=str(out/name);bpy.ops.render.render(scene=proof.name,write_still=True)
        image=bpy.data.images.load(proof.render.filepath,check_existing=False);w,h=image.size
        values=np.empty(w*h*4,np.float32);image.pixels.foreach_get(values);bpy.data.images.remove(image)
        return values.reshape(h,w,4)
    try:
        actual=render(target_frame,'time-offset-instance.exr')
        for m in list(candidate.modifiers):
            if m.type=='GREASE_PENCIL_TIME':candidate.modifiers.remove(m)
        # Render at the same scene time: GP antialiasing can vary with time.
        # Independently copy the expected drawing to the target key as reference.
        frozen=source.data.copy();frozen.animation_data_clear()
        for layer in frozen.layers:
            available=[f for f in layer.frames if f.frame_number<=source_frame]
            selected=max(available,key=lambda f:f.frame_number) if available else None
            selected_number=selected.frame_number if selected else None
            for number in [f.frame_number for f in layer.frames]:
                if number!=selected_number:layer.frames.remove(number)
            if selected_number is not None and selected_number!=target_frame:
                layer.frames.copy(selected_number,target_frame)
                layer.frames.remove(selected_number)
        candidate.data=frozen
        reference=render(target_frame,'time-offset-source.exr')
        np.testing.assert_allclose(actual,reference,atol=1e-6)
        assert actual[...,3].max()>0
        (out/'time-offset-proof.json').write_text(json.dumps(dict(source_frame=source_frame,instance_frame=target_frame,shared_data=True,maximum_pixel_error=float(abs(actual-reference).max())),indent=2))
    finally:
        bpy.data.objects.remove(candidate,do_unlink=True);bpy.data.scenes.remove(proof)
        if frozen and frozen.users==0:bpy.data.grease_pencils.remove(frozen)
