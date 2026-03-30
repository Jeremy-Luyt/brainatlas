#include "cuda_runtime.h"
#include "device_launch_parameters.h"
#include <iostream>
#include <malloc.h>
#include<time.h>
#include"G:\\postgraduate\\3rdparty\\3rdparty\\v3d_main_jba\\newmat11\\newmat.h"
#include "ele.cuh"

//__global__ void matrixInv(float* A, float* B, int i, int wA)
//{
//	int bx = blockIdx.x;
//	int by = blockIdx.y;
//	int tx = threadIdx.x;
//	int ty = threadIdx.y;
//
//	const int index_tx = bx*blockDim.x + tx;
//	const int index_ty = by*blockDim.y + ty;
//	/*int index=index_ty+(index_tx)*wA;*/
//	const float temp = A[i*wA + i];
//	if (index_ty < wA&&index_tx < wA)
//	{
//		B[i*wA + index_tx] = B[i*wA + index_tx] / temp;
//		A[i*wA + index_tx] = A[i*wA + index_tx] / temp;
//	}
//	float Avalue = 0.0;
//	float Bvalue = 0.0;
//	// C[index_ty*wA+index_tx]=A[index_ty*wA+i]*A[i*n+index_tx];
//	// D[index_ty*wA+index_tx]=A[index_ty*wA+i]*B[i*n+index_tx];
//
//	__shared__ float As[BLOCK_DIM][BLOCK_DIM];
//	__shared__ float Bs[BLOCK_DIM][BLOCK_DIM];
//	__shared__ float Cs[BLOCK_DIM][BLOCK_DIM];
//	__shared__ float Ds[BLOCK_DIM][BLOCK_DIM];
//	__shared__ float Ms[BLOCK_DIM][BLOCK_DIM];
//	if (index_ty < wA&&index_tx < wA)
//		for (int m = 0; m < wA / TILE_WIDTH; ++m)
//		{
//			Bs[ty][tx] = B[index_ty*wA + (m*TILE_WIDTH + tx)];
//			As[ty][tx] = A[index_ty*wA + (m*TILE_WIDTH + tx)];
//			Cs[ty][tx] = A[(m*TILE_WIDTH + ty)*wA + i];
//			Ds[ty][tx] = B[i*wA + (m*TILE_WIDTH + tx)];
//			Ms[ty][tx] = A[i*wA + (m*TILE_WIDTH + tx)];
//			__syncthreads();
//			/* int k=i-(i/TILE_WIDTH)*TILE_WIDTH;*/
//
//			// const int k=i%wA;
//			// const int j=i/wA;  
//
//			Avalue = A[index_ty*wA + i] * A[i*wA + index_tx];
//			Bvalue = A[index_ty*wA + i] * B[i*wA + index_tx];
//
//			Bs[ty][tx] = Bs[ty][tx] - Bvalue;
//			As[ty][tx] = As[ty][tx] - Avalue;
//			__syncthreads();
//			if (index_ty != i)
//			{
//				B[index_ty*wA + index_tx] = Bs[ty][tx];
//				A[index_ty*wA + index_tx] = As[ty][tx];
//			}
//		}
//}
__global__ void get_bTWOKERNAL(const Matrixtran dev_q2, const Matrixtran dev_xnxn_K, Matrixtran  dev_A1)
{
	int row = blockIdx.y * blockDim.y + threadIdx.y;
	int col = blockIdx.x * blockDim.x + threadIdx.x;

	if (col >= dev_A1.width || row >= dev_A1.height)
		return;
	float sum = 0;
	for (int i = 0; i < dev_q2.height; i++)
	{
		sum += dev_q2.elements[i*dev_q2.width + row] * dev_xnxn_K.elements[i*dev_xnxn_K.width + col];
	}
	dev_A1.elements[dev_A1.width*row + col] = sum;
}
__global__ void get_g(const Matrixtran dev_A, const Matrixtran dev_q2, Matrixtran  dev_Af)
{
	int row = blockIdx.y * blockDim.y + threadIdx.y;
	int col = blockIdx.x * blockDim.x + threadIdx.x;

	if (col >= dev_Af.width || row >= dev_Af.height)
		return;
	float sum = 0;
	for (int i = 0; i < dev_A.width; i++)
	{
		sum += dev_A.elements[row*dev_A.width + i] * dev_q2.elements[i*dev_q2.width + col];
	}
	dev_Af.elements[dev_Af.width*row + col] = sum;


}
extern "C" bool gpu_A(int ncpt, const Matrix &q2_t, const Matrix &xnxn_K, Matrix &A)
{

	cudaEvent_t   start, stop;
	HANDLE_ERROR(cudaEventCreate(&start));
	HANDLE_ERROR(cudaEventCreate(&stop));
	HANDLE_ERROR(cudaEventRecord(start, 0));
	printf("\t---------------------cuda process start---------------------\n");
	printf("\tncpt:%d\n", ncpt);
	//分配内存
	Matrixtran dev_q2_t, dev_xnxn_K, host_q2_t, host_xnxn_K, host_A1, dev_A1, host_A, dev_A;
	host_q2_t.width = ncpt - 4; host_q2_t.height = ncpt; size_t size_host_q2_t = host_q2_t.width*host_q2_t.height*sizeof(float); host_q2_t.elements = (float*)malloc(host_q2_t.height*host_q2_t.width * sizeof(float));
	host_xnxn_K.width = ncpt; host_xnxn_K.height = ncpt; size_t size_host_xnxn_K = host_xnxn_K.width*host_xnxn_K.height*sizeof(float); host_xnxn_K.elements = (float*)malloc(host_xnxn_K.height*host_xnxn_K.width * sizeof(float));;
	dev_q2_t.width = ncpt - 4; dev_q2_t.height = ncpt; size_t size_dev_q2_t = dev_q2_t.width*dev_q2_t.height*sizeof(float); cudaMalloc((void**)&dev_q2_t.elements, size_dev_q2_t);
	dev_xnxn_K.width = ncpt; dev_xnxn_K.height = ncpt; size_t size_dev_xnxn_K = dev_xnxn_K.width*dev_xnxn_K.height*sizeof(float); cudaMalloc((void**)&dev_xnxn_K.elements, size_dev_xnxn_K);
	host_A1.width = ncpt; host_A1.height = ncpt - 4; size_t size_host_A1 = host_A1.width*host_A1.height*sizeof(float); host_A1.elements = (float*)malloc(host_A1.height*host_A1.width * sizeof(float));
	dev_A1.width = ncpt; dev_A1.height = ncpt - 4; size_t size_dev_A1 = dev_A1.width*dev_A1.height*sizeof(float); cudaMalloc((void**)&dev_A1.elements, size_dev_A1);
	host_A.width = ncpt - 4; host_A.height = ncpt - 4; size_t size_host_A = host_A.width*host_A.height*sizeof(float); host_A.elements = (float*)malloc(host_A.height*host_A.width * sizeof(float));
	dev_A.width = ncpt - 4; dev_A.height = ncpt - 4; size_t size_dev_A = dev_A.width*dev_A.height*sizeof(float); cudaMalloc((void**)&dev_A.elements, size_dev_A);


	//转换数据类型
	for (int i = 0; i < q2_t.nrows(); i++)
	{
		for (int j = 0; j < q2_t.ncols(); j++)
		{

			host_q2_t.elements[i*host_q2_t.width + j] = q2_t(i + 1, j + 1);

		}
	}

	for (int i = 0; i < xnxn_K.nrows(); i++)
	{
		for (int j = 0; j < xnxn_K.ncols(); j++)
		{
			host_xnxn_K.elements[i*host_xnxn_K.width + j] = xnxn_K(i + 1, j + 1);

		}
	}


	//从cpu复制内存到gpu
	HANDLE_ERROR(cudaMemcpy(dev_q2_t.elements, host_q2_t.elements, dev_q2_t.width* dev_q2_t.height * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(dev_xnxn_K.elements, host_xnxn_K.elements, host_xnxn_K.width* host_xnxn_K.height * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(dev_A1.elements, host_A1.elements, host_A1.width* host_A1.height * sizeof(float), cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(dev_A.elements, host_A.elements, host_A.width* host_A.height * sizeof(float), cudaMemcpyHostToDevice));



	dim3 devgrid((ncpt - 4 + threads_num - 1) / threads_num, (ncpt + threads_num - 1) / threads_num);
	dim3 devblock(threads_num, threads_num);

	//get_b << <devgrid, devblock >> >(dev_q2_t, dev_xnxn_K, dev_A1, dev_A);
	get_bTWOKERNAL << <devgrid, devblock >> >(dev_q2_t, dev_xnxn_K, dev_A1);
	get_g << <devgrid, devblock >> >(dev_A1, dev_q2_t, dev_A);
	//从gpu复制内存到cpu
	//HANDLE_ERROR(cudaMemcpy(host_A1.elements, dev_A1.elements, dev_A1.width* dev_A1.height * sizeof(float), cudaMemcpyDeviceToHost));
	HANDLE_ERROR(cudaMemcpy(host_A.elements, dev_A.elements, dev_A.width* dev_A.height * sizeof(float), cudaMemcpyDeviceToHost));
	//printf("\n");
	//for (int j = 0; j < size_dev_A1; j++)
	//{
	//	
	//	printf("%.3f\t", host_A1.elements[j]);
	//	if (((j + 1) % host_A1.width) == 0){ printf("\n第%d行", (j + 1) / host_A1.width); }
	//
	//}
	//转换类型
	for (int i = 0; i < A.nrows(); i++)
	{
		for (int j = 0; j < A.ncols(); j++)
		{
			A(i + 1, j + 1) = host_A.elements[i*host_A.width + j];

		}
	}
	//for (long long row = 1; row <= A.nrows(); row++)
	//{
	//	printf("\n第%d行", row);
	//	for (long long col = 1; col <= A.ncols(); col++)
	//		printf("%.3f\t", A(row, col));
	//	printf("\n");
	//}
	//计时结束
	HANDLE_ERROR(cudaEventRecord(stop, 0));
	HANDLE_ERROR(cudaEventSynchronize(stop));
	float elapsedTime;
	HANDLE_ERROR(cudaEventElapsedTime(&elapsedTime, start, stop));
	printf("\tTime to generate: %3.1f ms\n", elapsedTime);
	HANDLE_ERROR(cudaEventDestroy(start));
	HANDLE_ERROR(cudaEventDestroy(stop));
	printf("\t---------------------cuda process end---------------------\n");
	//释放内存
	cudaFree(&dev_q2_t);
	cudaFree(&dev_xnxn_K);
	cudaFree(&dev_A1);
	cudaFree(&dev_A);
	return true;
}
