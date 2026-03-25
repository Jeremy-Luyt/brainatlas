
// q_imgwarp_tps_quicksmallmemory.h
// ============================================================================
// STPS/TPS warping function declarations
// (STPS/TPS 变形函数声明)
//
// Key algorithms:
//   - TPS (Thin-Plate Spline): classical r^2*log(r) kernel warping
//   - STPS (Subsampled TPS):   QR-based affine + non-affine decomposition
//   - Block-by-block processing for memory efficiency
// ============================================================================
#ifndef __Q_IMGWARP_TPS_QUICKSMALLMEMORY_H__
#define __Q_IMGWARP_TPS_QUICKSMALLMEMORY_H__

//#include "stackutil.h"
#include "basic_surf_objs.h"
#include "basic_memory.cpp"   // resolved via project AdditionalIncludeDirectories
#include "newmatap.h"         // newmat matrix library
#include "newmatio.h"         // newmat I/O
#include "q_littleQuickWarp_common.h"


// ----------------------------------------------------------------------------
// q_dfblcokinterp_linear: Trilinear interpolation of sub-DF block to full block
// (三线性插值: 将子采样位移场块插值到完整块)
// Uses 3D pointer for performance (避免频繁的 1D→3D 索引转换)
// ----------------------------------------------------------------------------
bool q_dfblcokinterp_linear(DisplaceFieldF3D ***&pppSubDF,
	const V3DLONG szBlock_x, const V3DLONG szBlock_y, const V3DLONG szBlock_z,
	const V3DLONG substart_x, const V3DLONG substart_y, const V3DLONG substart_z,
	DisplaceFieldF3D ***&pppDFBlock);

// ----------------------------------------------------------------------------
// q_dfblcokinterp_bspline: B-spline interpolation of sub-DF block
// (B样条插值: 使用 4×4×4 控制网格对位移场块插值)
// x_bsplinebasis: precomputed basis matrix from q_nonrigid_ini_bsplinebasis_3D
// ----------------------------------------------------------------------------
bool q_dfblcokinterp_bspline(DisplaceFieldF3D ***&pppSubDF, const Matrix &x_bsplinebasis,
	const V3DLONG sz_gridwnd, const V3DLONG substart_x, const V3DLONG substart_y, const V3DLONG substart_z,
	DisplaceFieldF3D ***&pppDFBlock);

// ----------------------------------------------------------------------------
// q_imgblockwarp: Warp a single image block using a displacement field block
// (使用位移场块对单个图像块进行变形)
// i_interpmethod_img: 0=bilinear (双线性), 1=nearest-neighbor (最近邻)
// ----------------------------------------------------------------------------
template <class T>
bool q_imgblockwarp(T ****&p_img_sub_4d, const V3DLONG *sz_img_sub, DisplaceFieldF3D ***&pppDFBlock,
	const V3DLONG szBlock_x, const V3DLONG szBlock_y, const V3DLONG szBlock_z, const int i_interpmethod_img,
	const V3DLONG substart_x, const V3DLONG substart_y, const V3DLONG substart_z,
	T ****&p_img_warp_4d);


// ----------------------------------------------------------------------------
// imgwarp_smallmemory: Main STPS/TPS block-by-block image warping
// (主变形函数: STPS/TPS 逐块图像变形)
//
// Orchestration:
//   1. Convert markers to Coord3D, compute sub-sampled displacement field (DF)
//   2. For each block: interpolate DF, warp image block, assemble output
//
// Parameters:
//   i_interpmethod_df:  0=trilinear (三线性), 1=bspline (B样条)
//   i_interpmethod_img: 0=bilinear  (双线性), 1=nearest-neighbor (最近邻)
//   sz_img_sub:    target output dimensions (目标输出尺寸)
//   sz_img_sub_ori: original input dimensions (原始输入尺寸)
// ----------------------------------------------------------------------------
template <class T>
bool imgwarp_smallmemory(T *p_img_sub, const V3DLONG *sz_img_sub,
	const QList<ImageMarker> &ql_marker_tar, const QList<ImageMarker> &ql_marker_sub,
	V3DLONG szBlock_x, V3DLONG szBlock_y, V3DLONG szBlock_z, int i_interpmethod_df, int i_interpmethod_img,
	T *&p_img_warp, const V3DLONG *sz_img_sub_ori);


// ----------------------------------------------------------------------------
// interpolate_coord_linear: Trilinear interpolation at arbitrary coordinates
// (在任意坐标处进行三线性插值)
// ----------------------------------------------------------------------------
bool interpolate_coord_linear(MYFLOAT_JBA * interpolatedVal, Coord3D_JBA *c, V3DLONG numCoord,
	MYFLOAT_JBA *** templateVol3d, V3DLONG tsz0, V3DLONG tsz1, V3DLONG tsz2,
	V3DLONG tlow0, V3DLONG tup0, V3DLONG tlow1, V3DLONG tup1, V3DLONG tlow2, V3DLONG tup2);

// ----------------------------------------------------------------------------
// compute_df_tps_subsampled_volume: Classical TPS displacement field
// (经典TPS位移场计算)
//
// Algorithm: Build wL matrix (TPS kernel + affine), solve wW = wL^{-1} * wY,
//   then compute displacement on a subsampled grid using r^2*log(r) kernel.
// (构建 wL 矩阵, 求解 wW = wL^{-1} * wY, 在子采样网格上使用 r^2*log(r) 核计算位移)
// ----------------------------------------------------------------------------
Vol3DSimple<DisplaceFieldF3D> * compute_df_tps_subsampled_volume(const vector <Coord3D_JBA> & matchTargetPos, const vector <Coord3D_JBA> & matchSubjectPos, V3DLONG sz0, V3DLONG sz1, V3DLONG sz2,
	V3DLONG gfactor_x, V3DLONG gfactor_y, V3DLONG gfactor_z);

// ----------------------------------------------------------------------------
// compute_df_stps_subsampled_volume_4bspline: STPS displacement field
// (STPS位移场计算, 用于B样条插值路径)
//
// Algorithm: QR decompose control point matrix P → [q1, q2].
//   Affine term:  d = (P^T P)^{-1} P^T Y
//   Non-affine:   A = q2^T K q2 + lambda*I;  c = q2 * A^{-1} * q2^T (Y - P*d)
//   Displacement: x_stps = x*d + K*c
// (QR分解控制点矩阵P, 分离仿射项d和非仿射项c, 通过正则化参数lambda控制平滑度)
// ----------------------------------------------------------------------------
Vol3DSimple<DisplaceFieldF3D> * compute_df_stps_subsampled_volume_4bspline(const vector <Coord3D_JBA> & matchTargetPos, const vector <Coord3D_JBA> & matchSubjectPos, V3DLONG sz0, V3DLONG sz1, V3DLONG sz2,
	V3DLONG gfactor_x, V3DLONG gfactor_y, V3DLONG gfactor_z);

// ----------------------------------------------------------------------------
// q_nonrigid_ini_bsplinebasis_3D: Build cubic B-spline basis matrix
// (构建三维三次B样条基矩阵, 使用 Kronecker 积: Bx ⊗ By ⊗ Bz)
// n: number of grid points per axis inside the control window
// ----------------------------------------------------------------------------
bool q_nonrigid_ini_bsplinebasis_3D(const long n, Matrix &BxBxB);

// ----------------------------------------------------------------------------
// linearinterp_regularmesh_3d: Regular-mesh linear interpolation
// (规则网格线性插值)
// ----------------------------------------------------------------------------
Vol3DSimple <MYFLOAT_JBA> * linearinterp_regularmesh_3d(V3DLONG sz0, V3DLONG sz1, V3DLONG sz2, Vol3DSimple <MYFLOAT_JBA> * df_regular_grid);

// ----------------------------------------------------------------------------
// STPS decomposition helper: compute affine (d), non-affine (c), and kernels
// (STPS分解辅助函数: 计算仿射项d, 非仿射项c, 以及核矩阵)
// ----------------------------------------------------------------------------
bool compute_df_stps_subsampled_volume_4bspline_per(const vector <Coord3D_JBA> & matchTargetPos, const vector <Coord3D_JBA> & matchSubjectPos, Matrix &x4x4_d, Matrix &xnx4_c, float * &H_X, float * &H_Y,
	float * &H_Z, int nCpt, Image2DSimple<MYFLOAT_JBA> * &cpt_subject);

// ----------------------------------------------------------------------------
// STPS block-wise displacement field computation from precomputed decomposition
// (从预计算分解参数逐块计算STPS位移场)
// ----------------------------------------------------------------------------
Vol3DSimple<DisplaceFieldF3D> * compute_df_stps_subsampled_volume_4bspline_block(int nCpt, Matrix x4x4_d, Matrix xnx4_c, V3DLONG sz0, V3DLONG sz1, V3DLONG sz2, V3DLONG gfactor_x,
	V3DLONG gfactor_y, V3DLONG gfactor_z, float * H_X, float * H_Y, float * H_Z);

// ----------------------------------------------------------------------------
// imgwarp_smallmemory_CYF: CYF variant with displacement field output
// (CYF变体: 额外输出位移场 dis_x/dis_y/dis_z)
// ----------------------------------------------------------------------------
bool imgwarp_smallmemory_CYF(unsigned char *p_img_sub, const V3DLONG *sz_img_sub,
	const QList<ImageMarker> &ql_marker_tar, const QList<ImageMarker> &ql_marker_sub,
	V3DLONG szBlock_x, V3DLONG szBlock_y, V3DLONG szBlock_z, int i_interpmethod_df, int i_interpmethod_img,
	unsigned char *&p_img_warp, const V3DLONG *sz_img_sub_ori);

#endif