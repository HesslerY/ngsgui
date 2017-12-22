class clipping:
    fragment =  """
#version 150
uniform vec4 fColor;
uniform vec4 fColor_clipped;

uniform vec4 clipping_plane;

out vec4 FragColor;

in VertexData
{
  vec3 pos;
} inData;

void main()
{
  FragColor = fColor;
}
"""

    vertex = """
#version 150
uniform mat4 MV;
uniform mat4 P;
in vec3 vPos;

out VertexData
{
  vec3 pos;
} outData;

void main()
{
    gl_Position = P * MV * vec4(vPos, 1.0);
    outData.pos = vPos;
}
"""

    geometry_solution = """
#version 150

uniform samplerBuffer coefficients;

layout(lines_adjacency) in;
layout(triangle_strip, max_vertices=6) out;

in VertexData
{
  vec3 pos;
  flat int element;
  vec3 lam;
} inData[];

out VertexData
{
  vec3 pos;
  flat int element;
  vec3 lam;
} outData;

uniform mat4 MV;
uniform mat4 P;
uniform vec4 clipping_plane;

{shader_functions}

float cut(vec3 x, vec3 y) {
      float dx = dot(clipping_plane, vec4(x,1.0));
      float dy = dot(clipping_plane, vec4(y,1.0));
      float a = dx/(dx-dy);
      return a;
}

void emit(vec3 x, vec3 lam) {
    outData.pos = x;
    outData.lam = lam;
    gl_Position = P * MV *vec4(x,1);
    EmitVertex();
}

void doAll(int i, int j) {
    vec3 lam;
    float a = cut(inData[i].pos,inData[j].pos);

    vec3 pos = mix(inData[i].pos, inData[j].pos, a);
    lam = mix(inData[i].lam, inData[j].lam, a);

    // deformation
    // pos.z += 0.1*EvalTET(inData[0].element, lam.x, lam.y, lam.z);
    outData.pos = pos;
    outData.lam = lam;

    gl_Position = P * MV *vec4(pos,1);
    EmitVertex();
}

void main() {
    outData.element = inData[0].element;

    int nvertices_behind = 0;
    int vertices_behind[3];
    int nvertices_front = 0;
    int vertices_front[3];
    for (int i=0; i<4; ++i) {
      float dist = dot(clipping_plane, vec4(inData[i].pos,1.0));
      if(dist>0) {
          vertices_behind[nvertices_behind] = i;
          nvertices_behind++;
      }
      else {
          vertices_front[nvertices_front] = i;
          nvertices_front++;
      }
    }
    if( nvertices_behind==3 ) {
        vec3 x = inData[vertices_front[0]].pos;
        for (int i=0; i<3; ++i) {
          doAll(vertices_front[0], vertices_behind[i]);
        }
        EndPrimitive();
    }
    if( nvertices_behind==1 ) {
        vec3 x = inData[vertices_behind[0]].pos;
        for (int i=0; i<3; ++i) {
          doAll(vertices_behind[0], vertices_front[i]);
        }
        EndPrimitive();
    }

    if( nvertices_behind==2 ) {
        vec3 res;
        vec3 lam;

        doAll(vertices_front[0],vertices_behind[0]);
        doAll(vertices_front[0],vertices_behind[1]);
        doAll(vertices_front[1],vertices_behind[1]);
        EndPrimitive();

        doAll(vertices_front[0],vertices_behind[0]);
        doAll(vertices_front[1],vertices_behind[1]);
        doAll(vertices_front[1],vertices_behind[0]);
        EndPrimitive();
    }
}

"""
    geometry = """
#version 150

layout(lines_adjacency) in;
layout(triangle_strip, max_vertices=6) out;

in VertexData
{
  vec3 pos;
} inData[];

out VertexData
{
  vec3 pos;
} outData;

uniform mat4 MV;
uniform mat4 P;
uniform vec4 clipping_plane;

vec3 cut(vec3 x, vec3 y) {
      float dx = dot(clipping_plane, vec4(x,1.0));
      float dy = dot(clipping_plane, vec4(y,1.0));
      float a = dx/(dx-dy);
      vec3 res =  mix(x,y,a);
      return res;
}

void emit(vec3 x) {
    outData.pos = x;
    gl_Position = P * MV *vec4(x,1);
    EmitVertex();
}


void main() {

    int nvertices_behind = 0;
    int vertices_behind[3];
    int nvertices_front = 0;
    int vertices_front[3];
    for (int i=0; i<4; ++i) {
      float dist = dot(clipping_plane, vec4(inData[i].pos,1.0));
      if(dist>0) {
          vertices_behind[nvertices_behind] = i;
          nvertices_behind++;
      }
      else {
          vertices_front[nvertices_front] = i;
          nvertices_front++;
      }
    }
    if( nvertices_behind==-1 ) {
        outData.pos = inData[0].pos;
        gl_Position = P * MV *vec4(inData[0].pos,1);
        EmitVertex();
        outData.pos = inData[1].pos;
        gl_Position = P * MV *vec4(inData[1].pos,1);
        EmitVertex();
        outData.pos = inData[2].pos;
        gl_Position = P * MV *vec4(inData[2].pos,1);
        EmitVertex();
        EndPrimitive();
    }
    if( nvertices_front==-1 ) {
        outData.pos = inData[vertices_behind[0]].pos;
        gl_Position = P * MV *vec4(inData[vertices_behind[0]].pos,1);
        EmitVertex();
        outData.pos = inData[1].pos;
        gl_Position = P * MV *vec4(inData[vertices_behind[1]].pos,1);
        EmitVertex();
        outData.pos = inData[2].pos;
        gl_Position = P * MV *vec4(inData[vertices_behind[2]].pos,1);
        EmitVertex();
        EndPrimitive();
    }
    if( nvertices_behind==3 ) {
        vec3 x = inData[vertices_front[0]].pos;
        for (int i=0; i<3; ++i) {
          vec3 y = inData[vertices_behind[i]].pos;
          vec3 res = cut(x,y);
          outData.pos = res;
          gl_Position = P * MV * vec4(res,1);
          EmitVertex();
        }
        EndPrimitive();
    }
    if( nvertices_behind==1 ) {
        vec3 x = inData[vertices_behind[0]].pos;
        for (int i=0; i<3; ++i) {
          vec3 y = inData[vertices_front[i]].pos;
          vec3 res = cut(x,y);
          outData.pos = res;
          gl_Position = P * MV * vec4(res,1);
          EmitVertex();
        }
        EndPrimitive();
    }

    if( nvertices_behind==2 ) {
        vec3 res;

        emit(cut(inData[vertices_front[0]].pos, inData[vertices_behind[0]].pos));
        emit(cut(inData[vertices_front[0]].pos, inData[vertices_behind[1]].pos));
        emit(cut(inData[vertices_front[1]].pos, inData[vertices_behind[1]].pos));
        EndPrimitive();

        emit(cut(inData[vertices_front[0]].pos, inData[vertices_behind[0]].pos));
        emit(cut(inData[vertices_front[1]].pos, inData[vertices_behind[1]].pos));
        emit(cut(inData[vertices_front[1]].pos, inData[vertices_behind[0]].pos));
        EndPrimitive();
    }
}

"""

class mesh:
    fragment =  """
#version 150
uniform vec4 fColor;
uniform vec4 fColor_clipped;
uniform vec4 clipping_plane;

out vec4 FragColor;

in VertexData
{
  vec3 pos;
} inData;

void main()
{
  if(dot(vec4(inData.pos,1.0),clipping_plane)<0)
    FragColor = fColor;
  else
    FragColor = fColor_clipped;
}
"""

    vertex = """
#version 150
uniform mat4 MV;
uniform mat4 P;
in vec3 vPos;

out VertexData
{
  vec3 pos;
} outData;

void main()
{
    gl_Position = P * MV * vec4(vPos, 1.0);
    outData.pos = vPos;
}
"""

class solution:
    fragment_header = """
#version 150
uniform samplerBuffer coefficients;
uniform float colormap_min, colormap_max;
uniform bool colormap_linear;
uniform int element_type;
uniform vec4 clipping_plane;
uniform bool do_clipping;

in VertexData
{
  vec3 pos;
  flat int element;
  vec3 lam;
} inData;

out vec4 FragColor;

vec3 MapColor(float value)
{
    value = (value-colormap_min)/(colormap_max-colormap_min);
    value = clamp(value, 0.0, 1.0);
    value = (1.0 - value);
    if(!colormap_linear)
      value = floor(8*value)/7.0;
    value = clamp(value, 0.0, 1.0);
    vec3 res;
    res.r = clamp(2.0-4.0*value, 0.0, 1.0);
    res.g = clamp(2.0-4.0*abs(0.5-value), 0.0, 1.0);
    res.b = clamp(4.0*value - 2.0, 0.0, 1.0);
    return res;
}

float zahn(float x, float y) {
  return atan(1000*x*y*y - floor(1000*x*y*y));
}

{shader_functions}

void main()
{
  if(!do_clipping || dot(vec4(inData.pos,1.0),clipping_plane)<0)
  {
      float x = inData.lam.x;
      float y = inData.lam.y;
      float z = inData.lam.z;
      //  { ET_POINT = 0, ET_SEGM = 1,
      //    ET_TRIG = 10, ET_QUAD = 11, 
      //    ET_TET = 20, ET_PYRAMID = 21, ET_PRISM = 22, ET_HEX = 24 };
      float value;
      if(element_type == 10) value = EvalTRIG(inData.element, x,y,z);
      if(element_type == 20) value = EvalTET(inData.element, x,y,z);
      if(element_type == 21) value = EvalPYRAMID(inData.element, x,y,z);
      if(element_type == 22) value = EvalPRISM(inData.element, x,y,z);
      if(element_type == 24) value = EvalHEX(inData.element, x,y,z);
      FragColor.r = MapColor(value).r;
      FragColor.g = MapColor(value).g;
      FragColor.b = MapColor(value).b;
      FragColor.a = 1.0;
  }
  else
    discard;
}
"""

    fragment_main = """
"""

    vertex = """
#version 150
uniform mat4 MV;
uniform mat4 P;

in vec3 vPos;
in vec3 vLam;
in int vElementNumber;

out VertexData
{
  vec3 pos;
  flat int element;
  vec3 lam;
} outData;

void main()
{
    gl_Position = P * MV * vec4(vPos, 1.0);
//    outData.lam = vec3(0.0, 0.0, 0.0);
    outData.pos = vPos; //0.5*vPos +0.5;
    outData.element = vElementNumber; //gl_VertexID/3; //vIndex/3;
    outData.lam = vLam;
}
"""

geometry_copy = """
#version 420

layout(triangles) in;
layout(triangle_strip, max_vertices=6) out;

in VertexData
{
  vec3 pos;
  flat int element;
  vec3 lam;
} inData[];

out VertexData
{
  vec3 pos;
  flat int element;
  vec3 lam;
} outData;

uniform mat4 MV;
uniform mat4 P;

void main() {
    // vec3 normal = cross(inData[1].pos-inData[0].pos, inData[2].pos-inData[0].pos);
    // normal = normal/sqrt(dot(normal,normal));

    // fBrightness = 0.3+0.7*clamp(dot(normal,vec3(1,1,1)/sqrt(3)), 0.0, 1.0);

    outData.element = inData[0].element;

    for (int i=0; i<3; ++i) {
      gl_Position = P * MV * vec4(inData[i].pos,1);
      outData.pos = inData[i].pos;
      outData.lam = inData[i].lam;
      EmitVertex();
    }
    EndPrimitive();
}

"""
def tryprint(s):
    try:
        print(s+str(gl.getInteger(gl.__getattr__('s'))))
    except:
        pass

def printLimits():
  import OpenGL.GL as gl
  tryprint('GL_MAX_3D_TEXTURE_SIZE')
  tryprint('GL_MAX_ARRAY_TEXTURE_LAYERS')
  tryprint('GL_MAX_ATTRIB_STACK_DEPTH')
  tryprint('GL_MAX_CLIENT_ATTRIB_STACK_DEPTH')
  tryprint('GL_MAX_CLIP_PLANES')
  tryprint('GL_MAX_COLOR_ATTACHMENTS')
  tryprint('GL_MAX_COLOR_MATRIX_STACK_DEPTH')
  tryprint('GL_MAX_COLOR_TEXTURE_SAMPLES')
  tryprint('GL_MAX_COMBINED_FRAGMENT_UNIFORM_COMPONENTS')
  tryprint('GL_MAX_COMBINED_GEOMETRY_UNIFORM_COMPONENTS')
  tryprint('GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS_ARB')
  tryprint('GL_MAX_COMBINED_UNIFORM_BLOCKS')
  tryprint('GL_MAX_COMBINED_VERTEX_UNIFORM_COMPONENTS')
  tryprint('GL_MAX_CONVOLUTION_WIDTH/HEIGHT')
  tryprint('GL_MAX_CUBE_MAP_TEXTURE_SIZE_ARB')
  tryprint('GL_MAX_DEPTH_TEXTURE_SAMPLES')
  tryprint('GL_MAX_DRAW_BUFFERS_ARB')
  tryprint('GL_MAX_DUAL_SOURCE_DRAW_BUFFERS')
  tryprint('GL_MAX_ELEMENTS_INDICES')
  tryprint('GL_MAX_ELEMENTS_VERTICES')
  tryprint('GL_MAX_EVAL_ORDER')
  tryprint('GL_MAX_FRAGMENT_INPUT_COMPONENTS')
  tryprint('GL_MAX_FRAGMENT_UNIFORM_BLOCKS')
  tryprint('GL_MAX_FRAGMENT_UNIFORM_COMPONENTS_ARB')
  tryprint('GL_MAX_GEOMETRY_INPUT_COMPONENTS')
  tryprint('GL_MAX_GEOMETRY_OUTPUT_COMPONENTS')
  tryprint('GL_MAX_GEOMETRY_OUTPUT_VERTICES')
  tryprint('GL_MAX_GEOMETRY_TEXTURE_IMAGE_UNITS')
  tryprint('GL_MAX_GEOMETRY_TOTAL_OUTPUT_COMPONENTS')
  tryprint('GL_MAX_GEOMETRY_UNIFORM_BLOCKS')
  tryprint('GL_MAX_GEOMETRY_UNIFORM_COMPONENTS')
  tryprint('GL_MAX_INTEGER_SAMPLES')
  tryprint('GL_MAX_LIGHTS')
  tryprint('GL_MAX_LIST_NESTING')
  tryprint('GL_MAX_MODELVIEW_STACK_DEPTH')
  tryprint('GL_MAX_NAME_STACK_DEPTH')
  tryprint('GL_MAX_PIXEL_MAP_TABLE')
  tryprint('GL_MAX_PROGRAM_ADDRESS_REGISTERS_ARB')
  tryprint('GL_MAX_PROGRAM_ADDRESS_REGISTERS_ARB')
  tryprint('GL_MAX_PROGRAM_ALU_INSTRUCTIONS_ARB')
  tryprint('GL_MAX_PROGRAM_ATTRIBS_ARB')
  tryprint('GL_MAX_PROGRAM_ENV_PARAMETERS_ARB')
  tryprint('GL_MAX_PROGRAM_INSTRUCTIONS_ARB')
  tryprint('GL_MAX_PROGRAM_LOCAL_PARAMETERS_ARB')
  tryprint('GL_MAX_PROGRAM_NATIVE_ADDRESS_REGISTERS_ARB')
  tryprint('GL_MAX_PROGRAM_NATIVE_ADDRESS_REGISTERS_ARB')
  tryprint('GL_MAX_PROGRAM_NATIVE_ALU_INSTRUCTIONS_ARB')
  tryprint('GL_MAX_PROGRAM_NATIVE_ATTRIBS_ARB')
  tryprint('GL_MAX_PROGRAM_NATIVE_INSTRUCTIONS_ARB')
  tryprint('GL_MAX_PROGRAM_NATIVE_PARAMETERS_ARB')
  tryprint('GL_MAX_PROGRAM_NATIVE_TEMPORARIES_ARB')
  tryprint('GL_MAX_PROGRAM_NATIVE_TEX_INDIRECTIONS_ARB')
  tryprint('GL_MAX_PROGRAM_NATIVE_TEX_INSTRUCTIONS_ARB')
  tryprint('GL_MAX_PROGRAM_PARAMETERS_ARB')
  tryprint('GL_MAX_PROGRAM_TEMPORARIES_ARB')
  tryprint('GL_MAX_PROGRAM_TEX_INDIRECTIONS_ARB')
  tryprint('GL_MAX_PROGRAM_TEX_INSTRUCTIONS_ARB')
  tryprint('GL_MAX_PROJECTION_STACK_DEPTH')
  tryprint('GL_MAX_RECTANGLE_TEXTURE_SIZE_NV')
  tryprint('GL_MAX_RENDERBUFFER_SIZE')
  tryprint('GL_MAX_SAMPLES')
  tryprint('GL_MAX_TEXTURE_BUFFER_SIZE')
  tryprint('GL_MAX_TEXTURE_COORDS_ARB')
  tryprint('GL_MAX_TEXTURE_IMAGE_UNITS_ARB')
  tryprint('GL_MAX_TEXTURE_LOD_BIAS_EXT')
  tryprint('GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT')
  tryprint('GL_MAX_TEXTURE_SIZE')
  tryprint('GL_MAX_TEXTURE_STACK_DEPTH')
  tryprint('GL_MAX_TEXTURE_UNITS_ARB')
  tryprint('GL_MAX_UNIFORM_BLOCK_SIZE')
  tryprint('GL_MAX_UNIFORM_BUFFER_BINDINGS')
  tryprint('GL_MAX_VARYING_FLOATS_ARB')
  tryprint('GL_MAX_VERTEX_ATTRIB_BINDINGS')
  tryprint('GL_MAX_VERTEX_ATTRIB_RELATIVE_OFFSET')
  tryprint('GL_MAX_VERTEX_ATTRIBS_ARB')
  tryprint('GL_MAX_VERTEX_ATTRIB_STRIDE')
  tryprint('GL_MAX_VERTEX_OUTPUT_COMPONENTS')
  tryprint('GL_MAX_VERTEX_TEXTURE_IMAGE_UNITS_ARB')
  tryprint('GL_MAX_VERTEX_UNIFORM_BLOCKS')
  tryprint('GL_MAX_VERTEX_UNIFORM_COMPONENTS_ARB')
  tryprint('GL_MAX_VIEWPORT_DIMS')
