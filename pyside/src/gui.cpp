#include<fem.hpp>
#include<comp.hpp>
#include<l2hofe_impl.hpp>
#include<l2hofefo.hpp>

#include<pybind11/pybind11.h>
#include<pybind11/stl_bind.h>
#include<pybind11/numpy.h>
#include<regex>

using namespace ngfem;

namespace genshader {
    template <ELEMENT_TYPE ET, typename BASE>
      class MyFEL : public BASE {
        public:
          using BASE::ndof;
          using BASE::vnums;
          using BASE::order;
          using BASE::order_inner;
          using BASE::GetFaceSort;
          using BASE::GetEdgeSort;
          MyFEL(int order) : BASE(order) {}
          MyFEL() : BASE() {}
          template<typename Tx, typename TFA>  
            INLINE void MyCalcShape (TIP<ET_trait<ET>::DIM,Tx> ip, TFA & shape) const
              {
                BASE::T_CalcShape(ip, shape);
              }
      };

    static std::vector<string> expressions;

    struct CCode {
        static int find( std::vector<string> &v, string val ){ 
            int i = 0;
            for(auto &s : v) {
                if(s==val)
                  return i;
                i++;
            }
            return -1;
        }

        static string strip(string s) {
            int n = s.size();
            if(n<=1) return s;
            if(s[0] == '(' && s[n-1] == ')') return strip(s.substr(1,n-2));
            return s;
        }
        mutable string s;

        static CCode Par(const CCode &c) {
            return c.s;
        }

        void Check() {
            static string int_num = "var[0-9]*";
            static regex pattern(int_num);
            if(s=="") return;
//             s = "("+s+")";
            int index = find( expressions, strip(s));
            if(index>=0) {
                s = "var"+ToString(index);
            }
            else {
                if(!regex_match(strip(s), pattern)) {
                    expressions.push_back(strip(s));
                    s = "var"+ToString(expressions.size()-1);
                }
            }
        }

        CCode(const CCode &c) : 
          s(c.s)
        {
          Check();
        }

        CCode(string as = "") : s(as) {
            Check();
        }

        CCode(double val) {
            std::stringstream str;
            str << fixed << setprecision( 15 ) << val;
            s = str.str();
            Check();
        }

        virtual CCode operator +(const CCode &c) { return CCode(s+'+'+c.s); }
        virtual CCode operator -(const CCode &c) { return CCode(s+'-'+c.s); }
        virtual CCode operator *(const CCode &c) { return CCode(s+'*'+c.s); }
        virtual void operator +=(const CCode &c) { *this = *this+c; }
        virtual void operator *=(const CCode &c) { *this = *this*c; }
        virtual CCode &operator=(const CCode &c) {
            s = c.s;
            return *this;
        }
//         virtual CCode operator /(const CCode &c) { return CCode(s+'/'+c.s); }
//         virtual void operator -=(const CCode &c) { *this = *this-c; }
//         virtual void operator /=(const CCode &c) { *this = *this/c; }
    };

    CCode operator -(int val, const CCode &c) { return CCode(1.0*val)-c; }
    CCode operator *(int val, const CCode &c) { return CCode(1.0*val)*c; }
    CCode operator -(double val, const CCode &c) { return CCode(val)-c; }
    CCode operator *(double val, const CCode &c) { return CCode(val)*c; }

    ostream &operator <<(ostream & s, const CCode &c) {
        s << c.s;
        return s;
    }

    template<ELEMENT_TYPE type=ET_TRIG> string GenerateCode(int order);

    template<>
    string GenerateCode<ET_TRIG>(int order) {
        expressions.clear();

        CCode x("x");
        CCode y("y");

        TIP<2,CCode> ip(x,y);

        MyFEL<ET_TRIG, L2HighOrderFE<ET_TRIG>> fel(order);

        Array<CCode> shape(fel.ndof);
        fel.MyCalcShape (ip, shape);

        stringstream f;
        f << 
          "float Eval( float x, float y, float z )\n"
          "{                             \n"
          " float result = 0.0;" << endl;

        stringstream ss;
        fel.MyCalcShape (ip, SBLambda([&] (int i, auto c) {
                                      ss << "result += texelFetch( coefficients, inData.element*"+ToString(fel.ndof) + "+"  + ToString(i) + ").r * " + c.s << ";" << endl;
                                      }));

        int i = 0;
        for(auto &s : expressions)
          f << "float var" << ToString(i++) << " = " <<  s << ";" << endl;
        f << ss.str() << endl;
        f << "return result;" << endl;
        f << "}" << endl;
        return f.str();
    }

    template<>
    string GenerateCode<ET_TET>(int order) {
        expressions.clear();

        CCode x("x");
        CCode y("y");
        CCode z("z");

        TIP<3,CCode> ip(x,y,z);

        MyFEL<ET_TET, L2HighOrderFE<ET_TET>> fel(order);

        Array<CCode> shape(fel.ndof);
        fel.MyCalcShape (ip, shape);

        stringstream f;
        f << 
          "float Eval( float x, float y, float z )\n"
          "{                             \n"
          " float result = 0.0;" << endl;

        stringstream ss;
        fel.MyCalcShape (ip, SBLambda([&] (int i, auto c) {
                                      ss << "result += texelFetch( coefficients, inData.element*"+ToString(fel.ndof) + "+"  + ToString(i) + ").r * " + c.s << ";" << endl;
                                      }));

        int i = 0;
        for(auto &s : expressions)
          f << "float var" << ToString(i++) << " = " <<  s << ";" << endl;
        f << ss.str() << endl;
        f << "return result;" << endl;
        f << "}" << endl;
        return f.str();
    }
}
namespace py = pybind11;

template<typename T>
auto MoveToNumpyArray( ngstd::Array<T> &a )
{
  py::capsule free_when_done(&a[0], [](void *f) {
      delete [] reinterpret_cast<T *>(f);
  });
  a.NothingToDelete();
  return py::array_t<T>(a.Size(), &a[0], free_when_done);
}

PYBIND11_MODULE(ngui, m) {

    m.def("GenerateShader", [](int order) {
//           return genshader::GenerateCode<ET_TRIG>(order);
          return genshader::GenerateCode<ET_TET>(order);
          });
    m.def("GetTetData", [] (shared_ptr<ngcomp::MeshAccess> ma) {
        ngstd::Array<float> coordinates;
        ngstd::Array<float> bary_coordinates;
        ngstd::Array<int> element_number;

        size_t ntets = ma->GetNE();
        element_number.SetSize(4*ntets);

        for (auto i : ngcomp::Range(ntets)) {
          auto el = ma->GetElement(ElementId(VOL, i));
          auto verts = el.Vertices();

          ArrayMem<int,4> sorted_vertices{verts[0], verts[1], verts[2], verts[3]};

          BubbleSort (sorted_vertices);
          for (auto ii : Range(sorted_vertices)) {
            auto vnum = sorted_vertices[ii];
            auto v = ma->GetPoint<3>(vnum);
            for (auto k : Range(3)) {
              coordinates.Append(v[k]);
              bary_coordinates.Append( ii==k ? 1.0 : 0.0 );
            }
          }
          element_number[4*i+0] = i;
          element_number[4*i+1] = i;
          element_number[4*i+2] = i;
          element_number[4*i+3] = i;
        }
        return py::make_tuple(
            ntets,
            MoveToNumpyArray(coordinates),
            MoveToNumpyArray(bary_coordinates),
            MoveToNumpyArray(element_number)
        );

    });
    m.def("GetFaceData", [] (shared_ptr<ngcomp::MeshAccess> ma) {
        ngstd::Array<float> coordinates;
        ngstd::Array<float> bary_coordinates;
        ngstd::Array<int> element_number;
        size_t ntrigs;

        Vector<> min(3);
        min = std::numeric_limits<double>::max();
        Vector<> max(3);
        max = std::numeric_limits<double>::lowest();

        auto addVertices = [&] (auto verts) {
            ArrayMem<int,3> sorted_vertices{0,1,2};
            ArrayMem<int,3> unsorted_vertices{verts[0], verts[1], verts[2]};

            BubbleSort (unsorted_vertices, sorted_vertices);
            for (auto j : ngcomp::Range(3)) {
                auto v = ma->GetPoint<3>(verts[j]);
                for (auto k : Range(3)) {
                  coordinates.Append(v[k]);
                  bary_coordinates.Append( sorted_vertices[j]==k ? 1.0 : 0.0 );

                  min[k] = min2(min[k], v[k]);
                  max[k] = max2(max[k], v[k]);
                }
            }
        };

        if(ma->GetDimension()==2)
        {
            ntrigs = ma->GetNE();
            element_number.SetSize(3*ntrigs);
            for (auto i : ngcomp::Range(ntrigs)) {
                addVertices(ma->GetElement(ElementId( VOL, i)).Vertices());
                element_number[3*i+0] = i;
                element_number[3*i+1] = i;
                element_number[3*i+2] = i;
            }
        }
        else if(ma->GetDimension()==3)
        {
            ntrigs = ma->GetNSE();
            element_number.SetSize(3*ntrigs);

            for (auto sel : ma->Elements(BND)) {
                auto sel_vertices = sel.Vertices();

                ArrayMem<int,10> elnums;
                ma->GetFacetElements (sel.Facets()[0], elnums);
                auto el = ma->GetElement(ElementId(VOL, elnums[0]));

                auto el_vertices = el.Vertices();
                ArrayMem<int,4> sorted_vertices{0,1,2,3};
                ArrayMem<int,4> unsorted_vertices{el_vertices[0], el_vertices[1], el_vertices[2], el_vertices[3]};
                BubbleSort (unsorted_vertices, sorted_vertices);

                for (auto j : ngcomp::Range(3)) {
                  auto v = ma->GetPoint<3>(sel_vertices[j]);
                  for (auto k : Range(3)) {
                    coordinates.Append(v[k]);
                    bary_coordinates.Append( unsorted_vertices[k]==sel_vertices[j] ? 1.0 : 0.0 );
                    min[k] = min2(min[k], v[k]);
                    max[k] = max2(max[k], v[k]);
                  }
                }
                element_number[3*sel.Nr()+0] = elnums[0];
                element_number[3*sel.Nr()+1] = elnums[0];
                element_number[3*sel.Nr()+2] = elnums[0];
            }
        }
        else
            throw runtime_error("Unsupported mesh dimension: "+ToString(ma->GetDimension()));

        return py::make_tuple(
            ntrigs,
            MoveToNumpyArray(coordinates),
            MoveToNumpyArray(bary_coordinates),
            MoveToNumpyArray(element_number),
            min, max
        );
    });


    py::bind_vector<std::vector<float>>(m, "VectorFloat");
    m.def("PrintPointer", [] ( std::vector<float> &v) {
          cout << "pointer: " << &v[0] << endl;
          });
    m.def("GetPointer", [] () {
          size_t N = 10000000;
//           float *p = new float[N];
//           std::vector<float> v(100000000);
          auto v = make_unique<std::vector<float>> (N);
          cout << "pointer: " << &(*v)[0] << endl;
//           cout << "got pointer " << p << endl;
//           py::capsule free_when_done(p, [](void *f) {
//             float *p = reinterpret_cast<float *>(f);
//             std::cerr << "Element [0] = " << p[0] << "\n";
//             std::cerr << "freeing memory @ " << f << "\n";
//             delete[] p;
//           });
//           for (auto i : Range(N))
//             p[i] = i+1;
//           cout << p[0] << endl;
//           int i;
//           cin >> i;
//           auto res = py::array_t<float>(N, p, free_when_done);
//           auto res = py::cast(std::move(v));
//           cin >> i;
//           return free_when_done;
          return v;
          });

}
