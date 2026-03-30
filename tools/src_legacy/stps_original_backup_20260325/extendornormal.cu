#include <stdio.h>
#include <stdlib.h>
#include <cusolverDn.h>
#include "ele.cuh"
#include"G:\\postgraduate\\3rdparty\\3rdparty\\v3d_main_jba\\newmat11\\newmat.h"

__global__ void get_gpu_extendornormal(float *d_Q, int ncpt, int i, int k, float *X, float *SSR)
{

	int idx = blockIdx.x * blockDim.x + threadIdx.x;

	if (idx >= ncpt)return;

	float sum = 0;
	for (int j = 0; j < i; j++)
	{
		sum += -d_Q[idx*ncpt + j] * d_Q[(k - 1)*ncpt + j];
	}

	X[idx] = sum;
	////	printf("\n值为：%f\t", sum);
	//	__syncthreads();
	//	if (idx == (k-1))
	//	{
	//		X[idx] += 1.0;
	//		float SumSquare = 0;
	//		for (int j = 0; j < ncpt; j++)
	//		{
	//			SumSquare += X[j] * X[j];
	//		}
	//		for (int j = 0; j < ncpt; j++)
	//		{
	//			X[j] /= sqrt(SumSquare);
	//		}
	//		
	//	}
	//	__syncthreads();
	//	d_Q[idx*ncpt + i ] = X[idx];
	//	SSR[idx] += X[idx] * X[idx];
	//	//__syncthreads();
}
__global__ void get_gpu_assign(float *d_Q, int ncpt, int i, float *X, float *SSR)
{

	int idx = blockIdx.x * blockDim.x + threadIdx.x;

	if (idx >= ncpt)return;


	d_Q[idx*ncpt + i] = X[idx];
	SSR[idx] += X[idx] * X[idx];
	//__syncthreads();
}

extern "C" int gpu_extendornormal(int ncpt, int n, Matrix &Q)
{
	ColumnVector SSR;
	//ColumnVector X;
	//Matrix A1 = Q.Columns(1, n);
	SSR = Q.sum_square_rows();//赋值每行元素的平方和，元素从1开始算起
	//printf("\t>>t time consume %f\n", SSR(1)); printf("\t>>t time consume %f\n", SSR(2)); printf("\t>>t time consume %f\n", SSR(3));
	//int t; SSR.minimum1(t); printf("\t>>t time consume %d\n", t);
	float *h_Q, *d_Q, *h_SSR, *d_SSR, *h_X, *d_X;
	h_Q = (float*)malloc(ncpt*ncpt * sizeof(float));  cudaMalloc((void**)&d_Q, ncpt*ncpt * sizeof(float));
	h_SSR = (float*)malloc(ncpt * sizeof(float));  cudaMalloc((void**)&d_SSR, ncpt * sizeof(float));
	h_X = (float*)malloc(ncpt * sizeof(float));  cudaMalloc((void**)&d_X, ncpt * sizeof(float));
	for (int i = 0; i < Q.nrows(); i++)
	{
		for (int j = 0; j < Q.ncols(); j++)
		{

			h_Q[i*ncpt + j] = Q(i + 1, j + 1);

		}
	}
	for (int j = 1; j <= ncpt; j++)
	{

		h_SSR[j - 1] = SSR(j);

	}
	HANDLE_ERROR(cudaMemcpy(d_Q, h_Q, ncpt* ncpt * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(d_SSR, h_SSR, ncpt * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(d_X, h_X, ncpt * sizeof(float), cudaMemcpyHostToDevice));
	for (int i = n; i < ncpt; ++i)
	{

		int k; SSR.minimum1(k);// printf("\nk值为：%d\t", k);//返回最小元素的行号
		//// orthogonalise column with 1 at element k, 0 elsewhere
		////printf("\t>> %d\n", i);// next line is rather inefficient
		//ColumnVector X;
		int block = 64;
		int grid = (ncpt + 64 - 1) / 64;
		get_gpu_extendornormal << <grid, block >> >(d_Q, ncpt, i, k, d_X, d_SSR);
		HANDLE_ERROR(cudaMemcpy(h_X, d_X, ncpt * sizeof(float), cudaMemcpyDeviceToHost));
		h_X[k - 1] += 1.0;
		float SumSquare = 0;
		for (int j = 0; j < ncpt; j++)
		{
			SumSquare += h_X[j] * h_X[j];
		}
		for (int j = 0; j < ncpt; j++)
		{
			h_X[j] /= sqrt(SumSquare);
		}
		HANDLE_ERROR(cudaMemcpy(d_X, h_X, ncpt * sizeof(float), cudaMemcpyHostToDevice));
		get_gpu_assign << <grid, block >> >(d_Q, ncpt, i, d_X, d_SSR);
		//printf("\nk值为：%d\t", k);
		//get_gpu_extendornormal << <1, 3 >> >(d_Q, ncpt, i, k, d_X, d_SSR);
		HANDLE_ERROR(cudaMemcpy(h_SSR, d_SSR, ncpt * sizeof(float), cudaMemcpyDeviceToHost));
		for (int j = 1; j <= ncpt; j++)
		{

			SSR(j) = h_SSR[j - 1];

		}

		////ColumnVector X = -Q.Columns(1, i) * Q.SubMatrix(k, k, 1, i).t();
		//X(k) += 1.0;
		//// normalise
		//X /= sqrt(X.SumSquare());	//for (k = 1; k <= nr; ++k) printf("\t>> %f\n", X(k));
		//// update row sums of squares
		//for (k = 1; k <= ncpt; ++k) SSR(k) += X(k)*X(k);
		//// load new column into matrix
		//Q.Column(i + 1) = X;

	}
	HANDLE_ERROR(cudaMemcpy(h_Q, d_Q, ncpt*ncpt * sizeof(float), cudaMemcpyDeviceToHost));
	HANDLE_ERROR(cudaMemcpy(h_X, d_X, ncpt * sizeof(float), cudaMemcpyDeviceToHost));
	//for (int i = 0; i < ncpt*ncpt; i++)printf("\n值为：%f\t", h_Q[i]);



	for (int i = 0; i < Q.nrows(); i++)
	{
		for (int j = 0; j < Q.ncols(); j++)
		{

			Q(i + 1, j + 1) = h_Q[i*ncpt + j];

		}
	}
	free(h_Q);
	free(h_SSR);
	free(h_X);
	cudaFree(&d_Q); cudaFree(&d_X);
	cudaFree(&d_SSR);
	return 0;

}