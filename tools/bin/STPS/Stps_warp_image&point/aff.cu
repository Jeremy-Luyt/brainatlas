#include "ele.cuh"
#include "stackutil.h"
#include "cuda_runtime_api.h"
#include <malloc.h>
#include <time.h>
#include"G:\\postgraduate\\3rdparty\\3rdparty\\v3d_main_jba\\newmat11\\newmat.h"
#include <math.h>
#include"qstring.h"
#include <QtGui>
//#include "q_warp_affine_tps.h"
#include "q_imgwarp_tps_quicksmallmemory.h"
#include "G:\\postgraduate\\3rdparty\\3rdparty\\v3d_main_basic_c_fun\\basic_memory.cpp"//note: should not include .h file, since they are template functions£¨very important£©
#include "cuda_runtime.h"
#include "cublas_v2.h"
#include "cusolverDn.h"
#include <assert.h>
#include <stdlib.h>
//#include <QtGui>

extern "C" Matrix matrixMultiply(const int m, const int n, const int k, Matrix &A, Matrix &B);

#define number 5000   //Ua_size in TPS
#define EPS 0.0001




extern "C" Matrix matrixMultiply(const int m, const int n, const int k, Matrix &A, Matrix &B)
{
	//A*B=C
	//m:A.row;n:B.col;k:A.col
	Matrix C(m, n);
	cudaError_t cudaStat;
	cublasStatus_t stat;
	float *H_A, *H_B, *H_C;

	float *D_A, *D_B, *D_C;
	int r_size = 8192;
	int m_size = r_size*r_size;

	H_A = (float*)malloc(m * k * sizeof(float));
	H_B = (float*)malloc(k * n * sizeof(float));
	H_C = (float*)malloc(m * n * sizeof(float));

	/*
	H_A = (float*)malloc(8192 * 8192 * sizeof(float));
	H_B = (float*)malloc(8192 * 8192 * sizeof(float));
	H_C = (float*)malloc(8192 * 8192 * sizeof(float));*/

	/*	for (int i = 0; i < m_size; i++) {
	H_A[i] = rand() / 10000000;
	H_B[i] = rand() / 10000000;
	H_C[i] = 0;
	}*/

	cudaStat = cudaMalloc((void**)&D_A, m * k * sizeof(float));
	cudaStat = cudaMalloc((void**)&D_B, k * n * sizeof(float));
	cudaStat = cudaMalloc((void**)&D_C, m * n * sizeof(float));

	/*	cudaStat = cudaMalloc((void**)&D_A, r_size * r_size * sizeof(float));
	cudaStat = cudaMalloc((void**)&D_B, r_size * r_size * sizeof(float));
	cudaStat = cudaMalloc((void**)&D_C, r_size * r_size * sizeof(float));*/
	printf("cudaStat %d\n", cudaStat);
	for (int i = 0; i < A.nrows(); i++)
	{
		for (int j = 0; j < A.ncols(); j++)
		{

			H_A[i * A.ncols() + j] = A(i + 1, j + 1);
			//if (H_A[i * A.ncols() + j] > EPS)printf("%f", H_A[i * A.ncols() + j]);
		}

	}

	for (int i = 0; i < B.nrows(); i++)
	{
		for (int j = 0; j < B.ncols(); j++)
		{

			H_B[i * B.ncols() + j] = B(i + 1, j + 1);
			//if (H_B[i * B.ncols() + j] > EPS)printf("%.2f\n", H_B[i * B.ncols() + j]);
		}

	}

	HANDLE_ERROR(cudaMemcpy(D_A, H_A, m * k * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(D_B, H_B, k * n * sizeof(float), cudaMemcpyHostToDevice));

	//	stat = cublasSetMatrix(r_size, r_size, sizeof(*H_A), H_A, r_size, D_A, r_size);
	//	stat = cublasSetMatrix(r_size, r_size, sizeof(*H_B), H_B, r_size, D_B, r_size);
	//	stat = cublasSetMatrix(r_size, r_size, sizeof(*H_C), H_C, r_size, D_C, r_size);

	//	dim3 threads(1, 1);
	//	dim3 grid(1, 1);

	const float alpha = 1.0f;
	const float beta = 0.0f;

	cublasHandle_t handle;
	cublasCreate(&handle);

	//	stat = cublasSgemm(handle, CUBLAS_OP_T, CUBLAS_OP_N, n, m, k, &alpha, D_A, n, D_B, k, &beta, D_C, n);
	stat = cublasSgemm(handle, CUBLAS_OP_N, CUBLAS_OP_N, n, m, k, &alpha, D_B, n, D_A, k, &beta, D_C, n);
	//	cublasSgemm(handle, CUBLAS_OP_T, CUBLAS_OP_T, m, n, k, &alpha, D_A, k, D_B, n, &beta, D_C, m);
	//	stat = cublasSgemm(handle, CUBLAS_OP_N, CUBLAS_OP_N, r_size, r_size, r_size, &alpha, D_A, r_size, D_B, r_size, &beta, D_C, r_size);
	//	stat=cublasDgemm(handle, CUBLAS_OP_N, CUBLAS_OP_N, n, m, k, &alpha, D_B, n, D_A, k, &beta, D_C, n);
	//	stat = cublasDgemm(handle, CUBLAS_OP_N, CUBLAS_OP_N, m, m, m, &alpha, D_A, m, D_B, m, &beta, D_C, m);
	cublasDestroy(handle);

	//	stat = cublasGetMatrix(r_size, r_size, sizeof(*H_C), D_C, r_size, H_C, r_size);
	printf("cublas %d\n", stat);
	HANDLE_ERROR(cudaMemcpy(H_C, D_C, m * n * sizeof(float), cudaMemcpyDeviceToHost));

	//	cToR(H_C, m, n);
	for (int i = 0; i < C.nrows(); i++)
	{
		for (int j = 0; j < C.ncols(); j++)
		{

			C(i + 1, j + 1) = H_C[i * C.ncols() + j];
			//if (C(i + 1, j + 1) > EPS)printf("%f\n", C(i + 1, j + 1));
		}

	}

	/*	for (int i = 0; i < C.nrows(); i++)
	{
	for (int j = 0; j < C.ncols(); j++)
	{

	C(i + 1, j + 1) = H_C[j * C.ncols() + i];

	}

	}*/

	free(H_A);
	free(H_B);
	free(H_C);
	cudaFree(D_A);
	cudaFree(D_B);
	cudaFree(D_C);

	return C;
}


