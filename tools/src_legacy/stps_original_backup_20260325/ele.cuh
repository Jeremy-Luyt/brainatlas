#include "cuda_runtime.h"
#include "device_launch_parameters.h"
#include <iostream>
const int threads_num = 32;
typedef struct
{
	int width;
	int height;
	float* elements;
}Matrixtran;
inline void HANDLE_ERROR(cudaError err)//´íÎó´¦Àíº¯Êý
{
	if (cudaSuccess != err)
	{
		fprintf(stderr, "CUDA Runtime API error: %s.\n", cudaGetErrorString(err));
		return;
	}
}