#include <stdio.h>
#include <stdlib.h>
#include <cusolverDn.h>
#include "ele.cuh"
#include"G:\\postgraduate\\3rdparty\\3rdparty\\v3d_main_jba\\newmat11\\newmat.h"


extern "C" int gpu_QR(int ncpt, const Matrix &A, Matrix &Q, Matrix &R)
{

	cusolverDnHandle_t cusolverH = NULL;
	const int m = ncpt;
	const int n = ncpt;
	const int lda = ncpt;
	float *q;
	q = (float*)malloc(m*n * sizeof(float));
	float *r;
	r = (float*)malloc(m*n * sizeof(float));

	for (int i = 0; i < ncpt; i++)
	{
		for (int j = 0; j < ncpt; j++)
		{

			q[j*ncpt + i] = A(i + 1, j + 1);

		}
	}

	float *W;
	W = (float*)malloc(m * sizeof(float));
	int info_gpu = 0;//计算状态保存
	// 步骤1：声明句柄
	cusolverDnCreate(&cusolverH);
	// 步骤2：分配显存空间
	float *d_A = NULL; cudaMalloc((void**)&d_A, sizeof(float) * lda * m);//声明Hermite矩阵（与计算后的特征向量为同一空间）
	float *d_W = NULL; cudaMalloc((void**)&d_W, sizeof(float) *m);//声明特征值存储空间
	int *devInfo = NULL; cudaMalloc((void**)&devInfo, sizeof(int));//声明计算结果状态空间
	cudaMemcpy(d_A, q, sizeof(float) * lda * m, cudaMemcpyHostToDevice);//数据拷贝
	cudaMemcpy(d_W, W, sizeof(float)* m, cudaMemcpyHostToDevice);//数据拷贝
	// 步骤3：申请计算缓存空间，并在显存中申请该空间
	float *d_work = NULL; float *h_work = NULL;
	int lwork = 0;
	int hwork = 0;
	//cusolverEigMode_t jobz = CUSOLVER_EIG_MODE_VECTOR; // compute eigenvalues and eigenvectors.
	//cublasFillMode_t uplo = CUBLAS_FILL_MODE_LOWER;
	cusolverDnSgeqrf_bufferSize(cusolverH, m, m, d_A, lda, &lwork);
	cudaMalloc((void**)&d_work, sizeof(float)*lwork);
	cusolverDnSgeqrf(cusolverH, m, m, d_A, lda, d_W, d_work, lwork, devInfo);
	cudaDeviceSynchronize();
	cudaMemcpy(q, d_A, sizeof(float)*lda*m, cudaMemcpyDeviceToHost);
	float *B = (float*)malloc(lda*m * sizeof(float));
	/*	for (int j = 0; j < m*m; j++)
	{
	if (((j) % m) == 0){ printf("\n第%d行", (((j + 1) / m) + 1)); }
	printf("%.3f\t", q[j]);
	}*/
	for (long long row = 0; row < m; row++)
	{

		for (long long col = row; col < m; col++)
			B[row * m + col] = q[col * m + row];

	}

	for (long long row = 0; row < 4; row++)
	{
		//	printf("\n第%d行", row + 1);
		for (long long col = 0; col < 4; col++){
			if (row <= 1) R(row + 1, col + 1) = -B[row * m + col];
			else R(row + 1, col + 1) = B[row * m + col];
			//	printf("%.3f\t", R(row + 1, col + 1));
		}

		//	printf("\n");
	}
	/*	for (long long row = 1; row <= R.nrows(); row++)
	{
	printf("\n第%d行", row);
	for (long long col = 1; col <= R.ncols(); col++)
	printf("%.3f\t", R(row, col));
	printf("\n");
	}*/
	cusolverDnSorgqr_bufferSize(cusolverH, m, m, m, d_A, lda, d_W, &hwork);
	cudaMalloc((void**)&h_work, sizeof(float)*hwork);
	cusolverDnSorgqr(cusolverH, m, m, m, d_A, lda, d_W, h_work, hwork, devInfo);
	cudaMemcpy(r, d_A, sizeof(float)*lda*m, cudaMemcpyDeviceToHost);
	//cudaMemcpy(W, d_W, sizeof(float)*m*m, cudaMemcpyDeviceToHost);
	cudaMemcpy(&info_gpu, devInfo, sizeof(int), cudaMemcpyDeviceToHost);


	//	float *C = (float*)malloc(lda*m * sizeof(float));


	for (long long row = 0; row < m; row++)
	{

		for (long long col = 0; col < 2; col++)
			Q(row + 1, col + 1) = -r[col * m + row];
		for (long long col = 2; col < 4; col++)
			Q(row + 1, col + 1) = r[col * m + row];
	}

	/*for (long long row = 0; row < m; row++)
	{
	printf("\n第%d行", row);
	for (long long col = 0; col < m; col++)
	printf("%.3f\t", Q(row + 1, col + 1));
	printf("\n");
	}*/

	//for (int j = 0; j < m*m; j++)
	//{

	//	if (((j) % m) == 0){ printf("\n第%d行", (((j + 1) / m) + 1)); }
	//	printf("%.3f\t", C[j]);


	//}
	free(q);
	free(r);
	free(W);
	free(B);
	cudaFree(&d_A);
	cudaFree(&h_work);
	cudaFree(&devInfo);
	cudaFree(&d_work);
	cusolverDnDestroy(cusolverH);
	return 0;

}