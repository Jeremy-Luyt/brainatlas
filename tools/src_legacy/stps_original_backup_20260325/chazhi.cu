#include "ele.cuh"
#include "stackutil.h"
#include "q_imgwarp_tps_quicksmallmemory.h"
#include "cuda_runtime_api.h"
#include <malloc.h>
#include<time.h>
#include"G:\\postgraduate\\3rdparty\\3rdparty\\v3d_main_jba\\newmat11\\newmat.h"
#include <math.h>
__device__ int myceil(double x)//向上取整
{
	if (x<0)

		return (float)((int)x);

	else

	{

		if (x == 0)

			return (float)((int)x) + 1;

		else

			return (float)((int)x) + 1;

	}
}
__device__ int myfloor(double x)//向下取整
{
	if (x<0)

		return (float)((int)x) - 1;

	else

	{

		if (x == 0)

			return (float)((int)x);

		else

			return (float)((int)x);

	}
}
__device__ void MUL(float *A, float *B, float *C)
{
	for (int i = 0; i < 64; i++)
	{

		for (int j = 0; j < 3; j++)
		{
			float sum = 0;
			for (int k = 0; k < 64; k++)
			{
				sum += A[i * 64 + k] * B[k * 3 + j];
			}
			C[i * 3 + j] = sum;
		}
	}
}
__global__ void get_Displacement_brightness(const V3DLONG sz_gridwnd, const int k, const V3DLONG gsz1, const V3DLONG gsz0, float * D_pppSubDF_x, float * D_pppSubDF_y, float * D_pppSubDF_z,
	float *D_x_bsplinebasis, float *D_pppDFBlock_x, float *D_pppDFBlock_y, float *D_pppDFBlock_z, const int szBlock_x, const int szBlock_y, const int szBlock_z, const int D_sz_img_sub0,
	const int D_sz_img_sub1, const int D_sz_img_sub2, const int D_sz_img_sub3, unsigned char *D_p_img_sub_4d, unsigned char *D_p_img_warp_4d, const int i_interpmethod_img, const int D_sz_img_ori_sub0,
	const int D_sz_img_ori_sub1, const int D_sz_img_ori_sub2, const int D_sz_img_ori_sub3)
{
	const int row = blockIdx.y * blockDim.y + threadIdx.y;
	const int col = blockIdx.x * blockDim.x + threadIdx.x;
	//printf("grid[%d %d]\n", row, col);
	if (row >= gsz1 - 1 - 2 || col >= gsz0 - 1 - 2)return;
	//printf("mark221");
	float x1D_gridblock[192];
	int ind = 1;
	for (int a = k; a<k + 4; a++)
		for (int c = col; c<col + 4; c++)
			for (int b = row; b<row + 4; b++)
			{
		x1D_gridblock[(ind - 1) * 3] = D_pppSubDF_x[a*gsz1*gsz0 + b*gsz0 + c];
		x1D_gridblock[(ind - 1) * 3 + 1] = D_pppSubDF_y[a*gsz1*gsz0 + b*gsz0 + c];
		x1D_gridblock[(ind - 1) * 3 + 2] = D_pppSubDF_z[a*gsz1*gsz0 + b*gsz0 + c];
		ind++;
			}
	//	printf("grid[%d %d],x:%f y:%f z:%f\n", row, col,x1D_gridblock[0], x1D_gridblock[1], x1D_gridblock[2]);

	float  x1D_gridblock_int[4 * 4 * 4 * 3];


	MUL(D_x_bsplinebasis, x1D_gridblock, x1D_gridblock_int);
	//printf("grid[%d %d],%f %f %f\n", row, col, x1D_gridblock_int[2], x1D_gridblock_int[1], x1D_gridblock_int[0]);
	//printf("ind:%d\n", ind);
	//printf("grid[%d %d %d],%f %f %f\n", k,row, col, x1D_gridblock_int[2], x1D_gridblock_int[1], x1D_gridblock_int[0]);
	int idx = 1;
	float D_pppDFBlock_x1[4 * 4 * 4]; float D_pppDFBlock_y1[4 * 4 * 4]; float D_pppDFBlock_z1[4 * 4 * 4];
	//printf("mark22");
	for (long zz = 0; zz<sz_gridwnd; zz++)
		for (long xx = 0; xx<sz_gridwnd; xx++)
			for (long yy = 0; yy<sz_gridwnd; yy++)
			{
		D_pppDFBlock_x1[zz * 16 + yy * 4 + xx] = x1D_gridblock_int[(idx - 1) * 3];
		D_pppDFBlock_y1[zz * 16 + yy * 4 + xx] = x1D_gridblock_int[(idx - 1) * 3 + 1];
		D_pppDFBlock_z1[zz * 16 + yy * 4 + xx] = x1D_gridblock_int[(idx - 1) * 3 + 2];
		idx++;
			}
	//printf("grid[%d %d %d],%f %f %f\n", k, row, col, D_pppDFBlock_x1[0], D_pppDFBlock_y1[0], D_pppDFBlock_z1[0]);
	//printf("mar222");
	int start_x, start_y, start_z;
	start_x = col*szBlock_x;
	start_y = row*szBlock_y;
	start_z = k*szBlock_z;
	//printf("mar333");
	for (int z = 0; z < szBlock_z; z++)
		for (int y = 0; y < szBlock_y; y++)
			for (int x = 0; x < szBlock_x; x++)
			{
		//printf("mar222");
		int pos_warp[3];
		pos_warp[0] = start_x + x;
		pos_warp[1] = start_y + y;
		pos_warp[2] = start_z + z;
		//printf("x:%d  y:%d  z:%d idx:%d  grid[%d %d %d],%d %d %d\n",x,y,z,x+y*4+z*16, k, row, col, pos_warp[0], pos_warp[1], pos_warp[2]);


		if (pos_warp[0] >= D_sz_img_sub0 || pos_warp[1] >= D_sz_img_sub1 || pos_warp[2] >= D_sz_img_sub2)
			continue;

		double pos_sub[3];
		pos_sub[0] = pos_warp[0] + D_pppDFBlock_x1[z * 16 + y * 4 + x];
		pos_sub[1] = pos_warp[1] + D_pppDFBlock_y1[z * 16 + y * 4 + x];
		pos_sub[2] = pos_warp[2] + D_pppDFBlock_z1[z * 16 + y * 4 + x];
		//printf("x:%d  y:%d  z:%d idx:%d  grid[%d %d %d],%f %f %f\n", x, y, z, x + y * 4 + z * 16, k, row, col, pos_sub[0], pos_sub[1], pos_sub[2]);

		//if (pos_sub[0]<0 || pos_sub[0]>D_sz_img_sub0 - 1 || pos_sub[1]<0 || pos_sub[1]>D_sz_img_sub1 - 1 || pos_sub[2]<0 || pos_sub[2]>D_sz_img_sub2 - 1)
		if (pos_sub[0]<0 || pos_sub[0]>D_sz_img_ori_sub0 - 1 || pos_sub[1]<0 || pos_sub[1]>D_sz_img_ori_sub1 - 1 || pos_sub[2]<0 || pos_sub[2]>D_sz_img_ori_sub2 - 1)
		{
			for (V3DLONG c = 0; c < D_sz_img_sub3; c++)
				D_p_img_warp_4d[pos_warp[2] * D_sz_img_sub1 * D_sz_img_sub0 + pos_warp[1] * D_sz_img_sub0 + pos_warp[0]] = 0;
			continue;
		}


		//find 8 neighor pixels boundary

		int x_s, x_b, y_s, y_b, z_s, z_b;
		x_s = myfloor(pos_sub[0]);            x_b = myceil(pos_sub[0]);
		y_s = myfloor(pos_sub[1]);            y_b = myceil(pos_sub[1]);
		z_s = myfloor(pos_sub[2]);            z_b = myceil(pos_sub[2]);
		//printf("x:%d y:%d z:%d idx:%d grid[%d %d %d],%f %f %f,down:%d %d %d up:%d %d %d\n", x, y, z, x + y * 4 + z * 16, k, row, col, pos_sub[0], pos_sub[1], pos_sub[2], x_s, y_s, z_s, x_b, y_b, z_b);

		//compute weight for left and right, top and  bottom -- 4 neighbor pixel's weight in a slice
		double l_w, r_w, t_w, b_w;
		l_w = 1.0 - (pos_sub[0] - x_s);  r_w = 1.0 - l_w;
		t_w = 1.0 - (pos_sub[1] - y_s);  b_w = 1.0 - t_w;
		double u_w, d_w;
		u_w = 1.0 - (pos_sub[2] - z_s);  d_w = 1.0 - u_w;
		//printf("x:%d y:%d z:%d idx:%d grid[%d %d %d],%f %f %f,l_w:%f r_w:%f t_w:%f b_w:%f u_w:%f d_w:%f\n", x, y, z, x + y * 4 + z * 16, k, row, col, pos_sub[0], pos_sub[1], pos_sub[2], l_w, r_w, t_w, b_w, u_w, d_w);
		//printf("x:%d y:%d z:%d idx:%d grid[%d %d %d],%f %f %f,down:%d %d %d up:%d %d %d\n", x, y, z, x + y * 4 + z * 16, k, row, col, pos_sub[0], pos_sub[1], pos_sub[2], x_s, y_s, z_s, x_b, y_b, z_b);
		//printf("l_w:%f r_w:%f t_w:%f b_w:%f u_w:%f d_w:%f %f %f %f\n", l_w, r_w, t_w, b_w, u_w, d_w, pos_sub[0], pos_sub[1], pos_sub[2]);

		double higher_slice;
		//higher_slice = t_w*(l_w*D_p_img_sub_4d[z_s*D_sz_img_sub1 * D_sz_img_sub0 + y_s*D_sz_img_sub0 + x_s] + r_w*D_p_img_sub_4d[z_s*D_sz_img_sub1 * D_sz_img_sub0 + y_s*D_sz_img_sub0 + x_b]) + b_w*(l_w*D_p_img_sub_4d[z_s*D_sz_img_sub1 * D_sz_img_sub0 + y_b*D_sz_img_sub0 + x_s] + r_w*D_p_img_sub_4d[z_s*D_sz_img_sub1 * D_sz_img_sub0 + y_b*D_sz_img_sub0 + x_b]);
		higher_slice = t_w*(l_w*D_p_img_sub_4d[z_s * D_sz_img_ori_sub1 * D_sz_img_ori_sub0 + y_s * D_sz_img_ori_sub0 + x_s] + r_w*D_p_img_sub_4d[z_s * D_sz_img_ori_sub1 * D_sz_img_ori_sub0 + y_s * D_sz_img_ori_sub0 + x_b]) + b_w*(l_w*D_p_img_sub_4d[z_s * D_sz_img_ori_sub1 * D_sz_img_ori_sub0 + y_b * D_sz_img_ori_sub0 + x_s] + r_w*D_p_img_sub_4d[z_s * D_sz_img_ori_sub1 * D_sz_img_ori_sub0 + y_b*D_sz_img_ori_sub0 + x_b]);
		double lower_slice;
		//lower_slice = t_w*(l_w*D_p_img_sub_4d[z_b*D_sz_img_sub1 * D_sz_img_sub0 + y_s*D_sz_img_sub0 + x_s] + r_w*D_p_img_sub_4d[z_b*D_sz_img_sub1 * D_sz_img_sub0 + y_s*D_sz_img_sub0 + x_b]) + b_w*(l_w*D_p_img_sub_4d[z_b*D_sz_img_sub1 * D_sz_img_sub0 + y_b*D_sz_img_sub0 + x_s] + r_w*D_p_img_sub_4d[z_b*D_sz_img_sub1 * D_sz_img_sub0 + y_b*D_sz_img_sub0 + x_b]);
		lower_slice = t_w*(l_w*D_p_img_sub_4d[z_b * D_sz_img_ori_sub1 * D_sz_img_ori_sub0 + y_s * D_sz_img_ori_sub0 + x_s] + r_w*D_p_img_sub_4d[z_b * D_sz_img_ori_sub1 * D_sz_img_ori_sub0 + y_s * D_sz_img_ori_sub0 + x_b]) + b_w*(l_w*D_p_img_sub_4d[z_b * D_sz_img_ori_sub1 * D_sz_img_ori_sub0 + y_b * D_sz_img_ori_sub0 + x_s] + r_w*D_p_img_sub_4d[z_b * D_sz_img_ori_sub1 * D_sz_img_ori_sub0 + y_b*D_sz_img_ori_sub0 + x_b]);
		double intval = (u_w*higher_slice + d_w*lower_slice + 0.5);

		D_p_img_warp_4d[pos_warp[2] * D_sz_img_sub1 * D_sz_img_sub0 + pos_warp[1] * D_sz_img_sub0 + pos_warp[0]] = intval;





			}
}

__global__ void get_Displacement_brightness_nn(const V3DLONG sz_gridwnd, const int k, const V3DLONG gsz1, const V3DLONG gsz0, float * D_pppSubDF_x, float * D_pppSubDF_y, float * D_pppSubDF_z,
	float *D_x_bsplinebasis, float *D_pppDFBlock_x, float *D_pppDFBlock_y, float *D_pppDFBlock_z, const int szBlock_x, const int szBlock_y, const int szBlock_z, const int D_sz_img_sub0,
	const int D_sz_img_sub1, const int D_sz_img_sub2, const int D_sz_img_sub3, unsigned char *D_p_img_sub_4d, unsigned char *D_p_img_warp_4d, const int i_interpmethod_img, const int D_sz_img_ori_sub0,
	const int D_sz_img_ori_sub1, const int D_sz_img_ori_sub2, const int D_sz_img_ori_sub3)
{
	const int row = blockIdx.y * blockDim.y + threadIdx.y;
	const int col = blockIdx.x * blockDim.x + threadIdx.x;
	//printf("grid[%d %d]\n", row, col);
	if (row >= gsz1 - 1 - 2 || col >= gsz0 - 1 - 2)return;
	//printf("mark221");
	float x1D_gridblock[192];
	int ind = 1;
	for (int a = k; a<k + 4; a++)
		for (int c = col; c<col + 4; c++)
			for (int b = row; b<row + 4; b++)
			{
		x1D_gridblock[(ind - 1) * 3] = D_pppSubDF_x[a*gsz1*gsz0 + b*gsz0 + c];
		x1D_gridblock[(ind - 1) * 3 + 1] = D_pppSubDF_y[a*gsz1*gsz0 + b*gsz0 + c];
		x1D_gridblock[(ind - 1) * 3 + 2] = D_pppSubDF_z[a*gsz1*gsz0 + b*gsz0 + c];
		ind++;
			}
	//	printf("grid[%d %d],x:%f y:%f z:%f\n", row, col,x1D_gridblock[0], x1D_gridblock[1], x1D_gridblock[2]);

	float  x1D_gridblock_int[4 * 4 * 4 * 3];


	MUL(D_x_bsplinebasis, x1D_gridblock, x1D_gridblock_int);
	//printf("grid[%d %d],%f %f %f\n", row, col, x1D_gridblock_int[2], x1D_gridblock_int[1], x1D_gridblock_int[0]);
	//printf("ind:%d\n", ind);
	//printf("grid[%d %d %d],%f %f %f\n", k,row, col, x1D_gridblock_int[2], x1D_gridblock_int[1], x1D_gridblock_int[0]);
	int idx = 1;
	float D_pppDFBlock_x1[4 * 4 * 4]; float D_pppDFBlock_y1[4 * 4 * 4]; float D_pppDFBlock_z1[4 * 4 * 4];
	//printf("mark22");
	for (long zz = 0; zz<sz_gridwnd; zz++)
		for (long xx = 0; xx<sz_gridwnd; xx++)
			for (long yy = 0; yy<sz_gridwnd; yy++)
			{
		D_pppDFBlock_x1[zz * 16 + yy * 4 + xx] = x1D_gridblock_int[(idx - 1) * 3];
		D_pppDFBlock_y1[zz * 16 + yy * 4 + xx] = x1D_gridblock_int[(idx - 1) * 3 + 1];
		D_pppDFBlock_z1[zz * 16 + yy * 4 + xx] = x1D_gridblock_int[(idx - 1) * 3 + 2];
		idx++;
			}
	//printf("grid[%d %d %d],%f %f %f\n", k, row, col, D_pppDFBlock_x1[0], D_pppDFBlock_y1[0], D_pppDFBlock_z1[0]);
	//printf("mar222");
	int start_x, start_y, start_z;
	start_x = col*szBlock_x;
	start_y = row*szBlock_y;
	start_z = k*szBlock_z;
	//printf("mar333");
	for (int z = 0; z < szBlock_z; z++)
		for (int y = 0; y < szBlock_y; y++)
			for (int x = 0; x < szBlock_x; x++)
			{
		//printf("mar222");
		int pos_warp[3];
		pos_warp[0] = start_x + x;
		pos_warp[1] = start_y + y;
		pos_warp[2] = start_z + z;
		//printf("x:%d  y:%d  z:%d idx:%d  grid[%d %d %d],%d %d %d\n",x,y,z,x+y*4+z*16, k, row, col, pos_warp[0], pos_warp[1], pos_warp[2]);


		if (pos_warp[0] >= D_sz_img_sub0 || pos_warp[1] >= D_sz_img_sub1 || pos_warp[2] >= D_sz_img_sub2)
			continue;

		double pos_sub[3];
		pos_sub[0] = pos_warp[0] + D_pppDFBlock_x1[z * 16 + y * 4 + x];
		pos_sub[1] = pos_warp[1] + D_pppDFBlock_y1[z * 16 + y * 4 + x];
		pos_sub[2] = pos_warp[2] + D_pppDFBlock_z1[z * 16 + y * 4 + x];
		//printf("x:%d  y:%d  z:%d idx:%d  grid[%d %d %d],%f %f %f\n", x, y, z, x + y * 4 + z * 16, k, row, col, pos_sub[0], pos_sub[1], pos_sub[2]);

		//if (pos_sub[0]<0 || pos_sub[0]>D_sz_img_sub0 - 1 || pos_sub[1]<0 || pos_sub[1]>D_sz_img_sub1 - 1 || pos_sub[2]<0 || pos_sub[2]>D_sz_img_sub2 - 1)
		if (pos_sub[0]<0 || pos_sub[0]>D_sz_img_ori_sub0 - 1 || pos_sub[1]<0 || pos_sub[1]>D_sz_img_ori_sub1 - 1 || pos_sub[2]<0 || pos_sub[2]>D_sz_img_ori_sub2 - 1)
		{
			for (V3DLONG c = 0; c < D_sz_img_sub3; c++)
				D_p_img_warp_4d[pos_warp[2] * D_sz_img_sub1 * D_sz_img_sub0 + pos_warp[1] * D_sz_img_sub0 + pos_warp[0]] = 0;
			continue;
		}

		///nearest neighbor interpolate

		long long pos_sub_nn[3];

		pos_sub_nn[0] = pos_sub[0] + 0.5;
		pos_sub_nn[0] = pos_sub_nn[0]<D_sz_img_ori_sub0 ? pos_sub_nn[0] : D_sz_img_ori_sub0 - 1;

		pos_sub_nn[1] = pos_sub[1] + 0.5;
		pos_sub_nn[1] = pos_sub_nn[1]<D_sz_img_ori_sub1 ? pos_sub_nn[1] : D_sz_img_ori_sub1 - 1;

		pos_sub_nn[2] = pos_sub[2] + 0.5;
		pos_sub_nn[2] = pos_sub_nn[2]<D_sz_img_ori_sub2 ? pos_sub_nn[2] : D_sz_img_ori_sub2 - 1;

		D_p_img_warp_4d[pos_warp[2] * D_sz_img_sub1 * D_sz_img_sub0 + pos_warp[1] * D_sz_img_sub0 + pos_warp[0]] = D_p_img_sub_4d[pos_sub_nn[2] * D_sz_img_ori_sub1 * D_sz_img_ori_sub0 + pos_sub_nn[1] * D_sz_img_ori_sub0 + pos_sub_nn[0]];




			}
}



extern "C" bool gpu_interpolation(const int gsz2, const int gsz1, const int gsz0, DisplaceFieldF3D ***&pppSubDF, const Matrix &x_bsplinebasis, const V3DLONG sz_gridwnd, DisplaceFieldF3D ***&pppDFBlock,
	unsigned char ****&p_img_sub_4d, const V3DLONG *sz_img_sub, const V3DLONG szBlock_x, const V3DLONG szBlock_y, const V3DLONG szBlock_z, const int i_interpmethod_img, unsigned char ****&p_img_warp_4d,
	const V3DLONG *sz_img_sub_ori, const unsigned char *p_img_sub, unsigned char *p_img_warp)
{
	//cudaEvent_t   start, stop;
	//HANDLE_ERROR(cudaEventCreate(&start));
	//HANDLE_ERROR(cudaEventCreate(&stop));
	float *H_pppSubDF_x, *H_pppSubDF_y, *H_pppSubDF_z, *H_pppDFBlock_x, *H_pppDFBlock_y, *H_pppDFBlock_z;
	float *H_x_bsplinebasis, *D_x_bsplinebasis;
	float *D_pppSubDF_x, *D_pppSubDF_y, *D_pppSubDF_z, *D_pppDFBlock_x, *D_pppDFBlock_y, *D_pppDFBlock_z;
	H_pppSubDF_x = (float*)malloc(gsz2 * gsz1 *gsz0 * sizeof(float));
	H_pppSubDF_y = (float*)malloc(gsz2 * gsz1 *gsz0 * sizeof(float));
	H_pppSubDF_z = (float*)malloc(gsz2 * gsz1 *gsz0 * sizeof(float));

	H_x_bsplinebasis = (float*)malloc(x_bsplinebasis.nrows() * x_bsplinebasis.ncols() * sizeof(float));
	H_pppDFBlock_x = (float*)malloc(sz_gridwnd * sz_gridwnd *sz_gridwnd * sizeof(float));
	H_pppDFBlock_y = (float*)malloc(sz_gridwnd * sz_gridwnd *sz_gridwnd * sizeof(float));
	H_pppDFBlock_z = (float*)malloc(sz_gridwnd * sz_gridwnd *sz_gridwnd * sizeof(float));
	printf("mark2\n");
	cudaMalloc((void**)&D_pppSubDF_x, gsz2 * gsz1 *gsz0 * sizeof(float));
	cudaMalloc((void**)&D_pppSubDF_y, gsz2 * gsz1 *gsz0 * sizeof(float));
	cudaMalloc((void**)&D_pppSubDF_z, gsz2 * gsz1 *gsz0 * sizeof(float));
	cudaMalloc((void**)&D_x_bsplinebasis, x_bsplinebasis.nrows() * x_bsplinebasis.ncols() * sizeof(float));
	cudaMalloc((void**)&D_pppDFBlock_x, sz_gridwnd * sz_gridwnd *sz_gridwnd* sizeof(float));
	cudaMalloc((void**)&D_pppDFBlock_y, sz_gridwnd * sz_gridwnd *sz_gridwnd * sizeof(float));
	cudaMalloc((void**)&D_pppDFBlock_z, sz_gridwnd * sz_gridwnd *sz_gridwnd * sizeof(float));


	unsigned char *D_p_img_sub_4d, *D_p_img_warp_4d;
	//H_p_img_sub_4d = (float*)malloc(2 * sz_img_sub[0] * sz_img_sub[1] * sz_img_sub[2] * sz_img_sub[3] * sizeof(float));
	//H_p_img_sub_4d = (float*)malloc(sz_img_sub_ori[0] * sz_img_sub_ori[1] * sz_img_sub_ori[2] * sz_img_sub[3] * sizeof(float));
	//H_p_img_warp_4d = (float*)malloc(sz_img_sub[0] * sz_img_sub[1] * sz_img_sub[2] * sz_img_sub[3] * sizeof(float));
	//H_sz_img_sub = (float*)malloc(4 * sizeof(float));
	//cudaMalloc((void**)&D_p_img_sub_4d, 2 * sz_img_sub[0] * sz_img_sub[1] * sz_img_sub[2] * sz_img_sub[3] * sizeof(float));
	cudaMalloc((void**)&D_p_img_sub_4d, sz_img_sub_ori[0] * sz_img_sub_ori[1] * sz_img_sub_ori[2] * sz_img_sub[3] * sizeof(unsigned char));
	cudaMalloc((void**)&D_p_img_warp_4d, sz_img_sub[0] * sz_img_sub[1] * sz_img_sub[2] * sz_img_sub[3] * sizeof(unsigned char));
	//cudaMalloc((void**)&D_sz_img_sub, 4 * sizeof(float));

	//H_sz_img_sub[0] = sz_img_sub[0]; H_sz_img_sub[1] = sz_img_sub[1]; H_sz_img_sub[2] = sz_img_sub[2]; H_sz_img_sub[3] = sz_img_sub[3];

	//for (V3DLONG a = 0; a < sz_img_sub[2]; a++)
	//{
	//	for (V3DLONG b = 0; b < sz_img_sub[1]; b++)
	//	{
	//		for (V3DLONG c = 0; c < sz_img_sub[0]; c++)
	//		{
	//			printf("\tTime to generate: %3.1f \n", p_img_sub_4d[0][a][b][c]);
	//		}
	//	}
	//}
	//for (V3DLONG a = 0; a < sz_img_sub[2]; a++)
	//{
	//	for (V3DLONG b = 0; b < sz_img_sub[1]; b++)
	//	{
	//		for (V3DLONG c = 0; c < sz_img_sub[0]; c++)
	//		{
	//			H_p_img_sub_4d[a*sz_img_sub[1] * sz_img_sub[0] + b*sz_img_sub[0]+c] = p_img_sub_4d[0][a][b][c];
	//		}
	//	}
	//}
	int aa = sz_img_sub[0]; int bb = sz_img_sub[1]; int cc = sz_img_sub[2]; int dd = sz_img_sub[3];
	int aa_ori = sz_img_sub_ori[0]; int bb_ori = sz_img_sub_ori[1]; int cc_ori = sz_img_sub_ori[2]; int dd_ori = sz_img_sub_ori[3];
	for (V3DLONG a = 0; a < gsz2; a++)
	{
		for (V3DLONG b = 0; b < gsz1; b++)
		{
			for (V3DLONG c = 0; c < gsz0; c++)
			{

				H_pppSubDF_x[a*gsz1*gsz0 + b*gsz0 + c] = pppSubDF[a][b][c].sx;
				H_pppSubDF_y[a*gsz1*gsz0 + b*gsz0 + c] = pppSubDF[a][b][c].sy;
				H_pppSubDF_z[a*gsz1*gsz0 + b*gsz0 + c] = pppSubDF[a][b][c].sz;

			}
		}
	}

	for (int i = 0; i < x_bsplinebasis.nrows(); i++)
	{
		for (int j = 0; j < x_bsplinebasis.ncols(); j++)
		{

			H_x_bsplinebasis[i * x_bsplinebasis.ncols() + j] = x_bsplinebasis(i + 1, j + 1);

		}
	}

	/*for (V3DLONG a = 0; a < sz_img_sub_ori[2]; a++)
	{
	for (V3DLONG b = 0; b < sz_img_sub_ori[1]; b++)
	{
	for (V3DLONG c = 0; c < sz_img_sub_ori[0]; c++)
	{
	H_p_img_sub_4d[a * sz_img_sub_ori[1] * sz_img_sub_ori[0] + b * sz_img_sub_ori[0] + c] = p_img_sub_4d[0][a][b][c];
	}
	}
	}*/
	//for (int i = 0; i < x_bsplinebasis.nrows(); i++)
	//{
	//	printf("\n第%d行", i);
	//	for (int j = 0; j < x_bsplinebasis.ncols(); j++)
	//	{
	//		printf("%.3f\t",H_x_bsplinebasis[i * x_bsplinebasis.ncols() + j]);
	//	}
	//	printf("\n");
	//}
	printf("mark2\n");
	HANDLE_ERROR(cudaMemcpy(D_pppSubDF_x, H_pppSubDF_x, gsz2 * gsz1 *gsz0 * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_pppSubDF_y, H_pppSubDF_y, gsz2 * gsz1 *gsz0 * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_pppSubDF_z, H_pppSubDF_z, gsz2 * gsz1 *gsz0 * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_x_bsplinebasis, H_x_bsplinebasis, x_bsplinebasis.nrows() * x_bsplinebasis.ncols() * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_pppDFBlock_x, H_pppDFBlock_x, sz_gridwnd * sz_gridwnd *sz_gridwnd * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_pppDFBlock_y, H_pppDFBlock_y, sz_gridwnd * sz_gridwnd *sz_gridwnd * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_pppDFBlock_z, H_pppDFBlock_z, sz_gridwnd * sz_gridwnd *sz_gridwnd * sizeof(float), cudaMemcpyHostToDevice));

	//HANDLE_ERROR(cudaMemcpy(D_sz_img_sub, H_sz_img_sub, 4 * sizeof(float), cudaMemcpyHostToDevice)); printf("mark8");
	//HANDLE_ERROR(cudaMemcpy(D_p_img_sub_4d, H_p_img_sub_4d, 2 * sz_img_sub[0] * sz_img_sub[1] * sz_img_sub[2] * sz_img_sub[3] * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_p_img_sub_4d, p_img_sub, sz_img_sub_ori[0] * sz_img_sub_ori[1] * sz_img_sub_ori[2] * sz_img_sub[3] * sizeof(unsigned char), cudaMemcpyHostToDevice));
	//HANDLE_ERROR(cudaMemcpy(D_p_img_warp_4d, H_p_img_warp_4d, sz_img_sub[0] * sz_img_sub[1] * sz_img_sub[2] * sz_img_sub[3] * sizeof(float), cudaMemcpyHostToDevice));
	//	printf("\tsz_img_sub[0]:%d sz_img_sub[1]:%d sz_img_sub[2]:%d sz_img_sub[3]:%d\n", sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3]);


	if (i_interpmethod_img)//nearest neighbor interpolate
	{
		for (int k = 0; k < gsz2 - 1 - 2; k++)
		{
			dim3 grid((gsz0 - 1 - 2 + threads_num - 1) / threads_num, (gsz1 - 1 - 2 + threads_num - 1) / threads_num);
			dim3 block(threads_num, threads_num);
			get_Displacement_brightness_nn << <grid, block >> >(sz_gridwnd, k, gsz1, gsz0, D_pppSubDF_x, D_pppSubDF_y, D_pppSubDF_z, D_x_bsplinebasis, D_pppDFBlock_x, D_pppDFBlock_y, D_pppDFBlock_z, szBlock_x, szBlock_y, szBlock_z, aa, bb, cc, dd, D_p_img_sub_4d, D_p_img_warp_4d, i_interpmethod_img, aa_ori, bb_ori, cc_ori, dd_ori);
			//get_Displacement << <grid, block >> >(sz_gridwnd, k, gsz1, gsz0, D_pppSubDF_x, D_pppSubDF_y, D_pppSubDF_z, D_x_bsplinebasis, D_pppDFBlock_x, D_pppDFBlock_y, D_pppDFBlock_z);
			//get_brightness << <grid, block >> >(gsz1, gsz0, D_p_img_sub_4d, D_sz_img_sub, D_pppDFBlock_x, D_pppDFBlock_y, D_pppDFBlock_z, szBlock_x, szBlock_y, szBlock_z, i_interpmethod_img, k, D_p_img_warp_4d);
			cudaDeviceSynchronize();
		}
	}
	else//linear interpolate
	{
		for (int k = 0; k < gsz2 - 1 - 2; k++)
		{
			dim3 grid((gsz0 - 1 - 2 + threads_num - 1) / threads_num, (gsz1 - 1 - 2 + threads_num - 1) / threads_num);
			dim3 block(threads_num, threads_num);
			get_Displacement_brightness << <grid, block >> >(sz_gridwnd, k, gsz1, gsz0, D_pppSubDF_x, D_pppSubDF_y, D_pppSubDF_z, D_x_bsplinebasis, D_pppDFBlock_x, D_pppDFBlock_y, D_pppDFBlock_z, szBlock_x, szBlock_y, szBlock_z, aa, bb, cc, dd, D_p_img_sub_4d, D_p_img_warp_4d, i_interpmethod_img, aa_ori, bb_ori, cc_ori, dd_ori);
			//get_Displacement << <grid, block >> >(sz_gridwnd, k, gsz1, gsz0, D_pppSubDF_x, D_pppSubDF_y, D_pppSubDF_z, D_x_bsplinebasis, D_pppDFBlock_x, D_pppDFBlock_y, D_pppDFBlock_z);
			//get_brightness << <grid, block >> >(gsz1, gsz0, D_p_img_sub_4d, D_sz_img_sub, D_pppDFBlock_x, D_pppDFBlock_y, D_pppDFBlock_z, szBlock_x, szBlock_y, szBlock_z, i_interpmethod_img, k, D_p_img_warp_4d);
			cudaDeviceSynchronize();
		}
	}




	printf("mark3\n");
	//printf("mark1\n");
	HANDLE_ERROR(cudaMemcpy(p_img_warp, D_p_img_warp_4d, sz_img_sub[0] * sz_img_sub[1] * sz_img_sub[2] * sz_img_sub[3] * sizeof(unsigned char), cudaMemcpyDeviceToHost));
	//printf("mark2\n");






	//for (V3DLONG a = 0; a < sz_img_sub[2]; a++)
	//{
	//	for (V3DLONG b = 0; b < sz_img_sub[1]; b++)
	//	{
	//		for (V3DLONG c = 0; c < sz_img_sub[0]; c++)
	//		{
	//			p_img_warp_4d[0][a][b][c] = H_p_img_warp_4d[a*sz_img_sub[1] * sz_img_sub[0] + b*sz_img_sub[0] + c];
	//			//if (H_p_img_warp_4d[a*sz_img_sub[1] * sz_img_sub[0] + b*sz_img_sub[0] + c]!=0)printf("p_img_warp:%f", H_p_img_warp_4d[a*sz_img_sub[1] * sz_img_sub[0] + b*sz_img_sub[0] + c]);
	//		}
	//	}
	//}





	//HANDLE_ERROR(cudaEventRecord(stop, 0));
	//HANDLE_ERROR(cudaEventSynchronize(stop));
	//float elapsedTime;
	//HANDLE_ERROR(cudaEventElapsedTime(&elapsedTime, start, stop));
	//printf("\tTime to generate: %3.1f ms\n", elapsedTime);
	//HANDLE_ERROR(cudaEventDestroy(start));
	//HANDLE_ERROR(cudaEventDestroy(stop));
	free(H_pppSubDF_x);
	free(H_pppSubDF_y);
	free(H_pppSubDF_z);

	free(H_x_bsplinebasis);

	free(H_pppDFBlock_x);
	free(H_pppDFBlock_y);
	free(H_pppDFBlock_z);

	cudaFree(D_pppSubDF_x); cudaFree(D_pppSubDF_y); cudaFree(D_pppSubDF_z);
	cudaFree(D_pppDFBlock_x); cudaFree(D_pppDFBlock_y); cudaFree(D_pppDFBlock_z);
	cudaFree(D_x_bsplinebasis); cudaFree(D_p_img_sub_4d); cudaFree(D_p_img_warp_4d);
	return true;
}