#version 150
uniform vec4 fColor;
uniform vec4 fColor_clipped;
uniform vec4 clipping_plane;
uniform bool use_index_color;
uniform sampler1D index_color;
uniform bool do_clipping;
uniform bool draw_edges;

out vec4 FragColor;

in VertexData
{
  vec3 pos;
  float edgedist;
  flat int index;
} inData;


void main()
{
  if(draw_edges && inData.edgedist>1e-5) discard;
  if(!do_clipping || dot(vec4(inData.pos,1.0),clipping_plane)<0) {
    FragColor = vec4(texelFetch(index_color, inData.index, 0));
    if(!use_index_color) {
      FragColor.rgb = fColor.rgb;
    }
    if(FragColor.a==0.0)
      discard;
  } else {
    discard;
    // FragColor = fColor_clipped;
  }
}
