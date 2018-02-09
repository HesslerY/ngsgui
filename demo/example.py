from ngsolve import *
from netgen.geom2d import unit_square
from netgen.csg import *
import ngsolve.gui as GUI

ngsglobals.msg_level = 0
# nrefinements = 1

# mesh = Mesh(unit_cube.GenerateMesh(maxh=0.2))
def MakeGeometry():
    geometry = CSGeometry()
    s1 = Sphere(Pnt( 0.0,0,0), 1)
    s2 = Sphere(Pnt( 0.0,1,0), 1)
    geometry.Add(s1+s2)
    return geometry
#     box = OrthoBrick(Pnt(-1,-1,-1),Pnt(2,1,2)).bc("outer")
# 
#     core = OrthoBrick(Pnt(0,-0.05,0),Pnt(0.8,0.05,1))- \
#            OrthoBrick(Pnt(0.1,-1,0.1),Pnt(0.7,1,0.9))- \
#            OrthoBrick(Pnt(0.5,-1,0.4),Pnt(1,1,0.6)).maxh(0.2).mat("core")
#     
#     coil = (Cylinder(Pnt(0.05,0,0), Pnt(0.05,0,1), 0.3) - \
#             Cylinder(Pnt(0.05,0,0), Pnt(0.05,0,1), 0.15)) * \
#             OrthoBrick (Pnt(-1,-1,0.3),Pnt(1,1,0.7)).maxh(0.2).mat("coil")
#     
#     geometry.Add ((box-core-coil).mat("air"))
#     geometry.Add (core)
#     geometry.Add (coil)
#     return geometry



ngmesh = MakeGeometry().GenerateMesh(maxh=1.0)
mesh = Mesh(ngmesh)
# for i in range(nrefinements):
#     print('refine')
#     mesh.Refine()

mesh.Curve(2)
print(mesh.ne,'elements')

n = 5
cf = cos(n*x)*cos(n*y)*cos(n*z)

gui = GUI.GUI()
# scene = GUI.ClippingPlaneScene(cf, mesh,name="Solution")
scene1 = GUI.MeshScene(mesh,name="Mesh", wireframe=False, elements=True, surface=False)
# scene2 = GUI.MeshScene(mesh,surface=False, wireframe=False, elements=True, name="Elements")
# gui.draw(scene)
gui.draw(scene1)
# win1 = gui.make_window()
# win1.draw(scene1)
gui.run()

# scene1 = GUI.MeshScene(mesh,name="Mesh")
# scene2 = GUI.MeshScene(mesh,surface=False, wireframe=False, elements=True, name="Elements")
# win1 = gui.make_window(console=locals())
# win1.draw(scene)
# win2 = gui.make_window()
# win1.draw(scene1)
# win2.draw(scene2)
# gui.run()



# scene1 = GUI.MeshScene(mesh)
# gui.draw(scene1)
# gui.run()
