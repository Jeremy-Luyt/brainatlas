// ============================================================================
// q_imgwarp_tps_quicksmallmemory.cpp
// Core implementation of TPS/STPS block-by-block image warping
// (TPS/STPS 逐块图像变形核心实现)
//
// Key algorithms:
//   - TPS:  classical thin-plate spline using r^2*log(r) kernel
//           (经典薄板样条, 使用 r^2*log(r) 核)
//   - STPS: subsampled TPS with QR decomposition separating affine (d)
//           and non-affine (c) terms + lambda regularization
//           (子采样TPS, QR分解分离仿射项d和非仿射项c, lambda正则化)
//   - Block-by-block processing minimizes peak memory usage
//           (逐块处理最小化内存峰值)
//
// by Lei Qu, 2012-07-08
// ============================================================================

#include "q_imgwarp_tps_quicksmallmemory.h"
#include <time.h>
extern "C" int gpu_QR(int ncpt, const Matrix &A, Matrix &Q, Matrix &R);
extern "C" int gpu_extendornormal(int ncpt, int n, Matrix &Q);
extern "C" bool gpu_A(int ncpt, const Matrix &q2_t, const Matrix &xnxn_K, Matrix &A);
extern "C" int gpu_A_i(int ncpt, const Matrix &A, Matrix &A_i);
extern "C" int gpu_A_i_new(int ncpt, const Matrix &A, Matrix &A_i);
extern "C" bool gpu_xnxn(int ncpt, const Matrix &q2, const Matrix &A_t, Matrix &C);
extern "C" int gpu_computedistance(int nCpt, V3DLONG gsz2, V3DLONG gsz1, V3DLONG gsz0, V3DLONG gfactor_x, V3DLONG gfactor_y, V3DLONG gfactor_z, Matrix &x4x4_d, Matrix &xnx4_c, float * H_X, float * H_Y, float * H_Z, DisplaceFieldF3D *** df_local_3d);
extern "C" bool gpu_interpolation(const int gsz2, const int gsz1, const int gsz0, DisplaceFieldF3D ***&pppSubDF, const Matrix &x_bsplinebasis, const V3DLONG sz_gridwnd, DisplaceFieldF3D ***&pppDFBlock,
	unsigned char ****&p_img_sub_4d, const V3DLONG *sz_img_sub, const V3DLONG szBlock_x, const V3DLONG szBlock_y, const V3DLONG szBlock_z, const int i_interpmethod_img, unsigned char ****&p_img_warp_4d,
	const V3DLONG *sz_img_sub_ori, const unsigned char *p_img_sub, unsigned char *p_img_warp);
extern "C" Matrix matrixMultiply(const int m, const int n, const int k, Matrix &A, Matrix &B);
// ============================================================================
// q_imgblockwarp: Warp a single image block using a displacement field block
// (使用位移场块对单个图像块进行变形)
//
// For each voxel in the output block:
//   1. Compute source position = output_pos + displacement (计算源位置)
//   2. Boundary check: fill with 0 if out of bounds (边界检查)
//   3. Interpolate source image value (插值源图像值):
//      - i_interpmethod_img=0: bilinear (双线性插值)
//      - i_interpmethod_img=1: nearest-neighbor (最近邻插值)
//
// Uses 4D pointer for fast indexed access (使用4D指针加速索引访问)
// ============================================================================
bool q_imgblockwarp(unsigned char ****&p_img_sub_4d, const V3DLONG *sz_img_sub, DisplaceFieldF3D ***&pppDFBlock,
	const V3DLONG szBlock_x, const V3DLONG szBlock_y, const V3DLONG szBlock_z, const int i_interpmethod_img,
	const V3DLONG substart_x, const V3DLONG substart_y, const V3DLONG substart_z,
	unsigned char ****&p_img_warp_4d)
{
	V3DLONG start_x, start_y, start_z;
	start_x = substart_x*szBlock_x;
	start_y = substart_y*szBlock_y;
	start_z = substart_z*szBlock_z;
	for (V3DLONG z = 0; z<szBlock_z; z++)
		for (V3DLONG y = 0; y<szBlock_y; y++)
			for (V3DLONG x = 0; x<szBlock_x; x++)
			{
		V3DLONG pos_warp[3];
		pos_warp[0] = start_x + x;
		pos_warp[1] = start_y + y;
		pos_warp[2] = start_z + z;
		if (pos_warp[0] >= sz_img_sub[0] || pos_warp[1] >= sz_img_sub[1] || pos_warp[2] >= sz_img_sub[2])
			continue;

		double pos_sub[3];
		pos_sub[0] = pos_warp[0] + pppDFBlock[z][y][x].sx;
		pos_sub[1] = pos_warp[1] + pppDFBlock[z][y][x].sy;
		pos_sub[2] = pos_warp[2] + pppDFBlock[z][y][x].sz;
		if (pos_sub[0]<0 || pos_sub[0]>sz_img_sub[0] - 1 ||
			pos_sub[1]<0 || pos_sub[1]>sz_img_sub[1] - 1 ||
			pos_sub[2]<0 || pos_sub[2]>sz_img_sub[2] - 1)
		{
			for (V3DLONG c = 0; c<sz_img_sub[3]; c++)
				p_img_warp_4d[c][pos_warp[2]][pos_warp[1]][pos_warp[0]] = 0;
			continue;
		}

		//nearest neighbor interpolate
		if (i_interpmethod_img == 1)
		{
			V3DLONG pos_sub_nn[3];
			for (int i = 0; i<3; i++)
			{
				pos_sub_nn[i] = pos_sub[i] + 0.5;
				pos_sub_nn[i] = pos_sub_nn[i]<sz_img_sub[i] ? pos_sub_nn[i] : sz_img_sub[i] - 1;
			}
			for (V3DLONG c = 0; c<sz_img_sub[3]; c++)
				p_img_warp_4d[c][pos_warp[2]][pos_warp[1]][pos_warp[0]] = p_img_sub_4d[c][pos_sub_nn[2]][pos_sub_nn[1]][pos_sub_nn[0]];
		}
		//linear interpolate
		else if (i_interpmethod_img == 0)
		{
			//find 8 neighor pixels boundary
			V3DLONG x_s, x_b, y_s, y_b, z_s, z_b;
			x_s = floor(pos_sub[0]);		x_b = ceil(pos_sub[0]);
			y_s = floor(pos_sub[1]);		y_b = ceil(pos_sub[1]);
			z_s = floor(pos_sub[2]);		z_b = ceil(pos_sub[2]);

			//compute weight for left and right, top and bottom -- 4 neighbor pixel's weight in a slice
			double l_w, r_w, t_w, b_w;
			l_w = 1.0 - (pos_sub[0] - x_s);	r_w = 1.0 - l_w;
			t_w = 1.0 - (pos_sub[1] - y_s);	b_w = 1.0 - t_w;
			//compute weight for higer slice and lower slice
			double u_w, d_w;
			u_w = 1.0 - (pos_sub[2] - z_s);	d_w = 1.0 - u_w;

			//linear interpolate each channel
			for (V3DLONG c = 0; c<sz_img_sub[3]; c++)
			{
				//linear interpolate in higher slice [t_w*(l_w*lt+r_w*rt)+b_w*(l_w*lb+r_w*rb)]
				double higher_slice;
				higher_slice = t_w*(l_w*p_img_sub_4d[c][z_s][y_s][x_s] + r_w*p_img_sub_4d[c][z_s][y_s][x_b]) +
					b_w*(l_w*p_img_sub_4d[c][z_s][y_b][x_s] + r_w*p_img_sub_4d[c][z_s][y_b][x_b]);
				//linear interpolate in lower slice [t_w*(l_w*lt+r_w*rt)+b_w*(l_w*lb+r_w*rb)]
				double lower_slice;
				lower_slice = t_w*(l_w*p_img_sub_4d[c][z_b][y_s][x_s] + r_w*p_img_sub_4d[c][z_b][y_s][x_b]) +
					b_w*(l_w*p_img_sub_4d[c][z_b][y_b][x_s] + r_w*p_img_sub_4d[c][z_b][y_b][x_b]);
				//linear interpolate the current position [u_w*higher_slice+d_w*lower_slice]
				double intval = (u_w*higher_slice + d_w*lower_slice + 0.5);
				p_img_warp_4d[c][pos_warp[2]][pos_warp[1]][pos_warp[0]] = intval;
			}
		}

			}

	return true;
}


// ============================================================================
// imgwarp_smallmemory: Main TPS/STPS block-by-block image warping orchestrator
// (主变形函数: TPS/STPS 逐块图像变形编排器)
//
// Workflow (工作流程):
//   1. Convert QList<ImageMarker> → vector<Coord3D_JBA> (坐标格式转换)
//   2. Compute sub-sampled displacement field (计算子采样位移场):
//      - df_method=0 → compute_df_tps_subsampled_volume (TPS, trilinear)
//      - df_method=1 → compute_df_stps_subsampled_volume_4bspline (STPS, bspline)
//   3. Allocate output image + 4D pointers (分配输出图像和4D指针)
//   4. For each block (逐块处理):
//      a) Interpolate sub-DF → full-resolution DF block (插值子采样DF到全分辨率)
//      b) Warp image block using DF (用DF变形图像块)
//   5. Release memory (释放内存)
//
// Parameters:
//   i_interpmethod_df:  0=trilinear (三线性), 1=bspline (B样条)
//   i_interpmethod_img: 0=bilinear  (双线性), 1=nearest-neighbor (最近邻)
//   sz_img_sub:    target output dimensions (目标输出尺寸)
//   sz_img_sub_ori: original input dimensions (原始输入尺寸)
// ============================================================================
bool imgwarp_smallmemory(unsigned char *p_img_sub, const V3DLONG *sz_img_sub,
	const QList<ImageMarker> &ql_marker_tar, const QList<ImageMarker> &ql_marker_sub,
	V3DLONG szBlock_x, V3DLONG szBlock_y, V3DLONG szBlock_z, int i_interpmethod_df, int i_interpmethod_img,
	unsigned char *&p_img_warp, const V3DLONG *sz_img_sub_ori)
{
	//check parameters
	if (p_img_sub == 0 || sz_img_sub == 0)
	{
		printf("ERROR: p_img_sub or sz_img_sub is invalid.\n");
		return false;
	}
	if (ql_marker_tar.size() == 0 || ql_marker_sub.size() == 0 || ql_marker_tar.size() != ql_marker_sub.size())
	{
		printf("ERROR: target or subject control points is invalid!\n");
		return false;
	}
	if (szBlock_x <= 0 || szBlock_y <= 0 || szBlock_z <= 0)
	{
		printf("ERROR: block size is invalid!\n");
		return false;
	}
	if (szBlock_x >= sz_img_sub[0] || szBlock_y >= sz_img_sub[1] || szBlock_z >= sz_img_sub[2])
	{
		printf("ERROR: block size should smaller than the image size!\n");
		return false;
	}
	if (i_interpmethod_df != 0 && i_interpmethod_df != 1)
	{
		printf("ERROR: DF_interp_method should be 0(linear) or 1(bspline)!\n");
		return false;
	}
	if (i_interpmethod_img != 0 && i_interpmethod_img != 1)
	{
		printf("ERROR: img_interp_method should be 0(linear) or 1(nn)!\n");
		return false;
	}
	if (i_interpmethod_df == 1 && (szBlock_x != szBlock_y || szBlock_x != szBlock_z))
	{
		printf("ERROR: df_interp_method=bspline need szBlock_x=szBlock_y=szBlock_z!\n");
		return false;
	}
	if (p_img_warp)
	{
		printf("WARNNING: output image pointer is not null, original memeroy it point to will be released!\n");
		if (p_img_warp) 			{ delete[]p_img_warp;		p_img_warp = 0; }
	}

	//------------------------------------------------------------------------------------------------------------------------------------
	printf(">>>>compute the subsampled displace field \n");
	vector<Coord3D_JBA> matchTargetPos, matchSubjectPos;
	for (V3DLONG i = 0; i < ql_marker_tar.size(); i++)
	{
		Coord3D_JBA tmpc;
		tmpc.x = 1 * ql_marker_tar.at(i).x;	tmpc.y = 1 * ql_marker_tar.at(i).y;	tmpc.z = 1 * ql_marker_tar.at(i).z;
		matchTargetPos.push_back(tmpc);
		tmpc.x = 1 * ql_marker_sub.at(i).x;	tmpc.y = 1 * ql_marker_sub.at(i).y;	tmpc.z = 1 * ql_marker_sub.at(i).z;
		matchSubjectPos.push_back(tmpc);
	}
	/*int nCpt = matchTargetPos.size();
	Image2DSimple<MYFLOAT_JBA> * cpt_subject=0;
	Matrix xnx4_c(nCpt,4);
	Matrix x4x4_d(4,4);
	float *H_X = 0;
	float *H_Y = 0;
	float *H_Z = 0;*/
	clock_t BSP;
	BSP = clock();
	/*if (!(compute_df_stps_subsampled_volume_4bspline_per(matchTargetPos, matchSubjectPos, x4x4_d, xnx4_c, H_X, H_Y, H_Z, nCpt, cpt_subject)))
	{
	printf("ERROR:compute_df_stps_subsampled_volume_4bspline_per() return false. \n");
	return false;
	}*/
	Vol3DSimple<DisplaceFieldF3D> *pSubDF = 0;
	if (i_interpmethod_df == 0)
		pSubDF = compute_df_tps_subsampled_volume(matchTargetPos, matchSubjectPos, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], szBlock_x, szBlock_y, szBlock_z);
	else
	{
		pSubDF = compute_df_stps_subsampled_volume_4bspline(matchTargetPos, matchSubjectPos, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], szBlock_x, szBlock_y, szBlock_z);

		/*pSubDF = compute_df_stps_subsampled_volume_4bspline_block(nCpt, x4x4_d, xnx4_c, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], szBlock_x, szBlock_y, szBlock_z, H_X, H_Y, H_Z);
		free(H_X);
		free(H_Y);
		free(H_Z);

		if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }*/
	}

	printf("\t>>BSP time consume: %.2f s\n", (float)(clock() - BSP) / CLOCKS_PER_SEC);
	if (!pSubDF)
	{
		printf("Fail to produce the subsampled DF.\n");
		return false;
	}
	DisplaceFieldF3D ***pppSubDF = pSubDF->getData3dHandle();
	printf("subsampled DF size: [%ld,%ld,%ld]\n", pSubDF->sz0(), pSubDF->sz1(), pSubDF->sz2());

	//------------------------------------------------------------------------
	//allocate memory
	printf(">>>>interpolate the subsampled displace field and warp block by block\n");
	p_img_warp = new unsigned char[sz_img_sub[0] * sz_img_sub[1] * sz_img_sub[2] * sz_img_sub[3]]();
	if (!p_img_warp)
	{
		printf("ERROR: Fail to allocate memory for p_img_warp.\n");
		if (pSubDF)				{ delete pSubDF;					pSubDF = 0; }
		return false;
	}
	unsigned char ****p_img_warp_4d = 0, ****p_img_sub_4d = 0;
	if (!new4dpointer(p_img_warp_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3], p_img_warp) ||
		!new4dpointer(p_img_sub_4d, sz_img_sub_ori[0], sz_img_sub_ori[1], sz_img_sub_ori[2], sz_img_sub_ori[3], p_img_sub))
	{
		printf("ERROR: Fail to allocate memory for the 4d pointer of image.\n");
		if (p_img_warp_4d) 		{ delete4dpointer(p_img_warp_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
		if (p_img_sub_4d) 		{ delete4dpointer(p_img_sub_4d, sz_img_sub_ori[0], sz_img_sub_ori[1], sz_img_sub_ori[2], sz_img_sub_ori[3]); }
		if (p_img_warp) 			{ delete[]p_img_warp;			p_img_warp = 0; }
		if (pSubDF)				{ delete pSubDF;					pSubDF = 0; }
		return false;
	}
	Vol3DSimple<DisplaceFieldF3D> *pDFBlock = new Vol3DSimple<DisplaceFieldF3D>(szBlock_x, szBlock_y, szBlock_z);
	if (!pDFBlock)
	{
		printf("ERROR: Fail to allocate memory for pDFBlock.\n");
		if (p_img_warp_4d) 		{ delete4dpointer(p_img_warp_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
		if (p_img_sub_4d) 		{ delete4dpointer(p_img_sub_4d, sz_img_sub_ori[0], sz_img_sub_ori[1], sz_img_sub_ori[2], sz_img_sub_ori[3]); }
		if (p_img_warp) 			{ delete[]p_img_warp;			p_img_warp = 0; }
		if (pSubDF)				{ delete pSubDF;					pSubDF = 0; }
		return false;
	}
	DisplaceFieldF3D ***pppDFBlock = pDFBlock->getData3dHandle();

	//------------------------------------------------------------------------
	//interpolate the SubDfBlock to DFBlock and do warp block by block
	if (i_interpmethod_df == 0)		printf("\t>>subsampled displace field interpolate method: trilinear\n");
	else if (i_interpmethod_df == 1)	printf("\t>>subsampled displace field interpolate method: B-spline\n");
	if (i_interpmethod_img == 0)		printf("\t>>image value               interpolate method: trilinear\n");
	else if (i_interpmethod_img == 1)	printf("\t>>image value               interpolate method: nearest neighbor\n");
	double q_dfblcokinterp_bspline_time = 0.0;
	double q_imgblockwarp_time = 0.0;
	if (i_interpmethod_df == 0)	//linear interpolate the SubDfBlock to DFBlock and do warp block by block
	{
		for (V3DLONG substart_z = 0; substart_z < pSubDF->sz2() - 1; substart_z++)
			for (V3DLONG substart_y = 0; substart_y < pSubDF->sz1() - 1; substart_y++)
				for (V3DLONG substart_x = 0; substart_x < pSubDF->sz0() - 1; substart_x++)
				{
					//linear interpolate the SubDfBlock to DFBlock
					q_dfblcokinterp_linear(pppSubDF, szBlock_x, szBlock_y, szBlock_z, substart_x, substart_y, substart_z, pppDFBlock);
					//warp image block using DFBlock
					q_imgblockwarp(p_img_sub_4d, sz_img_sub, pppDFBlock, szBlock_x, szBlock_y, szBlock_z, i_interpmethod_img, substart_x, substart_y, substart_z, p_img_warp_4d);
				}
	}
	else						//bspline interpolate the SubDfBlock to DFBlock and do warp block by block
	{
		//initialize the bspline basis function
		V3DLONG sz_gridwnd = szBlock_x;
		Matrix x_bsplinebasis(pow(double(sz_gridwnd), 3.0), pow(4.0, 3.0));
		if (!q_nonrigid_ini_bsplinebasis_3D(sz_gridwnd, x_bsplinebasis))
		{
			printf("ERROR: q_ini_bsplinebasis_3D() return false!\n");
			if (p_img_warp_4d) 		{ delete4dpointer(p_img_warp_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
			if (p_img_sub_4d) 		{ delete4dpointer(p_img_sub_4d, sz_img_sub_ori[0], sz_img_sub_ori[1], sz_img_sub_ori[2], sz_img_sub_ori[3]); }
			if (p_img_warp) 			{ delete[]p_img_warp;			p_img_warp = 0; }
			if (pSubDF)				{ delete pSubDF;					pSubDF = 0; }
			return false;
		}
		printf("\t>>x_bsplinebasis:[%d,%d]\n", x_bsplinebasis.nrows(), x_bsplinebasis.ncols());
		int g_type = 0;
		int gsz2 = pSubDF->sz2();
		int gsz1 = pSubDF->sz1();
		int gsz0 = pSubDF->sz0();
		if (g_type == 0)
		{
			clock_t stps_interpolation;
			stps_interpolation = clock();

			gpu_interpolation(gsz2, gsz1, gsz0, pppSubDF, x_bsplinebasis, sz_gridwnd, pppDFBlock, p_img_sub_4d, sz_img_sub, szBlock_x, szBlock_y, szBlock_z, i_interpmethod_img, p_img_warp_4d, sz_img_sub_ori, p_img_sub, p_img_warp);


			printf("\t>>interpolation time consume %.2f s\n", (float)(clock() - stps_interpolation) / CLOCKS_PER_SEC);
		}
		else
		{

			for (V3DLONG substart_z = 0; substart_z < pSubDF->sz2() - 1 - 2; substart_z++)
				for (V3DLONG substart_y = 0; substart_y < pSubDF->sz1() - 1 - 2; substart_y++)
					for (V3DLONG substart_x = 0; substart_x < pSubDF->sz0() - 1 - 2; substart_x++)
					{
						//bspline interpolate the SubDfBlock to DFBlock
						clock_t start_bspline = clock();
						q_dfblcokinterp_bspline(pppSubDF, x_bsplinebasis, sz_gridwnd, substart_x, substart_y, substart_z, pppDFBlock);
						clock_t end_bspline = clock();
						q_dfblcokinterp_bspline_time += double(end_bspline - start_bspline) / CLOCKS_PER_SEC;
						//warp image block using DFBlock
						clock_t start_warp = clock();
						q_imgblockwarp(p_img_sub_4d, sz_img_sub, pppDFBlock, szBlock_x, szBlock_y, szBlock_z, i_interpmethod_img, substart_x, substart_y, substart_z, p_img_warp_4d);
						clock_t end_warp = clock();
						q_imgblockwarp_time += double(end_warp - start_warp) / CLOCKS_PER_SEC;
					}
			// ������
			std::cout << "Total time spent in q_dfblcokinterp_bspline(): " << q_dfblcokinterp_bspline_time << " seconds" << std::endl;
			std::cout << "Total time spent in q_imgblockwarp(): " << q_imgblockwarp_time << " seconds" << std::endl;
		}

		//free memory
		if (p_img_warp_4d) 		{ delete4dpointer(p_img_warp_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
		if (p_img_sub_4d) 		{ delete4dpointer(p_img_sub_4d, sz_img_sub_ori[0], sz_img_sub_ori[1], sz_img_sub_ori[2], sz_img_sub_ori[3]); }
		if (pDFBlock)			{ delete pDFBlock;			pDFBlock = 0; }
		if (pSubDF)				{ delete pSubDF;				pSubDF = 0; }

		return true;
	}
}


// ============================================================================
// q_dfblcokinterp_linear: Trilinear interpolation of sub-sampled DF block
// (子采样位移场块的三线性插值)
//
// Takes a 2x2x2 corner of the sub-DF and interpolates it to a full
// szBlock_x * szBlock_y * szBlock_z block. Each axis (sx, sy, sz) is
// interpolated independently via linearinterp_regularmesh_3d.
// (取子DF的 2x2x2 角点, 通过三线性插值扩展到完整块大小)
// ============================================================================
bool q_dfblcokinterp_linear(DisplaceFieldF3D ***&pppSubDF,
	const V3DLONG szBlock_x, const V3DLONG szBlock_y, const V3DLONG szBlock_z,
	const V3DLONG substart_x, const V3DLONG substart_y, const V3DLONG substart_z,
	DisplaceFieldF3D ***&pppDFBlock)
{
	Vol3DSimple <MYFLOAT_JBA> 		*pDFBlock1C = 0;
	MYFLOAT_JBA			    	***pppDFBlock1C = 0;
	Vol3DSimple<MYFLOAT_JBA> 		*pSubDFBlock1c = new Vol3DSimple<MYFLOAT_JBA>(2, 2, 2);
	MYFLOAT_JBA 		     	***pppSubDFBlock1c = pSubDFBlock1c->getData3dHandle();

	V3DLONG i, j, k, is, js, ks;
	//x
	for (k = 0; k<2; k++)
		for (j = 0; j<2; j++)
			for (i = 0; i<2; i++)
			{
		ks = k + substart_z;
		js = j + substart_y;
		is = i + substart_x;
		pppSubDFBlock1c[k][j][i] = pppSubDF[ks][js][is].sx;
			}
	pDFBlock1C = linearinterp_regularmesh_3d(szBlock_x, szBlock_y, szBlock_z, pSubDFBlock1c);
	pppDFBlock1C = pDFBlock1C->getData3dHandle();
	for (k = 0; k<szBlock_z; k++) for (j = 0; j<szBlock_y; j++) for (i = 0; i<szBlock_x; i++) pppDFBlock[k][j][i].sx = pppDFBlock1C[k][j][i];
	if (pDFBlock1C) { delete pDFBlock1C; pDFBlock1C = 0; }
	//y
	for (k = 0; k<2; k++)
		for (j = 0; j<2; j++)
			for (i = 0; i<2; i++)
			{
		ks = k + substart_z;
		js = j + substart_y;
		is = i + substart_x;
		pppSubDFBlock1c[k][j][i] = pppSubDF[ks][js][is].sy;
			}
	pDFBlock1C = linearinterp_regularmesh_3d(szBlock_x, szBlock_y, szBlock_z, pSubDFBlock1c);
	pppDFBlock1C = pDFBlock1C->getData3dHandle();
	for (k = 0; k<szBlock_z; k++) for (j = 0; j<szBlock_y; j++) for (i = 0; i<szBlock_x; i++) pppDFBlock[k][j][i].sy = pppDFBlock1C[k][j][i];
	if (pDFBlock1C) { delete pDFBlock1C; pDFBlock1C = 0; }
	//z
	for (k = 0; k<2; k++)
		for (j = 0; j<2; j++)
			for (i = 0; i<2; i++)
			{
		ks = k + substart_z;
		js = j + substart_y;
		is = i + substart_x;
		pppSubDFBlock1c[k][j][i] = pppSubDF[ks][js][is].sz;
			}
	pDFBlock1C = linearinterp_regularmesh_3d(szBlock_x, szBlock_y, szBlock_z, pSubDFBlock1c);
	pppDFBlock1C = pDFBlock1C->getData3dHandle();
	for (k = 0; k<szBlock_z; k++) for (j = 0; j<szBlock_y; j++) for (i = 0; i<szBlock_x; i++) pppDFBlock[k][j][i].sz = pppDFBlock1C[k][j][i];
	if (pDFBlock1C) { delete pDFBlock1C; pDFBlock1C = 0; }

	if (pSubDFBlock1c)		{ delete pSubDFBlock1c;		pSubDFBlock1c = 0; }

	return true;
}


// ============================================================================
// q_dfblcokinterp_bspline: Cubic B-spline interpolation of sub-DF block
// (子采样位移场块的三次B样条插值)
//
// Uses a 4x4x4 control-point window from the sub-DF. The precomputed
// bspline basis matrix (from q_nonrigid_ini_bsplinebasis_3D) is multiplied
// with the vectorized control points to produce the full-resolution block.
// Formula: DF_block = BxBxB * control_points
// (使用 4x4x4 控制点窗口, 通过预计算的B样条基矩阵与向量化控制点
//  相乘得到完整块: DF_block = BxBxB * control_points)
// ============================================================================
bool q_dfblcokinterp_bspline(DisplaceFieldF3D ***&pppSubDF, const Matrix &x_bsplinebasis,
	const V3DLONG sz_gridwnd, const V3DLONG substart_x, const V3DLONG substart_y, const V3DLONG substart_z,
	DisplaceFieldF3D ***&pppDFBlock)
{
	//vectorize the gridblock's nodes position that use for interpolation
	Matrix x1D_gridblock(4 * 4 * 4, 3);
	long ind = 1;
	for (long dep = substart_z; dep<substart_z + 4; dep++)
		for (long col = substart_x; col<substart_x + 4; col++)
			for (long row = substart_y; row<substart_y + 4; row++)
			{
		x1D_gridblock(ind, 1) = pppSubDF[dep][row][col].sx;
		x1D_gridblock(ind, 2) = pppSubDF[dep][row][col].sy;
		x1D_gridblock(ind, 3) = pppSubDF[dep][row][col].sz;
		ind++;
			}
	//printf("grid[%d %d],%f %f %f\n", substart_y, substart_x, x1D_gridblock(1, 3), x1D_gridblock(1, 2), x1D_gridblock(1, 1));

	//cubic B-spline interpolate the vectorized grid block
	Matrix x1D_gridblock_int = x_bsplinebasis*x1D_gridblock;
	//printf("grid[%d %d],%f %f %f\n", substart_y, substart_x, x1D_gridblock_int(1, 3), x1D_gridblock_int(1, 2), x1D_gridblock_int(1, 1));
	//de-vectorize the interpolated grid block and save back to vec4D_grid_int
	ind = 1;
	for (long zz = 0; zz<sz_gridwnd; zz++)
		for (long xx = 0; xx<sz_gridwnd; xx++)
			for (long yy = 0; yy<sz_gridwnd; yy++)
			{
		pppDFBlock[zz][yy][xx].sx = x1D_gridblock_int(ind, 1);
		pppDFBlock[zz][yy][xx].sy = x1D_gridblock_int(ind, 2);
		pppDFBlock[zz][yy][xx].sz = x1D_gridblock_int(ind, 3);
		ind++;
			}

	return true;
}

// ============================================================================
// compute_df_tps_subsampled_volume: Classical TPS displacement field
// (经典TPS位移场计算)
//
// Mathematical formulation (数学公式):
//   Given n control point pairs (target_i, subject_i):
//   1. Build kernel matrix wR(i,j) = 2*r^2*log(r), r = |target_i - target_j|
//      (构建TPS核矩阵, 使用 r^2*log(r) 基函数)
//   2. Build augmented matrix wL = [wR, wP; wP^T, 0] where wP = [1, x, y, z]
//      (构建增广矩阵 wL)
//   3. Solve wW = wL^{-1} * wY for weights (求解权重矩阵 wW)
//   4. For each grid point: displacement = sum(wW_i * kernel_i) - position
//      (对每个网格点计算位移 = 权重×核值之和 - 当前位置)
//
// Output: Sub-sampled DF on grid with spacing (gfactor_x, gfactor_y, gfactor_z)
// (输出: 子采样位移场, 网格间距为 gfactor)
// ============================================================================
Vol3DSimple<DisplaceFieldF3D> * compute_df_tps_subsampled_volume(const vector <Coord3D_JBA> & matchTargetPos, const vector <Coord3D_JBA> & matchSubjectPos, V3DLONG sz0, V3DLONG sz1, V3DLONG sz2,
	V3DLONG gfactor_x, V3DLONG gfactor_y, V3DLONG gfactor_z)
{
	int nCpt = matchTargetPos.size();
	if (nCpt != matchSubjectPos.size() || nCpt <= 0)
	{
		fprintf(stderr, "The input vectors are invalid in compute_tps_df_field().\n");
		return 0;
	}

	Image2DSimple<MYFLOAT_JBA> * cpt_target = new Image2DSimple<MYFLOAT_JBA>(3, nCpt);
	Image2DSimple<MYFLOAT_JBA> * cpt_subject = new Image2DSimple<MYFLOAT_JBA>(3, nCpt);
	if (!cpt_target || !cpt_target->valid() || !cpt_subject || !cpt_subject->valid())
	{
		fprintf(stderr, "Fail to allocate memory.");
		if (cpt_target) { delete cpt_target; cpt_target = 0; }
		if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
		return 0;
	}

	V3DLONG n;

	MYFLOAT_JBA ** cpt_target_ref = cpt_target->getData2dHandle();
	MYFLOAT_JBA ** cpt_subject_ref = cpt_subject->getData2dHandle();
	//printf("\n---------------------------------\n");
	for (n = 0; n<nCpt; n++)
	{
		cpt_target_ref[n][0] = matchTargetPos.at(n).x;
		cpt_target_ref[n][1] = matchTargetPos.at(n).y;
		cpt_target_ref[n][2] = matchTargetPos.at(n).z;

		cpt_subject_ref[n][0] = matchSubjectPos.at(n).x;
		cpt_subject_ref[n][1] = matchSubjectPos.at(n).y;
		cpt_subject_ref[n][2] = matchSubjectPos.at(n).z;

		//printf("n=%d \tx=[%5.3f -> %5.3f] y=[%5.3f -> %5.3f] z=[%5.3f -> %5.3f] \n",
		//       n, cpt_target_ref[n][0], cpt_subject_ref[n][0], cpt_target_ref[n][1], cpt_subject_ref[n][1], cpt_target_ref[n][2], cpt_subject_ref[n][2]);
	}
	//printf("\n#################################\n");

	Matrix wR(nCpt, nCpt);

	double tmp, s;

	V3DLONG i, j, k;
	for (j = 0; j<nCpt; j++)
	{
		for (i = 0; i<nCpt; i++)
		{
			s = 0.0;
			tmp = cpt_target_ref[i][0] - cpt_target_ref[j][0]; s += tmp*tmp;
			tmp = cpt_target_ref[i][1] - cpt_target_ref[j][1]; s += tmp*tmp;
			tmp = cpt_target_ref[i][2] - cpt_target_ref[j][2]; s += tmp*tmp;
			wR(i + 1, j + 1) = 2 * s*log(s + 1e-20);
		}
	}

	Matrix wP(nCpt, 4);
	for (j = 0; j<nCpt; j++)
	{
		wP(j + 1, 1) = 1;
		wP(j + 1, 2) = cpt_target_ref[j][0];
		wP(j + 1, 3) = cpt_target_ref[j][1];
		wP(j + 1, 4) = cpt_target_ref[j][2];
	}

	Matrix wL(nCpt + 4, nCpt + 4);
	wL.submatrix(1, nCpt, 1, nCpt) = wR;
	wL.submatrix(1, nCpt, nCpt + 1, nCpt + 4) = wP;
	wL.submatrix(nCpt + 1, nCpt + 4, 1, nCpt) = wP.t();
	wL.submatrix(nCpt + 1, nCpt + 4, nCpt + 1, nCpt + 4) = 0;

	Matrix wY(nCpt + 4, 3);
	for (j = 0; j<nCpt; j++)
	{
		wY(j + 1, 1) = cpt_subject_ref[j][0];
		wY(j + 1, 2) = cpt_subject_ref[j][1];
		wY(j + 1, 3) = cpt_subject_ref[j][2];
	}
	wY.submatrix(nCpt + 1, nCpt + 4, 1, 3) = 0;

	Matrix wW;

	Try
	{
		wW = wL.i() * wY;
	}
		CatchAll
	{
		fprintf(stderr, "Fail to find the inverse of the wL matrix.\n");

		if (cpt_target) { delete cpt_target; cpt_target = 0; }
		if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
		return 0;
	}

	V3DLONG p;

	V3DLONG gsz0 = (V3DLONG)(ceil((double(sz0) / gfactor_x))) + 1, gsz1 = (V3DLONG)(ceil((double(sz1) / gfactor_y))) + 1, gsz2 = (V3DLONG)(ceil((double(sz2) / gfactor_z))) + 1;
	Vol3DSimple<DisplaceFieldF3D> * df_local = new Vol3DSimple<DisplaceFieldF3D>(gsz0, gsz1, gsz2);
	DisplaceFieldF3D *** df_local_3d = df_local->getData3dHandle();

	if (!df_local || !df_local->valid())
	{
		fprintf(stderr, "Fail to allocate memory for the subsampled DF volume memory [%d].\n", __LINE__);

		if (cpt_target) { delete cpt_target; cpt_target = 0; }
		if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
		if (df_local) { delete df_local; df_local = 0; }
		return 0;
	}

	V3DLONG ndimpt = 3;
	double * dist = new double[nCpt + ndimpt + 1];
	if (!dist)
	{
		fprintf(stderr, "Fail to allocate memory dist for tps warping [%d].\n", __LINE__);

		if (cpt_target) { delete cpt_target; cpt_target = 0; }
		if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
		if (df_local) { delete df_local; df_local = 0; }
		return 0;
	}

	printf("-------------------- Now compute the distances of pixels to the mapping points. -------\n\n");

	DisplaceFieldF3D * df_local_1d = df_local->getData1dHandle();
	for (k = 0; k<df_local->getTotalElementNumber(); k++)
	{
		df_local_1d[k].sz = df_local_1d[k].sy = df_local_1d[k].sx = 0;
	}
	for (k = 0; k<gsz2; k++)
	{
		for (j = 0; j<gsz1; j++)
		{
			for (i = 0; i<gsz0; i++)
			{
				for (n = 0; n<nCpt; n++)
				{
					s = 0;
					tmp = (i*gfactor_x) - cpt_target_ref[n][0]; s += tmp*tmp;
					tmp = (j*gfactor_y) - cpt_target_ref[n][1]; s += tmp*tmp;
					tmp = (k*gfactor_z) - cpt_target_ref[n][2]; s += tmp*tmp;
					dist[n] = 2 * s*log(s + 1e-20);
				}

				dist[nCpt] = 1;
				dist[nCpt + 1] = i*gfactor_x;
				dist[nCpt + 2] = j*gfactor_y;
				dist[nCpt + 3] = k*gfactor_z;

				s = 0;  for (p = 0; p<nCpt + ndimpt + 1; p++) { s += dist[p] * wW(p + 1, 1); }
				df_local_3d[k][j][i].sx = s - i*gfactor_x;

				s = 0;  for (p = 0; p<nCpt + ndimpt + 1; p++) { s += dist[p] * wW(p + 1, 2); }
				df_local_3d[k][j][i].sy = s - j*gfactor_y;

				s = 0;  for (p = 0; p<nCpt + ndimpt + 1; p++) { s += dist[p] * wW(p + 1, 3); }
				df_local_3d[k][j][i].sz = s - k*gfactor_z;
			}//i
		}//j
		printf("z=%ld ", k); fflush(stdout);
	}//k
	printf("\n");

	if (dist) { delete[]dist; dist = 0; }
	if (cpt_target) { delete cpt_target; cpt_target = 0; }
	if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }

	return df_local;
}

// ============================================================================
// compute_df_stps_subsampled_volume_4bspline: STPS displacement field
// (STPS位移场计算, 用于B样条插值路径)
//
// STPS (Subsampled Thin-Plate Spline) algorithm (算法流程):
//   1. Build kernel K(i,j) = -|xi - xj| (negative Euclidean distance)
//      (构建核矩阵 K, 使用负欧氏距离)
//   2. QR decompose control point matrix P = [1, x, y, z] → [q1, q2, R]
//      (QR分解控制点矩阵P)
//   3. Compute affine term d:
//      d = R^{-1} * q1^T * (Y - K*c)
//      (计算仿射项d)
//   4. Compute non-affine term c:
//      A = q2^T * K * q2 + lambda * I   (lambda=0.2 for smoothness)
//      c = q2 * A^{-1} * q2^T * Y
//      (计算非仿射项c, lambda=0.2控制平滑度)
//   5. For each grid point: x_stps = x * d + K_point * c
//      displacement = x_stps - position
//      (对每个网格点: 位移 = 仿射变换 + 非仿射变换 - 当前位置)
//
// Note: grid size is +2 for B-spline border support
// (注意: 网格尺寸加 2 用于B样条边界支撑)
// ============================================================================
Vol3DSimple<DisplaceFieldF3D> * compute_df_stps_subsampled_volume_4bspline(const vector <Coord3D_JBA> & matchTargetPos, const vector <Coord3D_JBA> & matchSubjectPos, V3DLONG sz0, V3DLONG sz1, V3DLONG sz2,
	V3DLONG gfactor_x, V3DLONG gfactor_y, V3DLONG gfactor_z)
{
	int nCpt = matchTargetPos.size();
	if (nCpt != matchSubjectPos.size() || nCpt <= 0)
	{
		fprintf(stderr, "The input vectors are invalid in compute_tps_df_field().\n");
		return 0;
	}

	Image2DSimple<MYFLOAT_JBA> * cpt_target = new Image2DSimple<MYFLOAT_JBA>(3, nCpt);
	Image2DSimple<MYFLOAT_JBA> * cpt_subject = new Image2DSimple<MYFLOAT_JBA>(3, nCpt);
	if (!cpt_target || !cpt_target->valid() || !cpt_subject || !cpt_subject->valid())
	{
		fprintf(stderr, "Fail to allocate memory.");
		if (cpt_target) { delete cpt_target; cpt_target = 0; }
		if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
		return 0;
	}

	V3DLONG n;
	Matrix x4x4_d, xnx4_c, xnxn_K;
	if (xnx4_c.nrows() != nCpt || xnx4_c.ncols() != 4)
		xnx4_c.ReSize(nCpt, 4);
	if (x4x4_d.nrows() != 4 || xnx4_c.ncols() != 4)
		x4x4_d.ReSize(4, 4);
	if (xnxn_K.nrows() != nCpt || xnxn_K.ncols() != nCpt)
		xnxn_K.ReSize(nCpt, nCpt);





	MYFLOAT_JBA ** cpt_target_ref = cpt_target->getData2dHandle();
	MYFLOAT_JBA ** cpt_subject_ref = cpt_subject->getData2dHandle();

	printf("\n---------------------------------\n");
	for (n = 0; n<nCpt; n++)
	{
		cpt_target_ref[n][0] = matchTargetPos.at(n).x;
		cpt_target_ref[n][1] = matchTargetPos.at(n).y;
		cpt_target_ref[n][2] = matchTargetPos.at(n).z;

		cpt_subject_ref[n][0] = matchSubjectPos.at(n).x;
		cpt_subject_ref[n][1] = matchSubjectPos.at(n).y;
		cpt_subject_ref[n][2] = matchSubjectPos.at(n).z;

		printf("n=%d \tx=[%5.3f -> %5.3f] y=[%5.3f -> %5.3f] z=[%5.3f -> %5.3f] \n",
			n, cpt_target_ref[n][0], cpt_subject_ref[n][0], cpt_target_ref[n][1], cpt_subject_ref[n][1], cpt_target_ref[n][2], cpt_subject_ref[n][2]);
	}
	printf("\n#################################\n");
	float *H_X, *H_Y, *H_Z;
	H_X = (float*)malloc(nCpt * sizeof(float)); H_Y = (float*)malloc(nCpt * sizeof(float)); H_Z = (float*)malloc(nCpt * sizeof(float));
	for (unsigned V3DLONG j = 0; j<nCpt; j++)
	{
		H_X[j] = cpt_subject_ref[j][0]; H_Y[j] = cpt_subject_ref[j][1]; H_Z[j] = cpt_subject_ref[j][2];
	}
	//compute K=-r=-|xi-xj|

	double d_x, d_y, d_z;
	for (unsigned V3DLONG i = 0; i<nCpt; i++)
		for (unsigned V3DLONG j = 0; j<nCpt; j++)
		{
		d_x = cpt_subject_ref[i][0] - cpt_subject_ref[j][0];
		d_y = cpt_subject_ref[i][1] - cpt_subject_ref[j][1];
		d_z = cpt_subject_ref[i][2] - cpt_subject_ref[j][2];
		xnxn_K(i + 1, j + 1) = -sqrt(d_x*d_x + d_y*d_y + d_z*d_z);
		}
	//	printf("\t>>xnxn_K time consume %.6f ms\n", (float)(clock() - stps_start) / CLOCKS_PER_SEC * 1000);
	int cdd = 1;
	clock_t c;
	c = clock();
	if (cdd == 0)
	{
		Matrix X(nCpt, 4), Y(nCpt, 4);
		Matrix Q_ori(nCpt, nCpt); Q_ori = 0.0;
		for (V3DLONG i = 0; i < nCpt; i++)
		{
			Q_ori(i + 1, 1) = X(i + 1, 1) = 1;
			Q_ori(i + 1, 2) = X(i + 1, 2) = cpt_subject_ref[i][0];
			Q_ori(i + 1, 3) = X(i + 1, 3) = cpt_subject_ref[i][1];
			Q_ori(i + 1, 4) = X(i + 1, 4) = cpt_subject_ref[i][2];

			Y(i + 1, 1) = 1;
			Y(i + 1, 2) = cpt_target_ref[i][0];
			Y(i + 1, 3) = cpt_target_ref[i][1];
			Y(i + 1, 4) = cpt_target_ref[i][2];
		}
		Matrix Q(nCpt, nCpt), Q_x(nCpt, nCpt);
		clock_t stps_start1;
		stps_start1 = clock();
		Matrix R(4, 4);
		clock_t stps_startqr;
		stps_startqr = clock();
		//gpu_QR(nCpt, Q_ori, Q_x, R);
		printf("\t>>QR�ֽ� time consume %.6f s\n", (float)(clock() - stps_startqr) / CLOCKS_PER_SEC);
		printf("\t>>QR�ֽ� time consume %.6f s\n", (float)(clock() - stps_start1) / CLOCKS_PER_SEC);
		clock_t stps_start2;
		stps_start2 = clock();
		UpperTriangularMatrix R1;
		QRZ(Q_ori, R1);
		Q_x = Q_ori;
		clock_t stps_start;
		stps_start = clock();
		gpu_extendornormal(nCpt, 4, Q_x);
		Q = Q_x;
		printf("\t>>extend_orthonormal���� time consume %.6f s\n", (float)(clock() - stps_start2) / CLOCKS_PER_SEC);
		Matrix q1 = Q.columns(1, 4);
		Matrix q2 = Q.columns(5, nCpt);
		//Matrix r = R.submatrix(1, 4, 1, 4);
		Matrix r = R1.submatrix(1, 4, 1, 4);;
		printf("\t>>q1��q2��r���� time consume %.6f s\n", (float)(clock() - stps_start2) / CLOCKS_PER_SEC);
		//Matrix A(nCpt - 4, nCpt - 4); A = 0.0;
		clock_t stps_start3;
		stps_start3 = clock();
		Matrix KQ(nCpt, nCpt - 4);
		KQ = matrixMultiply(nCpt, nCpt - 4, nCpt, xnxn_K, q2);
		Matrix q2t = q2.t();
		Matrix A1 = matrixMultiply(nCpt - 4, nCpt - 4, nCpt, q2t, KQ);
		Matrix A = A1 + IdentityMatrix(nCpt - 4)*0.2;
		//Matrix A = q2.t()*KQ + IdentityMatrix(nCpt - 4)*0.2;
		//	Matrix A = q2.t()*xnxn_K*q2 + IdentityMatrix(nCpt - 4)*0.2;
		//gpu_A(nCpt, q2, xnxn_K, A);
		//printf("\t>>A���� time consume %.6f s\n", (float)(clock() - stps_start3) / CLOCKS_PER_SEC);
		//A = A + IdentityMatrix(nCpt - 4)*0.2;
		Matrix A_i(nCpt - 4, nCpt - 4); A_i = 0.0;
		clock_t stps_startni;
		stps_startni = clock();
		//gpu_A_i(nCpt, A, A_i);
		//gpu_A_i_new(nCpt, A, A_i);
		A_i = A.i();
		printf("\t>>A_i_new���� time consume %.6f ms\n", (float)(clock() - stps_startni));
		//Matrix xnx4_c1(nCpt, nCpt);
		//clock_t stps_start6;
		//stps_start6 = clock();
		////gpu_xnxn(nCpt, q2, A_i, xnx4_c1);
		////xnx4_c = xnx4_c1*Y;
		Matrix q2A(nCpt, nCpt - 4);
		q2A = matrixMultiply(nCpt, nCpt - 4, nCpt - 4, q2, A_i);
		Matrix c1 = matrixMultiply(nCpt, nCpt, nCpt - 4, q2A, q2t);
		xnx4_c = c1*Y;
		//xnx4_c = q2A*q2.t()*Y;
		//	xnx4_c = q2*(A_i*q2.t()*Y);
		printf("\t>>total xnx4_c���� time consume %.6f s\n", (float)(clock() - stps_start3) / CLOCKS_PER_SEC);
		clock_t stps_start4;
		stps_start4 = clock();
		x4x4_d = r.i()*q1.t()*(Y - xnxn_K*xnx4_c);
		printf("\t>>x4x4_d���� time consume %.6f ms\n", (float)(clock() - stps_start4) / CLOCKS_PER_SEC * 1000);
		printf("\t>>the total consumption %.6f s\n", (float)(clock() - stps_start) / CLOCKS_PER_SEC);

	}
	else
	{
		//clock_t c;
		//c = clock();
		Matrix X(nCpt, 4), Y(nCpt, 4);
		Matrix Q(nCpt, nCpt); Q = 0.0;
		for (V3DLONG i = 0; i < nCpt; i++)
		{
			Q(i + 1, 1) = X(i + 1, 1) = 1;
			Q(i + 1, 2) = X(i + 1, 2) = cpt_subject_ref[i][0];
			Q(i + 1, 3) = X(i + 1, 3) = cpt_subject_ref[i][1];
			Q(i + 1, 4) = X(i + 1, 4) = cpt_subject_ref[i][2];
			Y(i + 1, 1) = 1;
			Y(i + 1, 2) = cpt_target_ref[i][0];
			Y(i + 1, 3) = cpt_target_ref[i][1];
			Y(i + 1, 4) = cpt_target_ref[i][2];
		}
		UpperTriangularMatrix R;
		QRZ(Q, R);
		clock_t stps_start;
		stps_start = clock();
		extend_orthonormal(Q, 4);//otherwise q2=0

		Matrix q1 = Q.columns(1, 4);
		Matrix q2 = Q.columns(5, nCpt);
		Matrix r = R.submatrix(1, 4, 1, 4);
		//compute non-affine term c which decomposed from TPS
		Matrix A = q2.t()*xnxn_K*q2 + IdentityMatrix(nCpt - 4)*0.2;
		xnx4_c = q2*(A.i()*q2.t()*Y);
		//compute affine term d (normal)
		x4x4_d = r.i()*q1.t()*(Y - xnxn_K*xnx4_c);
		printf("\t>>xnxn_K time consume %.2f s\n", (float)(clock() - stps_start) / CLOCKS_PER_SEC);
	}
	/*Matrix wR(nCpt, nCpt);
	double tmp, s;
	V3DLONG i, j, k;
	for (j = 0; j<nCpt; j++)
	{
	for (i = 0; i<nCpt; i++)
	{
	s = 0.0;
	tmp = cpt_target_ref[i][0] - cpt_target_ref[j][0]; s += tmp*tmp;
	tmp = cpt_target_ref[i][1] - cpt_target_ref[j][1]; s += tmp*tmp;
	tmp = cpt_target_ref[i][2] - cpt_target_ref[j][2]; s += tmp*tmp;
	wR(i + 1, j + 1) = 2 * s*log(s + 1e-20);
	}
	}

	Matrix wP(nCpt, 4);
	for (j = 0; j<nCpt; j++)
	{
	wP(j + 1, 1) = 1;
	wP(j + 1, 2) = cpt_target_ref[j][0];
	wP(j + 1, 3) = cpt_target_ref[j][1];
	wP(j + 1, 4) = cpt_target_ref[j][2];
	}

	Matrix wL(nCpt + 4, nCpt + 4);
	wL.submatrix(1, nCpt, 1, nCpt) = wR;
	wL.submatrix(1, nCpt, nCpt + 1, nCpt + 4) = wP;
	wL.submatrix(nCpt + 1, nCpt + 4, 1, nCpt) = wP.t();
	wL.submatrix(nCpt + 1, nCpt + 4, nCpt + 1, nCpt + 4) = 0;

	Matrix wY(nCpt + 4, 3);
	for (j = 0; j<nCpt; j++)
	{
	wY(j + 1, 1) = cpt_subject_ref[j][0];
	wY(j + 1, 2) = cpt_subject_ref[j][1];
	wY(j + 1, 3) = cpt_subject_ref[j][2];
	}
	wY.submatrix(nCpt + 1, nCpt + 4, 1, 3) = 0;

	Matrix wW;

	Try
	{
	wW = wL.i() * wY;
	}
	CatchAll
	{
	fprintf(stderr, "Fail to find the inverse of the wL matrix.\n");

	if (cpt_target) { delete cpt_target; cpt_target = 0; }
	if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
	return 0;
	}*/

	V3DLONG p;

	//	V3DLONG gsz0 = (V3DLONG)(ceil((double(sz0)/gfactor_x)))+1, gsz1 = (V3DLONG)(ceil((double(sz1)/gfactor_y)))+1, gsz2 = (V3DLONG)(ceil((double(sz2)/gfactor_z)))+1;
	V3DLONG gsz0 = (V3DLONG)(ceil((double(sz0) / gfactor_x))) + 1 + 2, gsz1 = (V3DLONG)(ceil((double(sz1) / gfactor_y))) + 1 + 2, gsz2 = (V3DLONG)(ceil((double(sz2) / gfactor_z))) + 1 + 2;//+2 for bspline
	Vol3DSimple<DisplaceFieldF3D> * df_local = new Vol3DSimple<DisplaceFieldF3D>(gsz0, gsz1, gsz2);
	DisplaceFieldF3D *** df_local_3d = df_local->getData3dHandle();

	if (!df_local || !df_local->valid())
	{
		fprintf(stderr, "Fail to allocate memory for the subsampled DF volume memory [%d].\n", __LINE__);

		if (cpt_target) { delete cpt_target; cpt_target = 0; }
		if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
		if (df_local) { delete df_local; df_local = 0; }
		return 0;
	}

	/*V3DLONG ndimpt = 3;
	double * dist = new double[nCpt + ndimpt + 1];
	if (!dist)
	{
	fprintf(stderr, "Fail to allocate memory dist for tps warping [%d].\n", __LINE__);

	if (cpt_target) { delete cpt_target; cpt_target = 0; }
	if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
	if (df_local) { delete df_local; df_local = 0; }
	return 0;
	}*/

	printf("-------------------- Now compute the distances of pixels to the mapping points. -------\n\n");

	V3DLONG i, j, k;
	DisplaceFieldF3D * df_local_1d = df_local->getData1dHandle();
	for (k = 0; k<df_local->getTotalElementNumber(); k++)
	{
		df_local_1d[k].sz = df_local_1d[k].sy = df_local_1d[k].sx = 0;
	}
	clock_t stps_computedistance;
	stps_computedistance = clock();
	//gpu_computedistance(nCpt, gsz2, gsz1, gsz0, gfactor_x, gfactor_y, gfactor_z, x4x4_d, xnx4_c, H_X, H_Y, H_Z, df_local_3d);
	printf("\t>>computedistance time consume %.2f s\n", (float)(clock() - stps_computedistance) / CLOCKS_PER_SEC);
	for (k = 0; k<gsz2; k++)
	{
		for (j = 0; j<gsz1; j++)
		{
			for (i = 0; i<gsz0; i++)
			{
				Matrix x_ori(1, 4);
				x_ori(1, 1) = 1.0;
				x_ori(1, 2) = (i - 1)*gfactor_x;
				x_ori(1, 3) = (j - 1)*gfactor_y;
				x_ori(1, 4) = (k - 1)*gfactor_z;
				Matrix x_stps(1, 4);
				Matrix xmxn_K;
				xmxn_K.resize(1, nCpt);
				double d_x, d_y, d_z;
				for (unsigned V3DLONG n = 0; n<nCpt; n++)
				{
					d_x = (i - 1)*gfactor_x - H_X[n];
					d_y = (j - 1)*gfactor_y - H_Y[n];
					d_z = (k - 1)*gfactor_z - H_Z[n];
					xmxn_K(1, n + 1) = -sqrt(d_x*d_x + d_y*d_y + d_z*d_z);
				}
				x_stps = x_ori*x4x4_d + xmxn_K*xnx4_c;
				df_local_3d[k][j][i].sx = x_stps(1, 2) - (i - 1)*gfactor_x;
				df_local_3d[k][j][i].sy = x_stps(1, 3) - (j - 1)*gfactor_y;
				df_local_3d[k][j][i].sz = x_stps(1, 4) - (k - 1)*gfactor_z;


			}//i
		}//j
		printf("z=%ld ", k); fflush(stdout);
	}//k
	printf("\n");

	//if (dist) { delete[]dist; dist = 0; }
	free(H_X);
	free(H_Y);
	free(H_Z);
	if (cpt_target) { delete cpt_target; cpt_target = 0; }
	if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }

	return df_local;
}

// ============================================================================
// q_nonrigid_ini_bsplinebasis_3D: Construct 3D cubic B-spline basis matrix
// (构建三维三次B样条基矩阵)
//
// Steps (步骤):
//   1. Define cubic B-spline basis B = (1/6)*[-1 3 -3 1; 3 -6 3 0; ...]
//      (定义三次B样条基矩阵)
//   2. Build parameter matrix T where T(i,:) = [t^3, t^2, t, 1]
//      (构建参数矩阵)
//   3. Compute TB = T * B (1D basis, n x 4)
//      (计算一维基函数)
//   4. 3D basis via Kronecker product: BxBxB = KP(KP(TB, TB), TB)
//      Result: n^3 x 4^3 matrix for 3D interpolation
//      (通过 Kronecker 积扩展到3D: n^3 x 64 矩阵)
// ============================================================================
bool q_nonrigid_ini_bsplinebasis_3D(const long n, Matrix &BxBxB)
{
	if (n <= 0)
	{
		printf("ERROR: n should > 0!\n");
		return false;
	}

	// Cubic B-spline basis matrix (三次B样条基矩阵)
	Matrix B(4, 4);
	B.row(1) << -1 << 3 << -3 << 1;
	B.row(2) << 3 << -6 << 3 << 0;
	B.row(3) << -3 << 0 << 3 << 0;
	B.row(4) << 1 << 4 << 1 << 0;
	B /= 6.0;

	//construct T(i,:)=[t^3 t^2 t^1 1]
	Matrix T(n, 4);
	double t_step = 1.0 / n;
	for (long i = 0; i<n; i++)
	{
		double t = t_step*i;
		for (long j = 0; j <= 3; j++)
			T(i + 1, j + 1) = pow(t, 3 - j);
	}

	//construct B-spline basis/blending functions B=T*B
	Matrix TB = T*B;//n x 4

	//construct B-spline basis/blending functions for 2D interpolation B=BxB
	Matrix BxB = KP(TB, TB);//n^2 x 4^2
	//construct B-spline basis/blending functions for 3D interpolation B=BxBxB
	BxBxB = KP(BxB, TB);//n^3 x 4^3

	return true;
}

// ============================================================================
// linearinterp_regularmesh_3d: Trilinear interpolation on a regular 3D mesh
// (规则三维网格上的三线性插值)
//
// Interpolates a coarse regular grid (df_regular_grid) to a fine output
// volume of size (sz0, sz1, sz2). Used to expand sub-DF to full resolution.
// (将粗规则网格插值到精细输出体积, 用于将子DF扩展到全分辨率)
// ============================================================================
Vol3DSimple <MYFLOAT_JBA> * linearinterp_regularmesh_3d(V3DLONG sz0, V3DLONG sz1, V3DLONG sz2, Vol3DSimple <MYFLOAT_JBA> * df_regular_grid)
{
	V3DLONG k, j, i;

	if (!df_regular_grid || !df_regular_grid->valid())
	{
		fprintf(stderr, "The pointer is not correct.\n");
		return 0;
	}
	MYFLOAT_JBA *** df_grid3d = df_regular_grid->getData3dHandle();
	//	V3DLONG n0 = df_regular_grid->sz0()-3, n1 = df_regular_grid->sz1()-3, n2 = df_regular_grid->sz2()-3;//-3 for B-spline?
	V3DLONG n0 = df_regular_grid->sz0() - 1, n1 = df_regular_grid->sz1() - 1, n2 = df_regular_grid->sz2() - 1;//modified by qul @ 120710
	if (n0 <= 0 || n1 <= 0 || n2 <= 0)
	{
		fprintf(stderr, "The size  is not correct.\n");
		return 0;
	}
	if (sz0 <= 0 || sz1 <= 0 || sz2 <= 0)
	{
		fprintf(stderr, "The size of the DF to be computed is not correct.\n");
		return 0;
	}

	Vol3DSimple <MYFLOAT_JBA> * df_field = new Vol3DSimple <MYFLOAT_JBA>(sz0, sz1, sz2);
	if (!df_field || !df_field->valid())
	{
		fprintf(stderr, "Fail to allocate memory.\n");
		if (df_field) { delete df_field; df_field = 0; }
		return 0;
	}

	MYFLOAT_JBA * df_field_ref1d = df_field->getData1dHandle();
	for (i = 0; i<df_field->getTotalElementNumber(); i++)
	{
		df_field_ref1d[i] = 0;
	}

	Coord3D_JBA *c = new Coord3D_JBA[df_field->getTotalElementNumber()];
	double nf0 = (double)n0 / sz0, nf1 = (double)n1 / sz1, nf2 = (double)n2 / sz2;
	V3DLONG cnt = 0;
	for (k = 0; k<sz2; k++)
	{
		double k_tmp = (double)k*nf2;
		for (j = 0; j<sz1; j++)
		{
			double j_tmp = (double)j*nf1;
			for (i = 0; i<sz0; i++)
			{
				c[cnt].x = i*nf0;
				c[cnt].y = j_tmp;
				c[cnt].z = k_tmp;
				cnt++;
			}
		}
	}

	interpolate_coord_linear(df_field_ref1d, c, df_field->getTotalElementNumber(),
		df_grid3d, df_regular_grid->sz0(), df_regular_grid->sz1(), df_regular_grid->sz2(),
		0, n0 - 1 + 1, 0, n1 - 1 + 1, 0, n2 - 1 + 1);

	if (c) { delete[]c; c = 0; }
	return df_field;
}

// ============================================================================
// interpolate_coord_linear: Trilinear interpolation at arbitrary 3D coordinates
// (在任意三维坐标处进行三线性插值)
//
// For each coordinate in c[], performs trilinear interpolation in the 3D
// template volume. Handles all degenerate cases (face/edge/corner aligned)
// for numerical stability.
// (对每个坐标点在三维模板体积中进行三线性插值, 处理所有退化情况)
// ============================================================================
bool interpolate_coord_linear(MYFLOAT_JBA * interpolatedVal, Coord3D_JBA *c, V3DLONG numCoord,
	MYFLOAT_JBA *** templateVol3d, V3DLONG tsz0, V3DLONG tsz1, V3DLONG tsz2,
	V3DLONG tlow0, V3DLONG tup0, V3DLONG tlow1, V3DLONG tup1, V3DLONG tlow2, V3DLONG tup2)
{
	if (!interpolatedVal || !c || numCoord <= 0 ||
		!templateVol3d || tsz0 <= 0 || tsz1 <= 0 || tsz2 <= 0 ||
		tlow0<0 || tlow0 >= tsz0 || tup0<0 || tup0 >= tsz0 || tlow0>tup0 ||
		tlow1<0 || tlow1 >= tsz1 || tup1<0 || tup1 >= tsz1 || tlow1>tup1 ||
		tlow2<0 || tlow2 >= tsz2 || tup2<0 || tup2 >= tsz2 || tlow2>tup2)
	{
		fprintf(stderr, "Invalid parameters! [%s][%d]\n", __FILE__, __LINE__);
		return false;
	}

	double curpx, curpy, curpz;
	V3DLONG cpx0, cpx1, cpy0, cpy1, cpz0, cpz1;

	for (V3DLONG ipt = 0; ipt<numCoord; ipt++)
	{
		if (c[ipt].x< tlow0 || c[ipt].x> tup0 || c[ipt].y< tlow1 || c[ipt].y> tup1 || c[ipt].z< tlow2 || c[ipt].z> tup2)
		{
			interpolatedVal[ipt] = 0;
			continue;
		}

		curpx = c[ipt].x; curpx = (curpx<tlow0) ? tlow0 : curpx; curpx = (curpx>tup0) ? tup0 : curpx;
#ifndef POSITIVE_Y_COORDINATE
		curpy = tsz1 - 1 - c[ipt].y; curpy = (curpy<tlow1) ? tlow1 : curpy; curpy = (curpy>tup1) ? tup1 : curpy;
#else
		curpy = c[ipt].y; curpy = (curpy<tlow1) ? tlow1 : curpy; curpy = (curpy>tup1) ? tup1 : curpy;
#endif
		curpz = c[ipt].z; curpz = (curpz<tlow2) ? tlow2 : curpz; curpz = (curpz>tup2) ? tup2 : curpz;

		cpx0 = V3DLONG(floor(curpx)); cpx1 = V3DLONG(ceil(curpx));
		cpy0 = V3DLONG(floor(curpy)); cpy1 = V3DLONG(ceil(curpy));
		cpz0 = V3DLONG(floor(curpz)); cpz1 = V3DLONG(ceil(curpz));

		if (cpz0 == cpz1)
		{
			if (cpy0 == cpy1)
			{
				if (cpx0 == cpx1)
				{
					interpolatedVal[ipt] = (MYFLOAT_JBA)(templateVol3d[cpz0][cpy0][cpx0]);
				}
				else
				{
					double w0x0y0z = (cpx1 - curpx);
					double w1x0y0z = (curpx - cpx0);
					interpolatedVal[ipt] = (MYFLOAT_JBA)(w0x0y0z * double(templateVol3d[cpz0][cpy0][cpx0]) +
						w1x0y0z * double(templateVol3d[cpz0][cpy0][cpx1]));
				}
			}
			else
			{
				if (cpx0 == cpx1)
				{
					double w0x0y0z = (cpy1 - curpy);
					double w0x1y0z = (curpy - cpy0);
					interpolatedVal[ipt] = (MYFLOAT_JBA)(w0x0y0z * double(templateVol3d[cpz0][cpy0][cpx0]) +
						w0x1y0z * double(templateVol3d[cpz0][cpy1][cpx0]));
				}
				else
				{
					double w0x0y0z = (cpx1 - curpx)*(cpy1 - curpy);
					double w0x1y0z = (cpx1 - curpx)*(curpy - cpy0);
					double w1x0y0z = (curpx - cpx0)*(cpy1 - curpy);
					double w1x1y0z = (curpx - cpx0)*(curpy - cpy0);
					interpolatedVal[ipt] = (MYFLOAT_JBA)(w0x0y0z * double(templateVol3d[cpz0][cpy0][cpx0]) +
						w0x1y0z * double(templateVol3d[cpz0][cpy1][cpx0]) +
						w1x0y0z * double(templateVol3d[cpz0][cpy0][cpx1]) +
						w1x1y0z * double(templateVol3d[cpz0][cpy1][cpx1]));
				}
			}
		}
		else
		{
			if (cpy0 == cpy1)
			{
				if (cpx0 == cpx1)
				{
					double w0x0y0z = (cpz1 - curpz);
					double w0x0y1z = (curpz - cpz0);

					interpolatedVal[ipt] = (MYFLOAT_JBA)(w0x0y0z * double(templateVol3d[cpz0][cpy0][cpx0]) + w0x0y1z * double(templateVol3d[cpz1][cpy0][cpx0]));
				}
				else
				{
					double w0x0y0z = (cpx1 - curpx)*(cpz1 - curpz);
					double w0x0y1z = (cpx1 - curpx)*(curpz - cpz0);

					double w1x0y0z = (curpx - cpx0)*(cpz1 - curpz);
					double w1x0y1z = (curpx - cpx0)*(curpz - cpz0);

					interpolatedVal[ipt] = (MYFLOAT_JBA)(w0x0y0z * double(templateVol3d[cpz0][cpy0][cpx0]) + w0x0y1z * double(templateVol3d[cpz1][cpy0][cpx0]) +
						w1x0y0z * double(templateVol3d[cpz0][cpy0][cpx1]) + w1x0y1z * double(templateVol3d[cpz1][cpy0][cpx1]));
				}
			}
			else
			{
				if (cpx0 == cpx1)
				{
					double w0x0y0z = (cpy1 - curpy)*(cpz1 - curpz);
					double w0x0y1z = (cpy1 - curpy)*(curpz - cpz0);

					double w0x1y0z = (curpy - cpy0)*(cpz1 - curpz);
					double w0x1y1z = (curpy - cpy0)*(curpz - cpz0);

					interpolatedVal[ipt] = (MYFLOAT_JBA)(w0x0y0z * double(templateVol3d[cpz0][cpy0][cpx0]) + w0x0y1z * double(templateVol3d[cpz1][cpy0][cpx0]) +
						w0x1y0z * double(templateVol3d[cpz0][cpy1][cpx0]) + w0x1y1z * double(templateVol3d[cpz1][cpy1][cpx0]));
				}
				else
				{
					double w0x0y0z = (cpx1 - curpx)*(cpy1 - curpy)*(cpz1 - curpz);
					double w0x0y1z = (cpx1 - curpx)*(cpy1 - curpy)*(curpz - cpz0);

					double w0x1y0z = (cpx1 - curpx)*(curpy - cpy0)*(cpz1 - curpz);
					double w0x1y1z = (cpx1 - curpx)*(curpy - cpy0)*(curpz - cpz0);

					double w1x0y0z = (curpx - cpx0)*(cpy1 - curpy)*(cpz1 - curpz);
					double w1x0y1z = (curpx - cpx0)*(cpy1 - curpy)*(curpz - cpz0);

					double w1x1y0z = (curpx - cpx0)*(curpy - cpy0)*(cpz1 - curpz);
					double w1x1y1z = (curpx - cpx0)*(curpy - cpy0)*(curpz - cpz0);

					interpolatedVal[ipt] = (MYFLOAT_JBA)(w0x0y0z * double(templateVol3d[cpz0][cpy0][cpx0]) + w0x0y1z * double(templateVol3d[cpz1][cpy0][cpx0]) +
						w0x1y0z * double(templateVol3d[cpz0][cpy1][cpx0]) + w0x1y1z * double(templateVol3d[cpz1][cpy1][cpx0]) +
						w1x0y0z * double(templateVol3d[cpz0][cpy0][cpx1]) + w1x0y1z * double(templateVol3d[cpz1][cpy0][cpx1]) +
						w1x1y0z * double(templateVol3d[cpz0][cpy1][cpx1]) + w1x1y1z * double(templateVol3d[cpz1][cpy1][cpx1]));
				}
			}
		}

	}

	return true;
}


bool compute_df_stps_subsampled_volume_4bspline_per(const vector <Coord3D_JBA> & matchTargetPos, const vector <Coord3D_JBA> & matchSubjectPos, Matrix &x4x4_d, Matrix &xnx4_c, float * &H_X, float * &H_Y,
	float * &H_Z, int nCpt, Image2DSimple<MYFLOAT_JBA> * &cpt_subject)
{
	//nCpt = matchTargetPos.size();
	if (nCpt != matchSubjectPos.size() || nCpt <= 0)
	{
		fprintf(stderr, "The input vectors are invalid in compute_tps_df_field().\n");
		return 0;
	}

	Image2DSimple<MYFLOAT_JBA> * cpt_target = new Image2DSimple<MYFLOAT_JBA>(3, nCpt);
	//Image2DSimple<MYFLOAT_JBA> * cpt_subject = new Image2DSimple<MYFLOAT_JBA>(3, nCpt);
	cpt_subject = new Image2DSimple<MYFLOAT_JBA>(3, nCpt);
	if (!cpt_target || !cpt_target->valid() || !cpt_subject || !cpt_subject->valid())
	{
		fprintf(stderr, "Fail to allocate memory.");
		if (cpt_target) { delete cpt_target; cpt_target = 0; }
		if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
		return 0;
	}

	V3DLONG n;
	//Matrix x4x4_d, xnx4_c, xnxn_K;
	Matrix xnxn_K;
	if (xnx4_c.nrows() != nCpt || xnx4_c.ncols() != 4)
		xnx4_c.ReSize(nCpt, 4);
	if (x4x4_d.nrows() != 4 || xnx4_c.ncols() != 4)
		x4x4_d.ReSize(4, 4);
	if (xnxn_K.nrows() != nCpt || xnxn_K.ncols() != nCpt)
		xnxn_K.ReSize(nCpt, nCpt);





	MYFLOAT_JBA ** cpt_target_ref = cpt_target->getData2dHandle();
	MYFLOAT_JBA ** cpt_subject_ref = cpt_subject->getData2dHandle();

	printf("\n---------------------------------\n");
	for (n = 0; n<nCpt; n++)
	{
		cpt_target_ref[n][0] = matchTargetPos.at(n).x;
		cpt_target_ref[n][1] = matchTargetPos.at(n).y;
		cpt_target_ref[n][2] = matchTargetPos.at(n).z;

		cpt_subject_ref[n][0] = matchSubjectPos.at(n).x;
		cpt_subject_ref[n][1] = matchSubjectPos.at(n).y;
		cpt_subject_ref[n][2] = matchSubjectPos.at(n).z;

		printf("n=%d \tx=[%5.3f -> %5.3f] y=[%5.3f -> %5.3f] z=[%5.3f -> %5.3f] \n",
			n, cpt_target_ref[n][0], cpt_subject_ref[n][0], cpt_target_ref[n][1], cpt_subject_ref[n][1], cpt_target_ref[n][2], cpt_subject_ref[n][2]);
	}
	printf("\n#################################\n");
	//float *H_X, *H_Y, *H_Z;
	H_X = (float*)malloc(nCpt * sizeof(float)); H_Y = (float*)malloc(nCpt * sizeof(float)); H_Z = (float*)malloc(nCpt * sizeof(float));
	for (unsigned V3DLONG j = 0; j<nCpt; j++)
	{
		H_X[j] = cpt_subject_ref[j][0]; H_Y[j] = cpt_subject_ref[j][1]; H_Z[j] = cpt_subject_ref[j][2];
	}
	//compute K=-r=-|xi-xj|

	double d_x, d_y, d_z;
	for (unsigned V3DLONG i = 0; i<nCpt; i++)
		for (unsigned V3DLONG j = 0; j<nCpt; j++)
		{
		d_x = cpt_subject_ref[i][0] - cpt_subject_ref[j][0];
		d_y = cpt_subject_ref[i][1] - cpt_subject_ref[j][1];
		d_z = cpt_subject_ref[i][2] - cpt_subject_ref[j][2];
		xnxn_K(i + 1, j + 1) = -sqrt(d_x*d_x + d_y*d_y + d_z*d_z);
		}
	//	printf("\t>>xnxn_K time consume %.6f ms\n", (float)(clock() - stps_start) / CLOCKS_PER_SEC * 1000);
	int cdd = 0;
	clock_t c;
	c = clock();
	if (cdd == 0)
	{
		Matrix X(nCpt, 4), Y(nCpt, 4);
		Matrix Q_ori(nCpt, nCpt); Q_ori = 0.0;
		for (V3DLONG i = 0; i < nCpt; i++)
		{
			Q_ori(i + 1, 1) = X(i + 1, 1) = 1;
			Q_ori(i + 1, 2) = X(i + 1, 2) = cpt_subject_ref[i][0];
			Q_ori(i + 1, 3) = X(i + 1, 3) = cpt_subject_ref[i][1];
			Q_ori(i + 1, 4) = X(i + 1, 4) = cpt_subject_ref[i][2];

			Y(i + 1, 1) = 1;
			Y(i + 1, 2) = cpt_target_ref[i][0];
			Y(i + 1, 3) = cpt_target_ref[i][1];
			Y(i + 1, 4) = cpt_target_ref[i][2];
		}
		Matrix Q(nCpt, nCpt), Q_x(nCpt, nCpt);
		clock_t stps_start1;
		stps_start1 = clock();
		Matrix R(4, 4);
		clock_t stps_startqr;
		stps_startqr = clock();
		gpu_QR(nCpt, Q_ori, Q_x, R);
		printf("\t>>QR�ֽ� time consume %.6f s\n", (float)(clock() - stps_startqr) / CLOCKS_PER_SEC);
		printf("\t>>QR�ֽ� time consume %.6f s\n", (float)(clock() - stps_start1) / CLOCKS_PER_SEC);
		clock_t stps_start2;
		stps_start2 = clock();
		UpperTriangularMatrix R1;
		//	QRZ(Q_ori, R1);
		//	Q = Q_ori;
		clock_t stps_start;
		stps_start = clock();
		gpu_extendornormal(nCpt, 4, Q_x);
		Q = Q_x;
		printf("\t>>extend_orthonormal���� time consume %.6f s\n", (float)(clock() - stps_start2) / CLOCKS_PER_SEC);
		Matrix q1 = Q.columns(1, 4);
		Matrix q2 = Q.columns(5, nCpt);
		Matrix r = R.submatrix(1, 4, 1, 4);
		//	Matrix r = R1.submatrix(1, 4, 1, 4);;
		printf("\t>>q1��q2��r���� time consume %.6f s\n", (float)(clock() - stps_start2) / CLOCKS_PER_SEC);
		//Matrix A(nCpt - 4, nCpt - 4); A = 0.0;
		clock_t stps_start3;
		stps_start3 = clock();
		Matrix KQ(nCpt, nCpt - 4);
		KQ = matrixMultiply(nCpt, nCpt - 4, nCpt, xnxn_K, q2);
		Matrix q2t = q2.t();
		Matrix A1 = matrixMultiply(nCpt - 4, nCpt - 4, nCpt, q2t, KQ);
		Matrix A = A1 + IdentityMatrix(nCpt - 4)*0.2;
		//Matrix A = q2.t()*KQ + IdentityMatrix(nCpt - 4)*0.2;
		//	Matrix A = q2.t()*xnxn_K*q2 + IdentityMatrix(nCpt - 4)*0.2;
		//gpu_A(nCpt, q2, xnxn_K, A);
		//printf("\t>>A���� time consume %.6f s\n", (float)(clock() - stps_start3) / CLOCKS_PER_SEC);
		//A = A + IdentityMatrix(nCpt - 4)*0.2;
		Matrix A_i(nCpt - 4, nCpt - 4); A_i = 0.0;
		//clock_t stps_startni;
		//stps_startni = clock();
		gpu_A_i(nCpt, A, A_i);
		//gpu_A_i_new(nCpt, A, A_i);
		//printf("\t>>A_i���� time consume %.6f s\n", (float)(clock() - stps_startni) / CLOCKS_PER_SEC);
		//Matrix xnx4_c1(nCpt, nCpt);
		//clock_t stps_start6;
		//stps_start6 = clock();
		////gpu_xnxn(nCpt, q2, A_i, xnx4_c1);
		////xnx4_c = xnx4_c1*Y;
		Matrix q2A(nCpt, nCpt - 4);
		q2A = matrixMultiply(nCpt, nCpt - 4, nCpt - 4, q2, A_i);
		Matrix c1 = matrixMultiply(nCpt, nCpt, nCpt - 4, q2A, q2t);
		xnx4_c = c1*Y;
		//xnx4_c = q2A*q2.t()*Y;
		//	xnx4_c = q2*(A_i*q2.t()*Y);
		printf("\t>>total xnx4_c���� time consume %.6f s\n", (float)(clock() - stps_start3) / CLOCKS_PER_SEC);
		clock_t stps_start4;
		stps_start4 = clock();
		x4x4_d = r.i()*q1.t()*(Y - xnxn_K*xnx4_c);
		printf("\t>>x4x4_d���� time consume %.6f ms\n", (float)(clock() - stps_start4) / CLOCKS_PER_SEC * 1000);
		printf("\t>>the total consumption %.6f s\n", (float)(clock() - stps_start) / CLOCKS_PER_SEC);

	}
	else
	{
		//clock_t c;
		//c = clock();
		Matrix X(nCpt, 4), Y(nCpt, 4);
		Matrix Q(nCpt, nCpt); Q = 0.0;
		for (V3DLONG i = 0; i < nCpt; i++)
		{
			Q(i + 1, 1) = X(i + 1, 1) = 1;
			Q(i + 1, 2) = X(i + 1, 2) = cpt_subject_ref[i][0];
			Q(i + 1, 3) = X(i + 1, 3) = cpt_subject_ref[i][1];
			Q(i + 1, 4) = X(i + 1, 4) = cpt_subject_ref[i][2];
			Y(i + 1, 1) = 1;
			Y(i + 1, 2) = cpt_target_ref[i][0];
			Y(i + 1, 3) = cpt_target_ref[i][1];
			Y(i + 1, 4) = cpt_target_ref[i][2];
		}
		UpperTriangularMatrix R;
		QRZ(Q, R);
		clock_t stps_start;
		stps_start = clock();
		extend_orthonormal(Q, 4);//otherwise q2=0

		Matrix q1 = Q.columns(1, 4);
		Matrix q2 = Q.columns(5, nCpt);
		Matrix r = R.submatrix(1, 4, 1, 4);
		//compute non-affine term c which decomposed from TPS
		Matrix A = q2.t()*xnxn_K*q2 + IdentityMatrix(nCpt - 4)*0.2;
		xnx4_c = q2*(A.i()*q2.t()*Y);
		//compute affine term d (normal)
		x4x4_d = r.i()*q1.t()*(Y - xnxn_K*xnx4_c);
		printf("\t>>xnxn_K time consume %.2f s\n", (float)(clock() - stps_start) / CLOCKS_PER_SEC);
	}
	if (cpt_target) { delete cpt_target; cpt_target = 0; }
	/*Matrix wR(nCpt, nCpt);
	double tmp, s;
	V3DLONG i, j, k;
	for (j = 0; j<nCpt; j++)
	{
	for (i = 0; i<nCpt; i++)
	{
	s = 0.0;
	tmp = cpt_target_ref[i][0] - cpt_target_ref[j][0]; s += tmp*tmp;
	tmp = cpt_target_ref[i][1] - cpt_target_ref[j][1]; s += tmp*tmp;
	tmp = cpt_target_ref[i][2] - cpt_target_ref[j][2]; s += tmp*tmp;
	wR(i + 1, j + 1) = 2 * s*log(s + 1e-20);
	}
	}

	Matrix wP(nCpt, 4);
	for (j = 0; j<nCpt; j++)
	{
	wP(j + 1, 1) = 1;
	wP(j + 1, 2) = cpt_target_ref[j][0];
	wP(j + 1, 3) = cpt_target_ref[j][1];
	wP(j + 1, 4) = cpt_target_ref[j][2];
	}

	Matrix wL(nCpt + 4, nCpt + 4);
	wL.submatrix(1, nCpt, 1, nCpt) = wR;
	wL.submatrix(1, nCpt, nCpt + 1, nCpt + 4) = wP;
	wL.submatrix(nCpt + 1, nCpt + 4, 1, nCpt) = wP.t();
	wL.submatrix(nCpt + 1, nCpt + 4, nCpt + 1, nCpt + 4) = 0;

	Matrix wY(nCpt + 4, 3);
	for (j = 0; j<nCpt; j++)
	{
	wY(j + 1, 1) = cpt_subject_ref[j][0];
	wY(j + 1, 2) = cpt_subject_ref[j][1];
	wY(j + 1, 3) = cpt_subject_ref[j][2];
	}
	wY.submatrix(nCpt + 1, nCpt + 4, 1, 3) = 0;

	Matrix wW;

	Try
	{
	wW = wL.i() * wY;
	}
	CatchAll
	{
	fprintf(stderr, "Fail to find the inverse of the wL matrix.\n");

	if (cpt_target) { delete cpt_target; cpt_target = 0; }
	if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
	return 0;
	}*/
	return true;
}

Vol3DSimple<DisplaceFieldF3D> * compute_df_stps_subsampled_volume_4bspline_block(int nCpt, Matrix x4x4_d, Matrix xnx4_c, V3DLONG sz0, V3DLONG sz1, V3DLONG sz2, V3DLONG gfactor_x,
	V3DLONG gfactor_y, V3DLONG gfactor_z, float * H_X, float * H_Y, float * H_Z)
{
	V3DLONG p;

	//	V3DLONG gsz0 = (V3DLONG)(ceil((double(sz0)/gfactor_x)))+1, gsz1 = (V3DLONG)(ceil((double(sz1)/gfactor_y)))+1, gsz2 = (V3DLONG)(ceil((double(sz2)/gfactor_z)))+1;
	V3DLONG gsz0 = (V3DLONG)(ceil((double(sz0) / gfactor_x))) + 1 + 2, gsz1 = (V3DLONG)(ceil((double(sz1) / gfactor_y))) + 1 + 2, gsz2 = (V3DLONG)(ceil((double(sz2) / gfactor_z))) + 1 + 2;//+2 for bspline
	Vol3DSimple<DisplaceFieldF3D> * df_local = new Vol3DSimple<DisplaceFieldF3D>(gsz0, gsz1, gsz2);
	DisplaceFieldF3D *** df_local_3d = df_local->getData3dHandle();

	if (!df_local || !df_local->valid())
	{
		fprintf(stderr, "Fail to allocate memory for the subsampled DF volume memory [%d].\n", __LINE__);

		//if (cpt_target) { delete cpt_target; cpt_target = 0; }
		//if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
		if (df_local) { delete df_local; df_local = 0; }
		return 0;
	}

	/*V3DLONG ndimpt = 3;
	double * dist = new double[nCpt + ndimpt + 1];
	if (!dist)
	{
	fprintf(stderr, "Fail to allocate memory dist for tps warping [%d].\n", __LINE__);

	if (cpt_target) { delete cpt_target; cpt_target = 0; }
	if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
	if (df_local) { delete df_local; df_local = 0; }
	return 0;
	}*/

	printf("-------------------- Now compute the distances of pixels to the mapping points. -------\n\n");

	V3DLONG i, j, k;
	DisplaceFieldF3D * df_local_1d = df_local->getData1dHandle();
	for (k = 0; k<df_local->getTotalElementNumber(); k++)
	{
		df_local_1d[k].sz = df_local_1d[k].sy = df_local_1d[k].sx = 0;
	}
	clock_t stps_computedistance;
	stps_computedistance = clock();
	//gpu_computedistance(nCpt, gsz2, gsz1, gsz0, gfactor_x, gfactor_y, gfactor_z, x4x4_d, xnx4_c, H_X, H_Y, H_Z, df_local_3d);
	printf("\t>>computedistance time consume %.2f s\n", (float)(clock() - stps_computedistance) / CLOCKS_PER_SEC);
	for (k = 0; k<gsz2; k++)
	{
		for (j = 0; j<gsz1; j++)
		{
			for (i = 0; i<gsz0; i++)
			{
				Matrix x_ori(1, 4);
				x_ori(1, 1) = 1.0;
				x_ori(1, 2) = (i - 1)*gfactor_x;
				x_ori(1, 3) = (j - 1)*gfactor_y;
				x_ori(1, 4) = (k - 1)*gfactor_z;
				Matrix x_stps(1, 4);
				Matrix xmxn_K;
				xmxn_K.resize(1, nCpt);
				double d_x, d_y, d_z;
				for (unsigned V3DLONG n = 0; n<nCpt; n++)
				{
					d_x = (i - 1)*gfactor_x - H_X[n];
					d_y = (j - 1)*gfactor_y - H_Y[n];
					d_z = (k - 1)*gfactor_z - H_Z[n];
					xmxn_K(1, n + 1) = -sqrt(d_x*d_x + d_y*d_y + d_z*d_z);
				}
				x_stps = x_ori*x4x4_d + xmxn_K*xnx4_c;
				df_local_3d[k][j][i].sx = x_stps(1, 2) - (i - 1)*gfactor_x;
				df_local_3d[k][j][i].sy = x_stps(1, 3) - (j - 1)*gfactor_y;
				df_local_3d[k][j][i].sz = x_stps(1, 4) - (k - 1)*gfactor_z;


			}//i
		}//j
		printf("z=%ld ", k); fflush(stdout);
	}//k
	printf("\n");

	//if (dist) { delete[]dist; dist = 0; }

	/*ע�⣺�������Ҫ�ڴ�ѭ���������ͷŵ�
	free(H_X);
	free(H_Y);
	free(H_Z);

	if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
	*/
	return df_local;
}




// TPS_linear_blockbyblock image warping
//	i_interp_method_df:  0-trilinear, 1-bspline
//	i_interp_method_img: 0-trilinear, 1-nearest neighbor
//template <class T>
bool imgwarp_smallmemory_CYF(unsigned char *p_img_sub, const V3DLONG *sz_img_sub,
	const QList<ImageMarker> &ql_marker_tar, const QList<ImageMarker> &ql_marker_sub,
	V3DLONG szBlock_x, V3DLONG szBlock_y, V3DLONG szBlock_z, int i_interpmethod_df, int i_interpmethod_img,
	unsigned char *&p_img_warp, const V3DLONG *sz_img_sub_ori)
{
	//check parameters
	if (p_img_sub == 0 || sz_img_sub == 0)
	{
		printf("ERROR: p_img_sub or sz_img_sub is invalid.\n");
		return false;
	}
	if (ql_marker_tar.size() == 0 || ql_marker_sub.size() == 0 || ql_marker_tar.size() != ql_marker_sub.size())
	{
		printf("ERROR: target or subject control points is invalid!\n");
		return false;
	}
	if (szBlock_x <= 0 || szBlock_y <= 0 || szBlock_z <= 0)
	{
		printf("ERROR: block size is invalid!\n");
		return false;
	}
	if (szBlock_x >= sz_img_sub[0] || szBlock_y >= sz_img_sub[1] || szBlock_z >= sz_img_sub[2])
	{
		printf("ERROR: block size should smaller than the image size!\n");
		return false;
	}
	if (i_interpmethod_df != 0 && i_interpmethod_df != 1)
	{
		printf("ERROR: DF_interp_method should be 0(linear) or 1(bspline)!\n");
		return false;
	}
	if (i_interpmethod_img != 0 && i_interpmethod_img != 1)
	{
		printf("ERROR: img_interp_method should be 0(linear) or 1(nn)!\n");
		return false;
	}
	if (i_interpmethod_df == 1 && (szBlock_x != szBlock_y || szBlock_x != szBlock_z))
	{
		printf("ERROR: df_interp_method=bspline need szBlock_x=szBlock_y=szBlock_z!\n");
		return false;
	}
	if (p_img_warp)
	{
		printf("WARNNING: output image pointer is not null, original memeroy it point to will be released!\n");
		if (p_img_warp) 			{ delete[]p_img_warp;		p_img_warp = 0; }
	}

	//------------------------------------------------------------------------------------------------------------------------------------
	printf(">>>>compute the subsampled displace field \n");
	vector<Coord3D_JBA> matchTargetPos, matchSubjectPos;
	for (V3DLONG i = 0; i<ql_marker_tar.size(); i++)
	{
		Coord3D_JBA tmpc;
		tmpc.x = 1 * ql_marker_tar.at(i).x;	tmpc.y = 1 * ql_marker_tar.at(i).y;	tmpc.z = 1 * ql_marker_tar.at(i).z;
		matchTargetPos.push_back(tmpc);
		tmpc.x = 1 * ql_marker_sub.at(i).x;	tmpc.y = 1 * ql_marker_sub.at(i).y;	tmpc.z = 1 * ql_marker_sub.at(i).z;
		matchSubjectPos.push_back(tmpc);
	}
	int nCpt = matchTargetPos.size();
	Image2DSimple<MYFLOAT_JBA> * cpt_subject = 0;
	Matrix xnx4_c(nCpt, 4);
	Matrix x4x4_d(4, 4);
	float *H_X = 0;
	float *H_Y = 0;
	float *H_Z = 0;
	clock_t BSP;
	BSP = clock();
	if (!(compute_df_stps_subsampled_volume_4bspline_per(matchTargetPos, matchSubjectPos, x4x4_d, xnx4_c, H_X, H_Y, H_Z, nCpt, cpt_subject)))
	{
		printf("ERROR:compute_df_stps_subsampled_volume_4bspline_per() return false. \n");
		return false;
	}
	//--------------------------------------------------------------------�ֿ�warp-----------------------------------------------------------

	Vol3DSimple<DisplaceFieldF3D> *pSubDF = 0;
	if (i_interpmethod_df == 0)
		pSubDF = compute_df_tps_subsampled_volume(matchTargetPos, matchSubjectPos, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], szBlock_x, szBlock_y, szBlock_z);
	else
	{
		//pSubDF = compute_df_stps_subsampled_volume_4bspline(matchTargetPos, matchSubjectPos, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], szBlock_x, szBlock_y, szBlock_z);

		pSubDF = compute_df_stps_subsampled_volume_4bspline_block(nCpt, x4x4_d, xnx4_c, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], szBlock_x, szBlock_y, szBlock_z, H_X, H_Y, H_Z);
		free(H_X);
		free(H_Y);
		free(H_Z);

		if (cpt_subject) { delete cpt_subject; cpt_subject = 0; }
	}

	printf("\t>>BSP time consume: %.2f s\n", (float)(clock() - BSP) / CLOCKS_PER_SEC);
	if (!pSubDF)
	{
		printf("Fail to produce the subsampled DF.\n");
		return false;
	}
	DisplaceFieldF3D ***pppSubDF = pSubDF->getData3dHandle();
	printf("subsampled DF size: [%ld,%ld,%ld]\n", pSubDF->sz0(), pSubDF->sz1(), pSubDF->sz2());

	//------------------------------------------------------------------------
	//allocate memory
	printf(">>>>interpolate the subsampled displace field and warp block by block\n");
	p_img_warp = new unsigned char[sz_img_sub[0] * sz_img_sub[1] * sz_img_sub[2] * sz_img_sub[3]]();
	if (!p_img_warp)
	{
		printf("ERROR: Fail to allocate memory for p_img_warp.\n");
		if (pSubDF)				{ delete pSubDF;					pSubDF = 0; }
		return false;
	}
	unsigned char ****p_img_warp_4d = 0, ****p_img_sub_4d = 0;
	if (!new4dpointer(p_img_warp_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3], p_img_warp) ||
		!new4dpointer(p_img_sub_4d, sz_img_sub_ori[0], sz_img_sub_ori[1], sz_img_sub_ori[2], sz_img_sub_ori[3], p_img_sub))
	{
		printf("ERROR: Fail to allocate memory for the 4d pointer of image.\n");
		if (p_img_warp_4d) 		{ delete4dpointer(p_img_warp_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
		if (p_img_sub_4d) 		{ delete4dpointer(p_img_sub_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
		if (p_img_warp) 			{ delete[]p_img_warp;			p_img_warp = 0; }
		if (pSubDF)				{ delete pSubDF;					pSubDF = 0; }
		return false;
	}
	Vol3DSimple<DisplaceFieldF3D> *pDFBlock = new Vol3DSimple<DisplaceFieldF3D>(szBlock_x, szBlock_y, szBlock_z);
	if (!pDFBlock)
	{
		printf("ERROR: Fail to allocate memory for pDFBlock.\n");
		if (p_img_warp_4d) 		{ delete4dpointer(p_img_warp_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
		if (p_img_sub_4d) 		{ delete4dpointer(p_img_sub_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
		if (p_img_warp) 			{ delete[]p_img_warp;			p_img_warp = 0; }
		if (pSubDF)				{ delete pSubDF;					pSubDF = 0; }
		return false;
	}
	DisplaceFieldF3D ***pppDFBlock = pDFBlock->getData3dHandle();

	//------------------------------------------------------------------------
	//interpolate the SubDfBlock to DFBlock and do warp block by block
	if (i_interpmethod_df == 0)		printf("\t>>subsampled displace field interpolate method: trilinear\n");
	else if (i_interpmethod_df == 1)	printf("\t>>subsampled displace field interpolate method: B-spline\n");
	if (i_interpmethod_img == 0)		printf("\t>>image value               interpolate method: trilinear\n");
	else if (i_interpmethod_img == 1)	printf("\t>>image value               interpolate method: nearest neighbor\n");

	if (i_interpmethod_df == 0)	//linear interpolate the SubDfBlock to DFBlock and do warp block by block
	{
		for (V3DLONG substart_z = 0; substart_z<pSubDF->sz2() - 1; substart_z++)
			for (V3DLONG substart_y = 0; substart_y<pSubDF->sz1() - 1; substart_y++)
				for (V3DLONG substart_x = 0; substart_x<pSubDF->sz0() - 1; substart_x++)
				{
			//linear interpolate the SubDfBlock to DFBlock
			q_dfblcokinterp_linear(pppSubDF, szBlock_x, szBlock_y, szBlock_z, substart_x, substart_y, substart_z, pppDFBlock);
			//warp image block using DFBlock
			q_imgblockwarp(p_img_sub_4d, sz_img_sub, pppDFBlock, szBlock_x, szBlock_y, szBlock_z, i_interpmethod_img, substart_x, substart_y, substart_z, p_img_warp_4d);
				}
	}
	else						//bspline interpolate the SubDfBlock to DFBlock and do warp block by block
	{
		//initialize the bspline basis function
		V3DLONG sz_gridwnd = szBlock_x;
		Matrix x_bsplinebasis(pow(double(sz_gridwnd), 3.0), pow(4.0, 3.0));
		if (!q_nonrigid_ini_bsplinebasis_3D(sz_gridwnd, x_bsplinebasis))
		{
			printf("ERROR: q_ini_bsplinebasis_3D() return false!\n");
			if (p_img_warp_4d) 		{ delete4dpointer(p_img_warp_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
			if (p_img_sub_4d) 		{ delete4dpointer(p_img_sub_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
			if (p_img_warp) 			{ delete[]p_img_warp;			p_img_warp = 0; }
			if (pSubDF)				{ delete pSubDF;					pSubDF = 0; }
			return false;
		}
		printf("\t>>x_bsplinebasis:[%d,%d]\n", x_bsplinebasis.nrows(), x_bsplinebasis.ncols());
		int gsz2 = pSubDF->sz2();
		int gsz1 = pSubDF->sz1();
		int gsz0 = pSubDF->sz0();
		clock_t stps_interpolation;
		stps_interpolation = clock();

		gpu_interpolation(gsz2, gsz1, gsz0, pppSubDF, x_bsplinebasis, sz_gridwnd, pppDFBlock, p_img_sub_4d, sz_img_sub, szBlock_x, szBlock_y, szBlock_z, i_interpmethod_img, p_img_warp_4d, sz_img_sub_ori, p_img_sub, p_img_warp);


		printf("\t>>interpolation time consume %.2f s\n", (float)(clock() - stps_interpolation) / CLOCKS_PER_SEC);

		//for(V3DLONG substart_z=0;substart_z<pSubDF->sz2()-1-2;substart_z++)
		//	for(V3DLONG substart_y=0;substart_y<pSubDF->sz1()-1-2;substart_y++)
		//		for(V3DLONG substart_x=0;substart_x<pSubDF->sz0()-1-2;substart_x++)
		//		{
		//			//bspline interpolate the SubDfBlock to DFBlock
		//			q_dfblcokinterp_bspline(pppSubDF,x_bsplinebasis,sz_gridwnd,substart_x,substart_y,substart_z,pppDFBlock);
		//			//warp image block using DFBlock
		//			q_imgblockwarp(p_img_sub_4d,sz_img_sub,pppDFBlock,szBlock_x,szBlock_y,szBlock_z,i_interpmethod_img,substart_x,substart_y,substart_z,p_img_warp_4d);
		//		}
	}

	//free memory
	if (p_img_warp_4d) 		{ delete4dpointer(p_img_warp_4d, sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]); }
	if (p_img_sub_4d) 		{ delete4dpointer(p_img_sub_4d, 547, 442, 682, sz_img_sub[3]); }
	if (pDFBlock)			{ delete pDFBlock;			pDFBlock = 0; }
	if (pSubDF)				{ delete pSubDF;				pSubDF = 0; }

	return true;
}


