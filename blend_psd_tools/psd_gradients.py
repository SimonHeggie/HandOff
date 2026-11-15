"""Photoshop gradient descriptors for the conservatively mapped native subset.

Reader/fixture validation is separate from target-application validation in the
capability registry. Unsupported transforms never receive guessed descriptors.
"""
import math

def material_gradient(paint,size):
    gradients=[c.get('fill_gradient') for c in paint['contours']]
    if not gradients or not gradients[0] or any(g!=gradients[0] for g in gradients):
        raise ValueError('Compound fill has incompatible gradient paints')
    gradient=gradients[0]
    if gradient.get('interpolation','LINEAR')!='LINEAR' or gradient.get('color_mode','RGB')!='RGB':
        raise ValueError('Gradient interpolation needs the original SVG editing model')
    if gradient.get('spread','pad')!='pad':raise ValueError('Repeating gradient requires preserved SVG')
    a,b,c,d,x,y=gradient['matrix'];det=a*d-b*c
    if abs(det)<1e-10:raise ValueError('Singular gradient transform')
    width,height=size
    if gradient['kind']=='LINEAR':
        nx,ny=d/det,-c/det;length=1/math.hypot(nx,ny);nx*=length;ny*=length
        if abs(nx)>1e-6 and abs(ny)>1e-6:raise ValueError('Rotated linear gradient mapping awaits target validation')
        center=(x+nx*length/2,y+ny*length/2)
        angle=math.degrees(math.atan2(-ny,nx));scale=100*length/(width if abs(nx)>abs(ny) else height)
        kind=b'Lnr '
    elif gradient['kind']=='RADIAL':
        diameter=math.hypot(a,b)
        if abs(a*c+b*d)>1e-5*diameter**2 or abs(diameter-math.hypot(c,d))>1e-5*max(1,diameter):
            raise ValueError('Elliptical/skewed radial gradient needs preserved SVG')
        center=(x+(a+c)/2,y+(b+d)/2);angle=0;scale=100*diameter/width;kind=b'Rdl '
    else:raise ValueError('Unsupported native material gradient type')
    from psd_tools.psd.descriptor import Descriptor,Double,Integer,List,Enumerated,String,UnitFloat,Bool
    from psd_tools.terminology import Unit
    from psd_vectors import _color,rgb
    stops=gradient['stops']
    colors=[Descriptor(classID=b'Clrt',items={b'Clr ':_color(rgb(dict(color=s['color'],linear=s.get('linear')),paint.get('_depth',8))),
        b'Type':Enumerated(b'Clry',b'UsrS'),b'Lctn':Integer(round(s['position']*4096)),b'Mdpn':Integer(50)}) for s in stops]
    alphas=[Descriptor(classID=b'TrnS',items={b'Opct':UnitFloat(s['opacity']*100,Unit.Percent),
        b'Lctn':Integer(round(s['position']*4096)),b'Mdpn':Integer(50)}) for s in stops]
    ramp=Descriptor(classID=b'Grdn',items={b'Nm  ':String('Source gradient'),b'GrdF':Enumerated(b'GrdF',b'CstS'),
        b'Intr':Double(4096),b'Clrs':List(colors),b'Trns':List(alphas)})
    return Descriptor(classID=b'gradientLayer',items={b'Grad':ramp,b'Type':Enumerated(b'GrdT',kind),
        b'Angl':UnitFloat(angle,Unit.Angle),b'Rvrs':Bool(False),b'Dthr':Bool(True),b'Algn':Bool(False),
        b'Scl ':UnitFloat(scale,Unit.Percent),b'Ofst':Descriptor(classID=b'Pnt ',items={
            b'Hrzn':UnitFloat(100*(center[0]/width-.5),Unit.Percent),
            b'Vrtc':UnitFloat(100*(center[1]/height-.5),Unit.Percent)})})
