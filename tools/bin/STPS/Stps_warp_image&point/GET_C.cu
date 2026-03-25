#include "cuda_runtime.h"
#include "device_launch_parameters.h"
#include <iostream>
#include <malloc.h>
#include<time.h>
#include"G:\\postgraduate\\3rdparty\\3rdparty\\v3d_main_jba\\newmat11\\newmat.h"
#include "ele.cuh"
#include <stdio.h>
#include <stdlib.h>
#include <cublas_v2.h>

void invert(float** src, float** dst, int n, const int batchSize)
{
	cublasHandle_t handle;
	cublasCreate_v2(&handle);

	int *P, *INFO;

	cudaMalloc(&P, n * batchSize * sizeof(int));
	cudaMalloc(&INFO, batchSize * sizeof(int));

	int lda = n;

	float **A = (float **)malloc(batchSize * sizeof(float *));
	float **A_d, *A_dflat;
	cudaMalloc(&A_d, batchSize * sizeof(float *));
	cudaMalloc(&A_dflat, n*n*batchSize * sizeof(float));
	A[0] = A_dflat;

	for (int i = 1; i < batchSize; i++)
		A[i] = A[i - 1] + (n*n);
	cudaMemcpy(A_d, A, batchSize * sizeof(float *), cudaMemcpyHostToDevice);
	for (int i = 0; i < batchSize; i++)
		cudaMemcpy(A_dflat + (i*n*n), src[i], n*n * sizeof(float), cudaMemcpyHostToDevice);

	cublasSgetrfBatched(handle, n, A_d, lda, P, INFO, batchSize);

	int *INFOh = new int[batchSize];
	//int INFOh[batchSize];
	cudaMemcpy(INFOh, INFO, batchSize * sizeof(int), cudaMemcpyDeviceToHost);

	for (int i = 0; i < batchSize; i++)
		if (INFOh[i] != 0)
		{
		fprintf(stderr, "Factorization of matrix %d Failed: Matrix may be singular\n", i);
		cudaDeviceReset();
		exit(EXIT_FAILURE);
		}

	float **C = (float **)malloc(batchSize * sizeof(float *));
	float **C_d, *C_dflat;
	cudaMalloc(&C_d, batchSize * sizeof(float *));
	cudaMalloc(&C_dflat, n*n*batchSize * sizeof(float));
	C[0] = C_dflat;
	for (int i = 1; i < batchSize; i++)
		C[i] = C[i - 1] + (n*n);
	cudaMemcpy(C_d, C, batchSize * sizeof(float *), cudaMemcpyHostToDevice);
	cublasSgetriBatched(handle, n, (const float **)A_d, lda, P, C_d, lda, INFO, batchSize);

	cudaMemcpy(INFOh, INFO, batchSize * sizeof(int), cudaMemcpyDeviceToHost);


	for (int i = 0; i < batchSize; i++)
		if (INFOh[i] != 0)
		{
		fprintf(stderr, "Inversion of matrix %d Failed: Matrix may be singular\n", i);
		cudaDeviceReset();
		exit(EXIT_FAILURE);
		}
	for (int i = 0; i < batchSize; i++)
		cudaMemcpy(dst[i], C_dflat + (i*n*n), n*n * sizeof(float), cudaMemcpyDeviceToHost);
	cudaFree(A_d); cudaFree(A_dflat); free(A);
	cudaFree(C_d); cudaFree(C_dflat); free(C);
	cudaFree(P); cudaFree(INFO); cublasDestroy_v2(handle); delete[]INFOh;

}
extern "C" int gpu_A_i(int ncpt, const Matrix &A, Matrix &A_i)
{

	const int n = ncpt - 4;
	const int mybatch = 1;
	float *full_pivot;
	full_pivot = (float*)malloc(n*n * sizeof(float));
	//printf("mark");
	////Random matrix with full pivots
	for (int i = 0; i < n; i++)
	{
		for (int j = 0; j < n; j++)
		{

			full_pivot[i*n + j] = A(i + 1, j + 1);

		}
	}

	float *result_flat = (float *)malloc(mybatch*n*n * sizeof(float));
	float **results = (float **)malloc(mybatch * sizeof(float *));
	for (int i = 0; i < mybatch; i++)
		results[i] = result_flat + (i*n*n);
	float **inputs = (float **)malloc(mybatch * sizeof(float *));
	inputs[0] = full_pivot;

	invert(inputs, results, n, mybatch);
	for (int i = 0; i < n; i++)
	{
		for (int j = 0; j < n; j++)
		{
			A_i(i + 1, j + 1) = results[0][i*n + j];
		}
	}
	//for (long long row = 1; row <= A_i.nrows(); row++)
	//{
	//	printf("\nµÚ%dÐÐ", row);
	//	for (long long col = 1; col <= A_i.ncols(); col++)
	//		printf("%.3f\t", A_i(row, col));
	//	printf("\n");
	//}
	free(full_pivot);
	free(result_flat);
	free(results);
	free(inputs);
	cudaDeviceReset();
	return 0;
}