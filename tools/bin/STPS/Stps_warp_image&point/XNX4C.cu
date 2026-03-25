#include "cuda_runtime.h"
#include "device_launch_parameters.h"
#include <iostream>
#include <malloc.h>
#include<time.h>
#include"G:\\postgraduate\\3rdparty\\3rdparty\\v3d_main_jba\\newmat11\\newmat.h"
#include "ele.cuh"



//__global__ void get_bTWOKERNAL(const Matrixtran dev_q2, const Matrixtran dev_xnxn_K, Matrixtran  dev_A1)
//{
//	int row = blockIdx.y * blockDim.y + threadIdx.y;
//	int col = blockIdx.x * blockDim.x + threadIdx.x;
//
//	if (col >= dev_A1.width || row >= dev_A1.height)
//		return;
//	float sum = 0;
//	for (int i = 0; i < dev_q2.height; i++)
//	{
//		sum += dev_q2.elements[i*dev_q2.width + row] * dev_xnxn_K.elements[i*dev_xnxn_K.width + col];
//	}
//	dev_A1.elements[dev_A1.width*row + col] = sum;
//}

__global__ void get_c1(const Matrixtran dev_q2, const Matrixtran dev_A_t, Matrixtran  dev_C1)
{
	int row = blockIdx.y * blockDim.y + threadIdx.y;
	int col = blockIdx.x * blockDim.x + threadIdx.x;

	if (col >= dev_C1.width || row >= dev_C1.height)
		return;
	float sum = 0;
	for (int i = 0; i < dev_q2.width; i++)
	{
		sum += dev_q2.elements[row*dev_q2.width + i] * dev_A_t.elements[i*dev_A_t.width + col];
	}
	dev_C1.elements[dev_C1.width*row + col] = sum;


}
__global__ void get_c2(Matrixtran dev_C1, const Matrixtran dev_q2, Matrixtran  dev_C2)
{
	int row = blockIdx.y * blockDim.y + threadIdx.y;
	int col = blockIdx.x * blockDim.x + threadIdx.x;

	if (col >= dev_C2.width || row >= dev_C2.height)
		return;
	float sum = 0;
	for (int i = 0; i < dev_C1.width; i++)
	{
		sum += dev_C1.elements[row*dev_C1.width + i] * dev_q2.elements[col*dev_q2.width + i];
	}
	dev_C2.elements[dev_C2.width*row + col] = sum;
}
__global__ void get_c(Matrixtran dev_C2, const Matrixtran dev_Y, Matrixtran  dev_C)
{
	int row = blockIdx.y * blockDim.y + threadIdx.y;
	int col = blockIdx.x * blockDim.x + threadIdx.x;

	if (col >= dev_C.width || row >= dev_C.height)
		return;
	float sum = 0;
	for (int i = 0; i < dev_C2.width; i++)
	{
		sum += dev_C2.elements[row*dev_C2.width + i] * dev_Y.elements[i*dev_Y.width + col];
	}
	dev_C.elements[dev_C.width*row + col] = sum;


}
//__global__ void get_ai(Matrixtran dev_A, Matrixtran  dev_A_i)
//{
//	int isx = blockIdx.x * blockDim.x + threadIdx.x;
//	int isy = blockIdx.y * blockDim.y + threadIdx.y;
//	double tmpIn;
//	double tmpInv;
//	//initialize E
//	if (isx == isy)
//		dev_A_i.elements[isy*dev_A_i.width+isx] = 1;
//	else
//		dev_A_i.elements[isy*dev_A_i.width + isx] = 0;
//
//	for (int i = 0; i < dev_A.height; i++)
//	{
//		if (i == isy && isx < (dev_A.width) && isy < dev_A.height)
//		{
//			//消除对角线上的元素（主元）为1
//			tmpIn = dev_A.elements[isy*dev_A.width + isx];
//			dev_A.elements[i*dev_A.width + isx] /= tmpIn;
//			dev_A_i.elements[i*dev_A_i.width + isx] /= tmpIn;
//		}
//		__syncthreads();
//		if (i != isy && isx < 3 && isy < 3)
//		{
//			//将主元所在列的元素化为0 所在行的元素同时变化
//			tmpInv = dev_A_i.elements[isy*dev_A_i.width + i];
//			dev_A.elements[isy*dev_A.width + isx] -= tmpInv * dev_A.elements[i*dev_A.width + isx];
//			dev_A_i.elements[isy*dev_A_i.width + isx] -= tmpInv * dev_A_i.elements[i*dev_A_i.width + isx];
//		}
//		__syncthreads();
//	}
//}
extern "C" bool gpu_xnxn(int ncpt, const Matrix &q2, const Matrix &A_t, Matrix &C)
{

	cudaEvent_t   start, stop;
	HANDLE_ERROR(cudaEventCreate(&start));
	HANDLE_ERROR(cudaEventCreate(&stop));
	HANDLE_ERROR(cudaEventRecord(start, 0));
	printf("\t---------------------cuda process start---------------------\n");
	printf("\tncpt:%d\n", ncpt);
	//分配内存
	Matrixtran dev_q2, dev_A_t, host_q2, host_A_t, host_Y, dev_Y, host_C1, dev_C1, host_C2, dev_C2;
	host_q2.width = ncpt - 4; host_q2.height = ncpt; size_t size_host_q2 = host_q2.width*host_q2.height*sizeof(float); host_q2.elements = (float*)malloc(size_host_q2);
	host_A_t.width = ncpt - 4; host_A_t.height = ncpt - 4; size_t size_host_A_t = host_A_t.width*host_A_t.height*sizeof(float); host_A_t.elements = (float*)malloc(size_host_A_t);
	dev_q2.width = ncpt - 4; dev_q2.height = ncpt; size_t size_dev_q2 = dev_q2.width*dev_q2.height*sizeof(float); cudaMalloc((void**)&dev_q2.elements, size_dev_q2);
	dev_A_t.width = ncpt - 4; dev_A_t.height = ncpt - 4; size_t size_dev_A_t = dev_A_t.width*dev_A_t.height*sizeof(float); cudaMalloc((void**)&dev_A_t.elements, size_dev_A_t);
	//host_Y.width = 4; host_Y.height = ncpt; size_t size_host_Y = host_Y.width*host_Y.height*sizeof(float); host_Y.elements = (float*)malloc(size_host_Y);
	//dev_Y.width = 4; dev_Y.height = ncpt; size_t size_dev_Y = dev_Y.width*dev_Y.height*sizeof(float); cudaMalloc((void**)&dev_Y.elements, size_dev_Y);
	//host_C.width =4; host_C.height = ncpt; size_t size_host_C = host_C.width*host_C.height*sizeof(float); host_C.elements = (float*)malloc(size_host_C);
	//dev_C.width =4; dev_C.height = ncpt ; size_t size_dev_C = dev_C.width*dev_C.height*sizeof(float); cudaMalloc((void**)&dev_C.elements, size_dev_C);
	host_C1.width = ncpt - 4; host_C1.height = ncpt; size_t size_host_C1 = host_C1.width*host_C1.height*sizeof(float); host_C1.elements = (float*)malloc(size_host_C1);
	dev_C1.width = ncpt - 4; dev_C1.height = ncpt; size_t size_dev_C1 = dev_C1.width*dev_C1.height*sizeof(float); cudaMalloc((void**)&dev_C1.elements, size_dev_C1);
	host_C2.width = ncpt; host_C2.height = ncpt; size_t size_host_C2 = host_C2.width*host_C2.height*sizeof(float); host_C2.elements = (float*)malloc(size_host_C2);
	dev_C2.width = ncpt; dev_C2.height = ncpt; size_t size_dev_C2 = dev_C2.width*dev_C2.height*sizeof(float); cudaMalloc((void**)&dev_C2.elements, size_dev_C2);

	//转换数据类型
	for (int i = 0; i < q2.nrows(); i++)
	{
		for (int j = 0; j < q2.ncols(); j++)
		{

			host_q2.elements[i*host_q2.width + j] = q2(i + 1, j + 1);

		}
	}

	for (int i = 0; i < A_t.nrows(); i++)
	{
		for (int j = 0; j < A_t.ncols(); j++)
		{
			host_A_t.elements[i*host_A_t.width + j] = A_t(i + 1, j + 1);

		}
	}

	//for (int i = 0; i < Y.nrows(); i++)
	//{
	//	for (int j = 0; j < Y.ncols(); j++)
	//	{
	//		host_Y.elements[i*host_Y.width + j] = Y(i + 1, j + 1);

	//	}
	//}

	//从cpu复制内存到gpu
	HANDLE_ERROR(cudaMemcpy(dev_q2.elements, host_q2.elements, size_host_q2, cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(dev_A_t.elements, host_A_t.elements, size_host_A_t, cudaMemcpyHostToDevice));
	//HANDLE_ERROR(cudaMemcpy(dev_Y.elements, host_Y.elements, size_host_Y, cudaMemcpyHostToDevice));
	//HANDLE_ERROR(cudaMemcpy(dev_C.elements, host_C.elements, size_host_C, cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(dev_C1.elements, host_C1.elements, size_host_C1, cudaMemcpyHostToDevice));
	HANDLE_ERROR(cudaMemcpy(dev_C2.elements, host_C2.elements, size_host_C2, cudaMemcpyHostToDevice));

	dim3 devgrid((ncpt - 4 + threads_num - 1) / threads_num, (ncpt + threads_num - 1) / threads_num);
	dim3 devblock(threads_num, threads_num);
	dim3 devgrid_c((ncpt - 4 + threads_num - 1) / threads_num, 1);
	dim3 devblock_c(threads_num, 4);

	get_c1 << <devgrid, devblock >> >(dev_q2, dev_A_t, dev_C1);

	get_c2 << <devgrid, devblock >> >(dev_C1, dev_q2, dev_C2);
	//get_c << <devgrid_c, devblock_c >> >(dev_C2, dev_Y, dev_C);
	//从gpu复制内存到cpu
	//HANDLE_ERROR(cudaMemcpy(host_A1.elements, dev_A1.elements, dev_A1.width* dev_A1.height * sizeof(float), cudaMemcpyDeviceToHost));
	HANDLE_ERROR(cudaMemcpy(host_C2.elements, dev_C2.elements, size_dev_C2, cudaMemcpyDeviceToHost));
	//printf("\n");
	//for (int j = 0; j < size_dev_C; j++)
	//{
	//	
	//	printf("%.3f\t", host_C.elements[j]);
	//	if (((j + 1) % host_C.width) == 0){ printf("\n第%d行", (j + 1) / host_C.width); }
	//
	//}


	//转换类型
	for (int i = 0; i < C.nrows(); i++)
	{
		for (int j = 0; j < C.ncols(); j++)
		{
			C(i + 1, j + 1) = host_C2.elements[i*host_C2.width + j];

		}
	}
	//for (long long row = 1; row <= C.nrows(); row++)
	//{
	//	printf("\n第%d行", row);
	//	for (long long col = 1; col <= C.ncols(); col++)
	//		printf("%.3f\t", C(row, col));
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
	cudaFree(&dev_q2);
	cudaFree(&dev_A_t);
	cudaFree(&dev_C1);
	//cudaFree(&dev_Y);
	cudaFree(&dev_C2);
	return true;
}

