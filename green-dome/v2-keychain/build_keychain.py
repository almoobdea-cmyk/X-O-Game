"""Green Dome keychain: watertight printable solid, built from the v1 survey constants.
Units: millimetres, Z up. Total height (base to top of ring) = 75 mm.
Run: python3 build_keychain.py   ->  green-dome-keychain-hollow.stl / -solid.stl
"""
import math, numpy as np, trimesh
from manifold3d import Manifold, CrossSection

TOTAL = 75.0            # hard limit on overall length
BODY  = 54.0            # roof level to shell apex; the rest is finial + ring
S = BODY / 14.40        # mm per metre of the real building (about 1:253)
SEG = 128
PI = math.pi

# survey constants from v1 (metres)
Y_BASE, Y_BRIM, Y_POLY, Y_DRUM, Y_ARC, Y_APEX = 5.80, 6.15, 7.50, 8.55, 9.33, 14.40
R_BRIM, R_POLY, R_DRUM, R_ARC = 6.0, 5.12, 4.60, 4.52
PROFILE = [(0,.38),(.4,.90),(.72,1.31),(1.04,1.71),(1.36,2.14),(1.68,2.56),(2.0,2.99),(2.32,3.31),(2.64,3.55),
           (2.96,3.73),(3.28,3.89),(3.6,4.03),(3.92,4.14),(4.24,4.21),(4.56,4.26),(4.88,4.29),(5.07,4.30)]
BASE = [(0,6.85,1.25),(0.25,6.80,1.25),(3.9,6.12,1.4),(Y_BASE,5.72,2.35)]   # y, half width, chamfer

def union(parts): return Manifold.batch_boolean(parts, __import__('manifold3d').OpType.Add)
def rotz(m, deg): return m.rotate([0,0,deg])
def cyl(h, r0, r1=None, seg=SEG): return Manifold.cylinder(h, r0, r0 if r1 is None else r1, seg)
def ring_pts(a, c, z): return [(x*S, y*S, z*S) for x,y in [(a,-(a-c)),(a,a-c),(a-c,a),(-(a-c),a),(-a,a-c),(-a,-(a-c)),(-(a-c),-a),(a-c,-a)]]
def loft(levels, inset=0.0):
    out=[]
    for (y0,a0,c0),(y1,a1,c1) in zip(levels, levels[1:]):
        i=inset/S
        out.append(Manifold.hull_points(ring_pts(a0-i,c0,y0)+ring_pts(a1-i,c1,y1)))
    return union(out)
def half_at(y):
    for (y0,a0,_),(y1,a1,_) in zip(BASE, BASE[1:]):
        if y<=y1: return a0+(a1-a0)*(y-y0)/(y1-y0)
    return BASE[-1][1]
def poly(pts):
    a=sum(x0*y1-x1*y0 for (x0,y0),(x1,y1) in zip(pts,pts[1:]+pts[:1]))
    return CrossSection([pts if a>0 else pts[::-1]])
def arch2d(w, h, n=14):
    r=w/2; pts=[(-r,0),(r,0)]+[(r*math.cos(t), h-r+r*math.sin(t)) for t in np.linspace(0,PI,n)]
    return CrossSection([pts])
def circle2d(r, n=48): return CrossSection([[(r*math.cos(t), r*math.sin(t)) for t in np.linspace(0,2*PI,n,endpoint=False)]])
def frame(u, v, n, p):
    return np.array([[u[0],v[0],n[0],p[0]],[u[1],v[1],n[1],p[1]],[u[2],v[2],n[2],p[2]]])
def on_ring(m, R, z, deg):
    """m is modelled with +Z pointing out of the wall and +Y up the wall; put it on a cylinder of radius R."""
    a=math.radians(deg); n=(math.sin(a),math.cos(a),0); u=(-math.cos(a),math.sin(a),0)
    return m.transform(frame(u,(0,0,1),n,(R*n[0],R*n[1],z)))

add, cut, post = [], [], []        # post = details that sit inside a recess, added after the cuts

# ---- white base -------------------------------------------------------------
add.append(loft(BASE))
add.append(loft([(0,7.0,1.3),(0.22,7.0,1.3)]))
beta = math.atan((BASE[1][1]-BASE[2][1])/(BASE[2][0]-BASE[1][0]))
def on_face(m, x, y, f):
    """place on base face f at lateral x (m) and height y (m); local +Z = outward wall normal."""
    n=(0,math.cos(beta),math.sin(beta)); v=(0,-math.sin(beta),math.cos(beta)); u=(-1,0,0)
    return rotz(m.transform(frame(u,v,n,(x*S, half_at(y)*S, y*S))), 90*f)
R_WIN = 0.60*S                      # round window, real 1.20 m
rosette = union([Manifold.cube([2*R_WIN,0.42,0.6],True).rotate([0,0,22.5+45*k]) for k in range(4)]
                + [cyl(0.6,0.75,None,24).translate([0,0,-0.3])]).translate([0,0,-0.3])
for f in range(4):
    for x,y in [(0,3.73),(-.84,2.40),(.84,2.40)]:
        cut.append(on_face(cyl(1.4,R_WIN-0.35,None,48).translate([0,0,-0.6]), x,y,f))       # recess 0.6 deep
        add.append(on_face(Manifold.extrude(circle2d(R_WIN+0.15)-circle2d(R_WIN-0.35),0.75).translate([0,0,-0.4]), x,y,f))  # frame, 0.35 proud
        post.append(on_face(rosette ^ cyl(2,R_WIN-0.3,None,48).translate([0,0,-1.5]), x,y,f))  # star grille
    for x in (-1.63,0,1.63):
        w,h=1.25*S,0.98*S
        cut.append(on_face(Manifold.extrude(arch2d(w-0.9,h-0.45),1.4).translate([0,0,-0.6]), x,0.62,f))
        add.append(on_face(Manifold.extrude(arch2d(w,h)-arch2d(w-0.9,h-0.45),0.75).translate([0,0,-0.4]), x,0.60,f))
        post.append(on_face(Manifold.cube([0.42,h-0.5,0.6],False).translate([-0.21,0,-0.6]), x,0.62,f))  # mullion
# corners: broach spurs and the chamfer window
for k in range(4):
    deg=45+90*k
    for s in (-1,1):
        sp=cyl(2.6*S,1.35*S,0.0,4).rotate([0,0,45]).translate([s*2.45*S, 6.0*S, 3.2*S])
        add.append(sp.rotate([0,0,-deg]))
    win=Manifold.cube([1.2*S,1.3*S,1.6],True).translate([0,0.65*S,0]) - Manifold.cube([0.8*S,0.9*S,1.6],True).translate([0,0.65*S,1.1])
    win=win+Manifold.cube([0.38,0.9*S,0.5],True).translate([0,0.65*S,0.05])
    n=(0,math.cos(0.555),math.sin(0.555)); v=(0,-math.sin(0.555),math.cos(0.555))
    add.append(win.transform(frame((-1,0,0),v,n,(0,7.5*S,4.05*S))).rotate([0,0,-deg]))

# ---- cornice and 16-sided base band ------------------------------------------
def poly16(h, r0, r1, z): return cyl(h*S, r0*S, r1*S, 16).rotate([0,0,11.25]).translate([0,0,z*S])
add += [poly16(.22,R_BRIM-.55,R_BRIM-.25,Y_BASE-.13), poly16(.26,R_BRIM,R_BRIM,Y_BASE+.07), poly16(.10,R_BRIM-.02,R_POLY+.12,Y_BASE+.33),
        poly16(Y_POLY-Y_BRIM-.22+.2,R_POLY+.04,R_POLY,Y_BRIM-.2), poly16(.22,R_POLY,R_DRUM+.08,Y_POLY-.22)]
AP = R_POLY*math.cos(PI/16)*S
for i in range(16):
    cut.append(on_ring(Manifold.extrude(arch2d(0.74*S,1.0*S),1.2).translate([0,0,-0.45]), AP, (Y_BRIM+.1)*S, i*22.5))
    post.append(on_ring(Manifold.cube([0.74*S,0.32,0.3],True).translate([0,0.5*S,-0.3]), AP, (Y_BRIM+.1)*S, i*22.5))  # shutter rail

# ---- drum, 32 paired niches --------------------------------------------------
add.append(cyl((Y_DRUM-Y_POLY)*S+.2, R_DRUM*S, (R_DRUM-.03)*S).translate([0,0,Y_POLY*S-.1]))
for i in range(16):
    for s in (-1,1):
        cut.append(on_ring(Manifold.extrude(arch2d(1.55,0.66*S),1.3).translate([0,0,-0.55]), R_DRUM*S, (Y_POLY+.14)*S, i*22.5+s*4.1))
for z in (Y_POLY+.02, Y_DRUM-.06):                                   # mouldings
    add.append(cyl(0.5, R_DRUM*S+0.3).translate([0,0,z*S-.25]))

# ---- arcade band, 64 blind arches -------------------------------------------
add.append(cyl((Y_ARC-Y_DRUM)*S+.2, R_ARC*S, (R_ARC-.12)*S).translate([0,0,Y_DRUM*S-.1]))
for i in range(64):
    cut.append(on_ring(Manifold.extrude(arch2d(1.15,0.52*S),1.0).translate([0,0,-0.32]), (R_ARC-.04)*S, (Y_DRUM+.1)*S, i*5.625))
add.append(cyl(0.5, (R_ARC-.1)*S+0.3).translate([0,0,Y_ARC*S-.25]))

# ---- ribbed shell ------------------------------------------------------------
prof=[(r*S,(Y_APEX-d)*S) for d,r in PROFILE]                         # apex first
shell2d=poly([(0,prof[-1][1]-.3)]+[(r,z) for r,z in reversed(prof)]+[(0,prof[0][1])])
add.append(Manifold.revolve(shell2d, SEG))
def offset_prof(o):                                                  # offset along the outward normal
    out=[]
    for i,(r,z) in enumerate(prof):
        r0,z0=prof[max(i-1,0)]; r1,z1=prof[min(i+1,len(prof)-1)]
        tx,tz=r1-r0,z1-z0; L=math.hypot(tx,tz); out.append((r+o*(-tz)/L, z+o*(tx)/L))
    return out
rib2d=poly(offset_prof(0.38)+list(reversed(offset_prof(-0.5))))
ribfull=Manifold.revolve(rib2d, SEG)
print('ribfull',ribfull.status(),ribfull.volume(),rib2d.area())
rib=(ribfull ^ Manifold.cube([60,0.62,90]).translate([0,-0.31,0])) - cyl(90,2.7,None,32)       # constant 0.62 mm wide standing seam
add += [rib.rotate([0,0,(i+.5)*5.625]) for i in range(64)]
add.append(cyl(0.55, 4.31*S+0.32).translate([0,0,Y_ARC*S+.05]))      # drip edge

# ---- finial with the key ring as its crest -----------------------------------
z=Y_APEX*S-1.0
lobes=[Manifold.sphere(1.0,32).scale([1.25,1.25,1.9]).translate([1.75*math.cos(k*PI/4),1.75*math.sin(k*PI/4),1.75]) for k in range(8)]
lotus=union(lobes+[Manifold.sphere(1.0,32).scale([2.3,2.3,2.0]).translate([0,0,1.8])]).trim_by_plane([0,0,1],0.0)
add.append(lotus.translate([0,0,z])); z+=3.3
add.append(cyl(9.0,1.4,None,32).translate([0,0,z-1.0]))               # 2.8 mm core through the whole stack
for r in (2.2,2.0):
    add.append(cyl(0.5,r+0.25,None,32).translate([0,0,z])); z+=0.35
    add.append(Manifold.sphere(r,40).scale([1,1,1.08]).translate([0,0,z+r*1.08-0.2])); z+=2*r*1.08-0.45
add.append(cyl(0.5,2.0,None,32).translate([0,0,z])); z+=0.3
RING_R, WIRE = 3.85, 1.35                                             # centre-line radius, wire radius -> hole 5.0 mm
RING_R = (TOTAL-(z-0.9)-2*WIRE)/2                                     # size the ring so the top lands exactly at 75 mm
torus=Manifold.revolve(circle2d(WIRE,32).translate([RING_R,0]),72).rotate([90,0,0])
add.append(torus.translate([0,0,z-0.9+RING_R+WIRE]))

import sys
for i,m in enumerate(add):
    if m.is_empty() or m.volume()<=0: print('EMPTY add',i,m.status(),m.volume(),file=sys.stderr)
for i,m in enumerate(cut):
    if m.is_empty() or m.volume()<=0: print('EMPTY cut',i,m.status(),m.volume(),file=sys.stderr)
solid = (union(add) - union(cut)) + union(post)
print('solid',solid.status(),solid.num_tri(),solid.volume())

# ---- hollow version: 2.4 mm wall, open underneath -----------------------------
T=2.4
inner=[(max(r-T,0.01), z_-T*0.6) for r,z_ in offset_prof(0)]
cav2d=poly([(0,-1)]+[(R_DRUM*S-T-0.6,-1),(R_DRUM*S-T-0.6,inner[-1][1])]+[(r,z_) for r,z_ in reversed(inner) if r>0.8]+[(0,inner[0][1]-1.0)])
cavity=Manifold.revolve(cav2d,SEG) + loft([(-0.5,BASE[0][1],BASE[0][2]),(BASE[2][0],BASE[2][1],BASE[2][2]),(Y_BASE-0.75,BASE[3][1]+.05,BASE[3][2])], inset=T+0.7)
hollow = solid - cavity

def export(m, name):
    me=m.to_mesh(); tm=trimesh.Trimesh(np.asarray(me.vert_properties)[:,:3], np.asarray(me.tri_verts), process=False)
    tm.export(name); bb=tm.bounds
    print(f"{name}: {len(tm.faces)} tris, watertight={tm.is_watertight}, size={np.round(bb[1]-bb[0],2)} mm, volume={tm.volume/1000:.1f} cm3, ring hole Ø={2*(RING_R-WIRE):.2f} mm")
export(solid,'green-dome-keychain-solid.stl'); export(hollow,'green-dome-keychain-hollow.stl')
