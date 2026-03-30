#include "cuda_runtime.h"
#include "device_launch_parameters.h"
#include <iostream>
#include <malloc.h>
#include<time.h>
#include"G:\\postgraduate\\3rdparty\\3rdparty\\v3d_main_jba\\newmat11\\newmat.h"
#include "ele.cuh"
#include "stackutil.h"
#include "q_imgwarp_tps_quicksmallmemory.h"
#include "cuda_runtime_api.h"
//__device__ void MUL(float *A, float *B, float *C, float *D, float *E, int nCpt)
//{
//	int k, a; int p1 = 0; int p2 = 0;
//
//		for (int i = 0; i < 4; i++)
//		{
//			float sum1 = 0; float sum2 = 0;
//			for (k = 0; k < 4; k++)
//			{
//				sum1 += A[k] * B[k+p1];
//			}
//			for (a = 0; a < nCpt; a++)
//			{
//				sum2 += C[a] * D[a+p2];
//			}
//			E[i] = sum1 + sum2;
//			p1 = p1 + 4;
//			p2 = p2 + nCpt;
//		}
//
//	
//}
//__global__ void get_cd(V3DLONG k, const V3DLONG gsz1, const V3DLONG gsz0, int nCpt, V3DLONG gfactor_x, V3DLONG gfactor_y, V3DLONG gfactor_z, float * x_ori, float * x_stps, float * D_X, float * D_Y, float * D_Z, float *D_xmxn_K, float *D_x4x4_d, float *D_xnx4_c, float *D_RESULT_X, float *D_RESULT_Y, float *D_RESULT_Z)
//{
//	int row = blockIdx.y * blockDim.y + threadIdx.y;
//	int col = blockIdx.x * blockDim.x + threadIdx.x;
//	if (row >= gsz1 || col >= gsz0)return;
//	x_ori[0] = 1.0; x_ori[1] = (col - 1)*gfactor_x; x_ori[2] = (row - 1)*gfactor_y; x_ori[3] = (k - 1)*gfactor_z;
//	__syncthreads();
//	float d_x, d_y, d_z;
//	for (int n = 0; n<nCpt; n++)
//		{
//			d_x = (col - 1)*gfactor_x - D_X[n];
//			d_y = (row - 1)*gfactor_y - D_Y[n];
//			d_z = (k - 1)*gfactor_z - D_Z[n];
//			D_xmxn_K[n] = -sqrt(d_x*d_x + d_y*d_y + d_z*d_z);
//		}
//	__syncthreads();
//	//printf("---------markinner-------\n\n");
//	MUL(x_ori, D_x4x4_d, D_xmxn_K, D_xnx4_c, x_stps, nCpt);
//	//printf("---------markMUL-------\n\n");
//	__syncthreads();
//	D_RESULT_X[k*gsz1 + row*gsz0 + col] = x_stps[1] - x_ori[1]; __syncthreads();
//	D_RESULT_Y[k*gsz1 + row*gsz0 + col] = x_stps[2] - x_ori[2]; __syncthreads();
//	D_RESULT_Z[k*gsz1 + row*gsz0 + col] = x_stps[3] - x_ori[3];
//}
//extern "C" bool gpu_computedistance(int nCpt, const V3DLONG gsz2, const V3DLONG gsz1, const V3DLONG gsz0, V3DLONG gfactor_x, V3DLONG gfactor_y, V3DLONG gfactor_z, Matrix &x4x4_d, Matrix &xnx4_c, float * H_X, float * H_Y, float * H_Z, DisplaceFieldF3D *** df_local_3d)
//{
//	float *D_X, *D_Y, *D_Z, *H_xmxn_K, *D_xmxn_K, *H_ori, *D_ori, *H_stps, *D_stps, *H_x4x4_d, *D_x4x4_d, *H_xnx4_c, *D_xnx4_c, *H_RESULT_X, *H_RESULT_Y, *H_RESULT_Z, *D_RESULT_X, *D_RESULT_Y, *D_RESULT_Z;
//	H_xmxn_K = (float*)malloc(nCpt * sizeof(float)), H_ori = (float*)malloc(4 * sizeof(float)), H_stps = (float*)malloc(4 * sizeof(float)); H_x4x4_d = (float*)malloc(4 * 4 * sizeof(float)); H_xnx4_c = (float*)malloc(nCpt * 4 * sizeof(float));
//	H_RESULT_X = (float*)malloc(gsz2 * gsz1 *gsz0* sizeof(float)); H_RESULT_Y = (float*)malloc(gsz2 * gsz1 *gsz0* sizeof(float)); H_RESULT_Z = (float*)malloc(gsz2 * gsz1 *gsz0* sizeof(float));
//	cudaMalloc((void**)&D_X, nCpt * sizeof(float)); cudaMalloc((void**)&D_Y, nCpt * sizeof(float)); cudaMalloc((void**)&D_Z, nCpt * sizeof(float)); 
//	cudaMalloc((void**)&D_xmxn_K, nCpt * sizeof(float)); cudaMalloc((void**)&D_x4x4_d, 4 * 4 * sizeof(float)); cudaMalloc((void**)&D_xnx4_c, nCpt * 4 * sizeof(float)); cudaMalloc((void**)&D_ori, 4 * sizeof(float)); cudaMalloc((void**)&D_stps, 4 * sizeof(float));
//	cudaMalloc((void**)&D_RESULT_X, gsz2 * gsz1 *gsz0* sizeof(float)); cudaMalloc((void**)&D_RESULT_Y, gsz2 * gsz1 *gsz0* sizeof(float)); cudaMalloc((void**)&D_RESULT_Z, gsz2 * gsz1 *gsz0* sizeof(float));
//	printf("\t>>gfactor_x : %d \n", gfactor_x);
//	printf("\t>>gfactor_y : %d \n", gfactor_y);
//	printf("\t>>gfactor_z : %d \n", gfactor_z);
//	for (int i = 0; i < x4x4_d.nrows(); i++)
//	{
//		for (int j = 0; j < x4x4_d.ncols(); j++)
//		{
//
//			H_x4x4_d[i*4 + j] = x4x4_d(i + 1, j + 1);
//
//		}
//	}
//	for (int i = 0; i < xnx4_c.nrows(); i++)
//	{
//		for (int j = 0; j < xnx4_c.ncols(); j++)
//		{
//
//			H_xnx4_c[i * 4 + j] = xnx4_c(i + 1, j + 1);
//
//		}
//	}
//	printf("---------mark3-------\n\n");
//	HANDLE_ERROR(cudaMemcpy(D_X, H_X, nCpt * sizeof(float), cudaMemcpyHostToDevice));
//	HANDLE_ERROR(cudaMemcpy(D_Y, H_Y, nCpt * sizeof(float), cudaMemcpyHostToDevice));
//	HANDLE_ERROR(cudaMemcpy(D_Z, H_Z, nCpt * sizeof(float), cudaMemcpyHostToDevice));
//	HANDLE_ERROR(cudaMemcpy(D_ori, H_ori, 4 * sizeof(float), cudaMemcpyHostToDevice));
//	HANDLE_ERROR(cudaMemcpy(D_stps, H_stps, 4 * sizeof(float), cudaMemcpyHostToDevice));
//	HANDLE_ERROR(cudaMemcpy(D_x4x4_d, H_x4x4_d, 4 * 4*sizeof(float), cudaMemcpyHostToDevice));
//	HANDLE_ERROR(cudaMemcpy(D_xnx4_c, H_xnx4_c, 4 * nCpt* sizeof(float), cudaMemcpyHostToDevice));
//	printf("---------mark4-------\n\n");
//	HANDLE_ERROR(cudaMemcpy(D_RESULT_X, H_RESULT_X, gsz2 * gsz1 *gsz0* sizeof(float), cudaMemcpyHostToDevice));
//	HANDLE_ERROR(cudaMemcpy(D_RESULT_Y, H_RESULT_Y, gsz2 * gsz1 *gsz0* sizeof(float), cudaMemcpyHostToDevice));
//	HANDLE_ERROR(cudaMemcpy(D_RESULT_Z, H_RESULT_Z, gsz2 * gsz1 *gsz0* sizeof(float), cudaMemcpyHostToDevice));
//	printf("---------mark5-------\n\n");
//	for (int k = 0; k < gsz2; k++)
//	{
//		dim3 grid((gsz1 + threads_num - 1) / threads_num, (gsz0 + threads_num - 1) / threads_num);
//		dim3 block(threads_num, threads_num);
//		get_cd << <grid, block >> >(nCpt, k, gsz1, gsz0, gfactor_x, gfactor_y, gfactor_z, D_ori, D_stps, D_X, D_Y, D_Z, D_xmxn_K, D_x4x4_d, D_xnx4_c, D_RESULT_X, D_RESULT_Y, D_RESULT_Z);
//		cudaThreadSynchronize();
//		printf("---------mark[%d]-------\n\n", k);
//	}
//	HANDLE_ERROR(cudaMemcpy(H_ori, D_ori, 4 * sizeof(float), cudaMemcpyDeviceToHost));
//	HANDLE_ERROR(cudaMemcpy(H_RESULT_X, D_RESULT_X, gsz2 * gsz1 *gsz0* sizeof(float), cudaMemcpyDeviceToHost));
//	HANDLE_ERROR(cudaMemcpy(H_RESULT_Y, D_RESULT_Y, gsz2 * gsz1 *gsz0* sizeof(float), cudaMemcpyDeviceToHost));
//	HANDLE_ERROR(cudaMemcpy(H_RESULT_Z, D_RESULT_Z, gsz2 * gsz1 *gsz0* sizeof(float), cudaMemcpyDeviceToHost));
//	for (int j = 0; j < 4; j++)
//	{
//
//		printf("---------mark[%f]-------\n\n", H_ori[j]);
//
//	}
//	for (V3DLONG a = 0; a < gsz2; a++)
//	{
//		for (V3DLONG b = 0; b < gsz1; b++)
//		{
//			for (V3DLONG c = 0; c < gsz0; c++)
//			{
//				df_local_3d[a][b][c].sx = H_RESULT_X[a*gsz1 + b*gsz0 + c];
//				df_local_3d[a][b][c].sy = H_RESULT_Y[a*gsz1 + b*gsz0 + c];
//				df_local_3d[a][b][c].sz = H_RESULT_Z[a*gsz1 + b*gsz0 + c];
//			}
//		}
//	}
//	cudaFree(&D_X); cudaFree(&D_ori); cudaFree(&D_stps); cudaFree(&D_x4x4_d); cudaFree(&D_xnx4_c);
//	cudaFree(&D_Y); cudaFree(&D_RESULT_X); cudaFree(&D_RESULT_Y); cudaFree(&D_RESULT_Z);
//	cudaFree(&D_Z);
//	return true;
//}
__device__ void MUL(float *A, float *B, float C[1742], float *D, float E[4], int nCpt)//MUL(x_ori, D_x4x4_d, xmxn_K1, D_xnx4_c, x_stps, nCpt)
{
	int k, a; int p1 = 0; int p2 = 0;

	for (int i = 0; i < 4; i++)
	{
		float sum1 = 0; float sum2 = 0;
		for (k = 0; k < 4; k++)
		{
			sum1 += A[k] * B[k + p1];
		}
		for (a = 0; a < nCpt; a++)
		{
			sum2 += C[a] * D[a + p2];
		}
		E[i] = sum1 + sum2;
		p1 = p1 + 4;
		p2 = p2 + nCpt;
	}


}
__device__ void assignment(V3DLONG k, int row, int col, V3DLONG gsz1, V3DLONG gsz0, V3DLONG gfactor_x, V3DLONG gfactor_y, V3DLONG gfactor_z, float *D_RESULT_X, float *D_RESULT_Y, float *D_RESULT_Z, const float x_stps[4])
{
	//printf("\t>>gfactor_z[%d] [%d] : %f  %f  %f  %f  k=%d:\n", row, col, x_stps[0], x_stps[1], x_stps[2], x_stps[3], k);
	int id = k * 88 + row*gsz0 + col;
	float a = x_stps[1], b = x_stps[2], c = x_stps[3]; __syncthreads();
	//printf("\t>>gfactor_z[%d] [%d] : %f  %f  %f  %f  k=%d:\n", row, col, x_stps[0], a, b, c, k);
	D_RESULT_Y[id] = b - (row - 1)*gfactor_y;// printf("\t>>gfactor_z[%d] [%d] : %f  %f  %f  %f  k=%d:\n", row, col, x_stps[0], x_stps[1], x_stps[2], x_stps[3], k);

	D_RESULT_X[id] = a - (col - 1)*gfactor_x; //__syncthreads();

	D_RESULT_Z[id] = c - (k - 1)*gfactor_z;
	//	printf("\t>>gfactor_z[%d] [%d] :%d  %f  %f  %f  k=%d:\n", row, col, id,  D_RESULT_X[id], D_RESULT_Y[id], D_RESULT_Z[id], k);
}
__global__ void get_cd(int nCpt, V3DLONG k, const V3DLONG gsz1, const V3DLONG gsz0, V3DLONG gfactor_x, V3DLONG gfactor_y, V3DLONG gfactor_z, float * D_X, float * D_Y, float * D_Z, float *D_x4x4_d, float *D_xnx4_c, float *D_RESULT_X, float *D_RESULT_Y, float *D_RESULT_Z)
{
	const int row = blockIdx.y * blockDim.y + threadIdx.y;
	const int col = blockIdx.x * blockDim.x + threadIdx.x;
	if (row >= gsz1 || col >= gsz0)return;
	float x_ori[4]; float xmxn_K1[5000]; float x_stps[4];
	x_stps[0] = 0; x_stps[1] = 0; x_stps[2] = 0; x_stps[3] = 0;
	x_ori[0] = 1.0; x_ori[1] = (col - 1)*gfactor_x; x_ori[2] = (row - 1)*gfactor_y; x_ori[3] = (k - 1)*gfactor_z;
	for (int n = 0; n < nCpt; n++)
	{
		xmxn_K1[n] = -sqrt(((col - 1)*gfactor_x - D_X[n])*((col - 1)*gfactor_x - D_X[n]) + ((row - 1)*gfactor_y - D_Y[n])*((row - 1)*gfactor_y - D_Y[n]) + ((k - 1)*gfactor_z - D_Z[n])*((k - 1)*gfactor_z - D_Z[n]));
	}


	MUL(x_ori, D_x4x4_d, xmxn_K1, D_xnx4_c, x_stps, nCpt);


	D_RESULT_X[k*gsz1*gsz0 + row*gsz0 + col] = x_stps[1] - (col - 1)*gfactor_x;
	D_RESULT_Y[k*gsz1*gsz0 + row*gsz0 + col] = x_stps[2] - (row - 1)*gfactor_y;
	D_RESULT_Z[k*gsz1*gsz0 + row*gsz0 + col] = x_stps[3] - (k - 1)*gfactor_z;

}



extern "C" bool gpu_computedistance(int nCpt, const V3DLONG gsz2, const V3DLONG gsz1, const V3DLONG gsz0, V3DLONG gfactor_x, V3DLONG gfactor_y, V3DLONG gfactor_z, Matrix &x4x4_d, Matrix &xnx4_c, float * H_X, float * H_Y, float * H_Z, DisplaceFieldF3D *** df_local_3d)
{
	float *D_X, *D_Y, *D_Z, *H_xmxn_K, *D_xmxn_K, *H_ori, *D_ori, *H_stps, *D_stps, *H_x4x4_d, *D_x4x4_d, *H_xnx4_c, *D_xnx4_c, *H_RESULT_X, *H_RESULT_Y, *H_RESULT_Z, *D_RESULT_X, *D_RESULT_Y, *D_RESULT_Z;
	H_xmxn_K = (float*)malloc(nCpt * sizeof(float));
	H_ori = (float*)malloc(4 * sizeof(float));
	H_stps = (float*)malloc(4 * sizeof(float));
	H_x4x4_d = (float*)malloc(4 * 4 * sizeof(float));
	H_xnx4_c = (float*)malloc(nCpt * 4 * sizeof(float));
	H_RESULT_X = (float*)malloc(gsz2 * gsz1 *gsz0* sizeof(float));
	H_RESULT_Y = (float*)malloc(gsz2 * gsz1 *gsz0* sizeof(float));
	H_RESULT_Z = (float*)malloc(gsz2 * gsz1 *gsz0* sizeof(float));

	cudaMalloc((void**)&D_X, nCpt * sizeof(float));
	cudaMalloc((void**)&D_Y, nCpt * sizeof(float));
	cudaMalloc((void**)&D_Z, nCpt * sizeof(float));
	cudaMalloc((void**)&D_xmxn_K, nCpt * sizeof(float));
	cudaMalloc((void**)&D_x4x4_d, 4 * 4 * sizeof(float));
	cudaMalloc((void**)&D_xnx4_c, nCpt * 4 * sizeof(float));
	cudaMalloc((void**)&D_ori, 4 * sizeof(float));
	cudaMalloc((void**)&D_stps, 4 * sizeof(float));
	cudaMalloc((void**)&D_RESULT_X, gsz2 * gsz1 *gsz0* sizeof(float));
	cudaMalloc((void**)&D_RESULT_Y, gsz2 * gsz1 *gsz0* sizeof(float));
	cudaMalloc((void**)&D_RESULT_Z, gsz2 * gsz1 *gsz0* sizeof(float));
	printf("\t>>gsz2 : %d \n", gsz2);
	printf("\t>>gsz1 : %d \n", gsz1);
	printf("\t>>gsz0 : %d \n", gsz0);
	for (int i = 0; i < x4x4_d.nrows(); i++)//x4x4_d矩阵转换成数组H_X4X4_d
	{
		for (int j = 0; j < x4x4_d.ncols(); j++)
		{

			H_x4x4_d[j * x4x4_d.nrows() + i] = x4x4_d(i + 1, j + 1);

		}
	}



	for (int i = 0; i < xnx4_c.nrows(); i++)//xnx4_c矩阵转换成数组H_xnx4_c
	{
		for (int j = 0; j < xnx4_c.ncols(); j++)
		{

			H_xnx4_c[j * xnx4_c.nrows() + i] = xnx4_c(i + 1, j + 1);

		}
	}


	HANDLE_ERROR(cudaMemcpy(D_X, H_X, nCpt * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_Y, H_Y, nCpt * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_Z, H_Z, nCpt * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_x4x4_d, H_x4x4_d, 4 * 4 * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_xnx4_c, H_xnx4_c, 4 * nCpt* sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_RESULT_X, H_RESULT_X, gsz2 * gsz1 *gsz0* sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_RESULT_Y, H_RESULT_Y, gsz2 * gsz1 *gsz0* sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_RESULT_Z, H_RESULT_Z, gsz2 * gsz1 *gsz0* sizeof(float), cudaMemcpyHostToDevice));

	for (int k = 0; k < gsz2; k++)
	{
		dim3 grid((gsz0 + threads_num - 1) / threads_num, (gsz1 + threads_num - 1) / threads_num);//dim3 设置一个三维数向量，但最后一维为1
		dim3 block(threads_num, threads_num);
		get_cd << <grid, block >> >(nCpt, k, gsz1, gsz0, gfactor_x, gfactor_y, gfactor_z, D_X, D_Y, D_Z, D_x4x4_d, D_xnx4_c, D_RESULT_X, D_RESULT_Y, D_RESULT_Z);
		cudaDeviceSynchronize();
		//printf("---------mark[%d]-------\n\n", k);
	}

	HANDLE_ERROR(cudaMemcpy(H_RESULT_X, D_RESULT_X, gsz2 * gsz1 * gsz0 * sizeof(float), cudaMemcpyDeviceToHost));//设备到主机 传递数据
	HANDLE_ERROR(cudaMemcpy(H_RESULT_Y, D_RESULT_Y, gsz2 * gsz1 * gsz0 * sizeof(float), cudaMemcpyDeviceToHost));
	HANDLE_ERROR(cudaMemcpy(H_RESULT_Z, D_RESULT_Z, gsz2 * gsz1 * gsz0 * sizeof(float), cudaMemcpyDeviceToHost));



	for (V3DLONG a = 0; a < gsz2; a++)
	{
		for (V3DLONG b = 0; b < gsz1; b++)
		{
			for (V3DLONG c = 0; c < gsz0; c++)
			{
				df_local_3d[a][b][c].sx = H_RESULT_X[a*gsz1*gsz0 + b*gsz0 + c]; //printf("\t>>gfactor_z[%d] [%d] :x=%.3f\n ", b, c, df_local_3d[a][b][c].sx);
				df_local_3d[a][b][c].sy = H_RESULT_Y[a*gsz1*gsz0 + b*gsz0 + c]; //printf("y=%.3f ", df_local_3d[a][b][c].sy);
				df_local_3d[a][b][c].sz = H_RESULT_Z[a*gsz1*gsz0 + b*gsz0 + c];// printf("z=%.3f  ", df_local_3d[a][b][c].sz);
			}
		}
	}

	free(H_xmxn_K);
	free(H_ori);
	free(H_stps);
	free(H_xnx4_c);
	free(H_x4x4_d);
	free(H_RESULT_X);
	free(H_RESULT_Y);
	free(H_RESULT_Z);

	cudaFree(&D_X); cudaFree(&D_ori); cudaFree(&D_stps); cudaFree(&D_x4x4_d); cudaFree(&D_xnx4_c);
	cudaFree(&D_Y); cudaFree(&D_RESULT_X); cudaFree(&D_RESULT_Y); cudaFree(&D_RESULT_Z);
	cudaFree(&D_Z);
	return true;
}