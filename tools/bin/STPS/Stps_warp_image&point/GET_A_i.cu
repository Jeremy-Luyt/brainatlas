#include "cuda_runtime.h"
#include "device_launch_parameters.h"
#include <cuda.h>
#include <stdio.h>
#include <malloc.h>
#include <iostream>
#include <chrono>
#include <ctime>
#include <time.h>
#include <stdlib.h>
#include"G:\\postgraduate\\3rdparty\\3rdparty\\v3d_main_jba\\newmat11\\newmat.h"
#include "ele.cuh"



__global__ void MatrixInvert(float *A_splice, float *A_mem, int n, int row)
{
	int i = blockDim.x * blockIdx.x + threadIdx.x;
	int j = blockDim.y * blockIdx.y + threadIdx.y;

	if (i >= 2 * n || j >= n) return;

	float temp = 0;



	if (j != row)
	{
		temp = A_mem[j] / A_splice[row * 2 * n + row];
		A_splice[j * 2 * n + i] = A_splice[j * 2 * n + i] - A_splice[row * 2 * n + i] * temp;
	}
}


__global__ void Matrixend(float *A_splice, float *A_mem, int n, int row)
{
	int i = blockDim.x * blockIdx.x + threadIdx.x;

	if (i >= 2 * n) return;

	float temp = 0;


	A_splice[row * 2 * n + i] = A_splice[row * 2 * n + i] / A_mem[row];


}


__global__ void Matrixpre(float *A_splice, int n, int row)
{
	int i = blockDim.x * blockIdx.x + threadIdx.x;

	if (i >= 2 * n) return;

	float temp = 0;


	for (int Newrow = 0; Newrow < n; Newrow++)
	{
		if (A_splice[Newrow * 2 * n + row] != 0)
		{
			A_splice[row * 2 * n + i] = A_splice[row * 2 * n + i] + A_splice[Newrow * 2 * n + i];
			break;
		}
	}

}

__global__ void Matrixmem(float *A_mem, float *A_splice, int n, int row)
{
	int i = blockDim.x * blockIdx.x + threadIdx.x;

	if (i >= n) return;

	A_mem[i] = A_splice[i * 2 * n + row];
}


extern "C" int gpu_A_i_new(int ncpt, const Matrix &A, Matrix &A_i)
{
	const int n = ncpt - 4;
	const int size = n * n * sizeof(float);

	float *h_A_splice = (float*)malloc(2 * size);


	for (int i = 0; i < n; i++)
	{
		for (int j = 0; j < 2 * n; j++)
		{
			if (j < n)
			{
				h_A_splice[i * 2 * n + j] = A(i + 1, j + 1);
			}
			else if (j >= n)
			{
				if (i + n == j)
				{
					h_A_splice[i * 2 * n + j] = 1;
				}
				else
				{
					h_A_splice[i * 2 * n + j] = 0;
				}
			}
		}
	}



	float *d_A_splice, *d_A_mem;
	HANDLE_ERROR(cudaMalloc((void**)&d_A_splice, 2 * size));
	HANDLE_ERROR(cudaMalloc((void**)&d_A_mem, n * sizeof(float)));

	HANDLE_ERROR(cudaMemcpy(d_A_splice, h_A_splice, 2 * size, cudaMemcpyHostToDevice));

	int threads = 32;
	dim3 block(threads, threads);
	dim3 grid((2 * n + threads - 1) / threads, (n + threads - 1) / threads);

	dim3 block1(threads);
	dim3 grid1((2 * n + threads - 1) / threads);


	for (int row = 0; row < n; row++)
	{
		if (h_A_splice[row * 2 * n + row] == 0)
		{
			Matrixpre << <grid1, block1 >> > (d_A_splice, n, row);
			cudaDeviceSynchronize();
		}
	}


	for (int row = 0; row < n; row++)
	{
		Matrixmem << <grid1, block1 >> > (d_A_mem, d_A_splice, n, row);
		cudaDeviceSynchronize();
		MatrixInvert << <grid, block >> > (d_A_splice, d_A_mem, n, row);
		cudaDeviceSynchronize();
		Matrixend << < grid1, block1 >> > (d_A_splice, d_A_mem, n, row);

	}

	HANDLE_ERROR(cudaMemcpy(h_A_splice, d_A_splice, 2 * size, cudaMemcpyDeviceToHost));

	for (int i = 0; i < n; i++)
	{
		for (int j = 0; j < n; j++)
		{
			A_i(i + 1, j + 1) = h_A_splice[i * 2 * n + n + j];
		}
	}

	free(h_A_splice);
	HANDLE_ERROR(cudaFree(d_A_splice));
	HANDLE_ERROR(cudaFree(d_A_mem));
	cudaDeviceReset();

	return 0;
}