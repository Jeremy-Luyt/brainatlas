// main_warp_ssdjba_ctlpts.cpp
// ============================================================================
// STPS (Subsampled Thin-Plate Spline) image & point warping tool
// (STPS 子采样薄板样条 图像与点变形工具)
//
// Original by Lei Qu, 2019-03-17
// Refactored: added CLI switch-case argument parsing, removed hardcoded paths,
//             optimized memory management, added bilingual comments
//
// Modes:
//   Single-sample STPS warp:
//     Stps_warp_image.exe -s <img> -T <tar.marker> -S <sub.marker> -o <output> [opts]
//   Batch preprocessing (downsample + NIfTI export):
//     Stps_warp_image.exe -f <data.txt> -D <data_dir> -O <out_dir> [opts]
// ============================================================================

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "getopt.h"
#include <vector>
#include <iostream>
#include <fstream>
#include <time.h>
#include <math.h>

using namespace std;

#define WANT_STREAM
#include "newmatap.h"    // newmat matrix library (需通过项目 Include 路径指定)
#include "newmatio.h"
#include "nifti1_io.h"
#include "stackutil.h"
#include "basic_surf_objs.h"
#include "basic_memory.cpp"
#include "q_imresize.cpp"

#include "q_imgwarp_tps_quicksmallmemory.h"
#include "q_littleQuickWarp_common.h"




// ============================================================================
// v3draw2nii: Save in-memory image data as a NIfTI (.nii.gz) file
// (将内存中的图像数据保存为NIfTI格式文件)
//
// Parameters:
//   Qfileoutput - output file path (输出文件路径)
//   img         - pointer to image data (图像数据指针)
//   sz_img      - image dimensions [w, h, d, c] (图像尺寸数组)
//   type        - NIfTI data type code (NIfTI数据类型)
// ============================================================================
void v3draw2nii(string Qfileoutput, unsigned char *img, long long *sz_img, int type)
{
	nifti_image *nim = nifti_simple_init_nim(sz_img, type);
	nim->nx = sz_img[0];
	nim->ny = sz_img[1];
	nim->nz = sz_img[2];
	nim->nvox = sz_img[0] * sz_img[1] * sz_img[2];
	nim->fname = const_cast<char *>(Qfileoutput.c_str());
	nim->data = img;
	nifti_image_write(nim);
}



// ============================================================================
// Coord3D_PCM: 3D coordinate point class (三维坐标点类)
// ============================================================================
class Coord3D_PCM
{
public:
	double x, y, z;
	Coord3D_PCM(double x0, double y0, double z0) { x = x0; y = y0; z = z0; }
	Coord3D_PCM() { x = y = z = 0; }
};


// ============================================================================
// downsample3dvol: 3D volume downsampling (3D体数据降采样)
//
// Downsample an input 3D image by a given factor.
// (将输入3D图像按给定因子进行降采样)
//
// Template parameter T: data type (unsigned char, float, etc.)
// Parameters:
//   outdata  - [out] downsampled data (降采样后的数据, allocated inside)
//   indata   - [in]  input image data (输入数据)
//   szin     - [in]  input dimensions [w, h, d, c] (输入尺寸)
//   szout    - [out] output dimensions (输出尺寸, allocated inside)
//   resample - [in]  downsample factor, e.g. 4 (降采样因子)
//   tag      - [in]  0=averaging(均值), 1=nearest-neighbor(最近邻)
// ============================================================================
template <class T>
bool downsample3dvol(T *&outdata, T *indata, V3DLONG *szin, V3DLONG * &szout, int resample, unsigned char tag)
{
	// Compute downsample factor per dimension (计算各维度的降采样因子)
	double *dfactor = new double[3];
	for (int i = 0; i < 3; i++)
		dfactor[i] = resample;

	// Compute output dimensions (计算输出尺寸)
	for (V3DLONG i = 0; i < 3; i++)
	{
		szout[i] = (V3DLONG)(floor(double(szin[i]) / double(dfactor[i])));
		if (szout[i] <= 0)
		{
			fprintf(stderr, "ERROR: downsample factor too large, output size <= 0. [%s][%d]\n", __FILE__, __LINE__);
			delete[] dfactor;
			return false;
		}
	}
	szout[3] = szin[3];

	// Allocate output buffer (分配输出内存)
	outdata = new T[szout[0] * szout[1] * szout[2]];
	long szout_01 = szout[0] * szout[1];
	long szin_01 = szin[0] * szin[1];

	if (tag == 0)
	{
		// ---- Averaging mode: compute mean of input voxels in each output block ----
		// ---- 均值降采样: 对每个输出体素求其对应输入区域的平均值 ----
		for (V3DLONG k = 0; k < szout[2]; k++)
		{
			long tt1 = k * szout_01;
			V3DLONG k2low = (V3DLONG)(floor(k * dfactor[2]));
			V3DLONG k2high = (V3DLONG)(floor((k + 1) * dfactor[2] - 1));
			if (k2high > szin[2]) k2high = szin[2];
			V3DLONG kw = k2high - k2low + 1;

			for (V3DLONG j = 0; j < szout[1]; j++)
			{
				long tt2 = j * szout[0];
				V3DLONG j2low = (V3DLONG)(floor(j * dfactor[1]));
				V3DLONG j2high = (V3DLONG)(floor((j + 1) * dfactor[1] - 1));
				if (j2high > szin[1]) j2high = szin[1];
				V3DLONG jw = j2high - j2low + 1;

				for (V3DLONG i = 0; i < szout[0]; i++)
				{
					long idx_out = tt1 + tt2 + i;
					V3DLONG i2low = (V3DLONG)(floor(i * dfactor[0]));
					V3DLONG i2high = (V3DLONG)(floor((i + 1) * dfactor[0] - 1));
					if (i2high > szin[0]) i2high = szin[0];
					V3DLONG iw = i2high - i2low + 1;

					double cubevolume = double(kw) * jw * iw;
					double s = 0.0;
					for (V3DLONG k1 = k2low; k1 <= k2high; k1++)
					{
						long tmp1 = k1 * szin_01;
						for (V3DLONG j1 = j2low; j1 <= j2high; j1++)
						{
							long tmp2 = j1 * szin[0];
							for (V3DLONG i1 = i2low; i1 <= i2high; i1++)
							{
								s += indata[tmp1 + tmp2 + i1];
							}
						}
					}
					outdata[idx_out] = (T)(s / cubevolume);
				}
			}
		}
	}
	else
	{
		// ---- Nearest-neighbor mode: pick the closest input voxel ----
		// ---- 最近邻降采样: 取每个输出体素对应的最近邻输入体素 ----
		for (V3DLONG k = 0; k < szout[2]; k++)
		{
			long tt1 = k * szout_01;
			V3DLONG k2 = V3DLONG(floor(k * dfactor[2]));

			for (V3DLONG j = 0; j < szout[1]; j++)
			{
				long tt2 = j * szout[0];
				V3DLONG j2 = V3DLONG(floor(j * dfactor[1]));

				for (V3DLONG i = 0; i < szout[0]; i++)
				{
					long idx_out = tt1 + tt2 + i;
					V3DLONG i2 = V3DLONG(floor(i * dfactor[0]));
					outdata[idx_out] = indata[k2 * szin_01 + j2 * szin[0] + i2];
				}
			}
		}
	}

	// Optimization: free dfactor (原代码遗漏了此处释放)
	delete[] dfactor;
	return true;
}



// ============================================================================
// euclidean_distance: Euclidean distance between two 3D points
// (计算两个三维点之间的欧氏距离)
//
// Parameters:
//   (x1,y1,z1) - first point  (第一个点)
//   (x2,y2,z2) - second point (第二个点)
// Returns: sqrt( dx^2 + dy^2 + dz^2 )
// ============================================================================
double euclidean_distance(double x1, double y1, double z1,
                          double x2, double y2, double z2)
{
	double dx = x1 - x2;
	double dy = y1 - y2;
	double dz = z1 - z2;
	return sqrt(dx * dx + dy * dy + dz * dz);
}


// ============================================================================
// marker_dis: Compute mean & std-dev of Euclidean distances between two
//             paired marker sets (计算两组配对标记点的欧氏距离均值与标准差)
//
// Parameters:
//   ql_marker_tar  - target marker list  (目标标记点集)
//   ql_marker_sub  - subject marker list (样本标记点集)
//   mean_distance  - [out] mean distance  (平均距离)
//   std_dev        - [out] standard deviation (标准差)
// ============================================================================
void marker_dis(const QList<ImageMarker> &ql_marker_tar,
                const QList<ImageMarker> &ql_marker_sub,
                double &mean_distance, double &std_dev)
{
	if (ql_marker_tar.size() != ql_marker_sub.size())
	{
		fprintf(stderr, "ERROR: marker sets must have identical size.\n");
		return;
	}

	int n = ql_marker_tar.size();
	vector<double> distances(n);

	// Compute distance for each point pair (计算每对点之间的距离)
	for (int i = 0; i < n; i++)
	{
		distances[i] = euclidean_distance(
			ql_marker_tar[i].x, ql_marker_tar[i].y, ql_marker_tar[i].z,
			ql_marker_sub[i].x, ql_marker_sub[i].y, ql_marker_sub[i].z);
	}

	// Compute mean (计算平均距离)
	double sum = 0.0;
	for (int i = 0; i < n; i++)
		sum += distances[i];
	mean_distance = sum / n;

	// Compute standard deviation (计算标准差)
	double var_sum = 0.0;
	for (int i = 0; i < n; i++)
	{
		double diff = distances[i] - mean_distance;
		var_sum += diff * diff;
	}
	std_dev = sqrt(var_sum / n);
}


// ============================================================================
// printHelp: Print command-line usage information
// (打印命令行使用帮助)
// ============================================================================
void printHelp()
{
	printf("\n");
	printf("============================================================\n");
	printf("STPS Warp Image & Point Tool\n");
	printf("(STPS sub-sampled thin-plate spline image & point warping)\n");
	printf("============================================================\n\n");
	printf("Usage:\n");
	printf("  Mode 1 - Single-sample STPS warp:\n");
	printf("    Stps_warp_image.exe -s <img> -T <tar.marker> -S <sub.marker>\n");
	printf("                        -o <output.v3draw> [options]\n\n");
	printf("  Mode 2 - Batch preprocessing (downsample + NIfTI export):\n");
	printf("    Stps_warp_image.exe -f <data.txt> -D <data_dir> -O <out_dir>\n");
	printf("                        [options]\n\n");
	printf("Input parameters:\n");
	printf("  -s <file>    Subject image file (v3draw)\n");
	printf("  -L <file>    Label image file (v3draw, optional)\n");
	printf("  -T <file>    Target marker file (.marker)\n");
	printf("  -S <file>    Subject marker file (.marker)\n\n");
	printf("Output parameters:\n");
	printf("  -o <file>    Output warped image file\n\n");
	printf("Batch parameters:\n");
	printf("  -f <file>    Batch data file (one sample name per line)\n");
	printf("  -D <dir>     Batch data root directory\n");
	printf("  -O <dir>     Batch output root directory\n\n");
	printf("Options:\n");
	printf("  -r <int>     Downsample factor (default: 4)\n");
	printf("  -b <int>     Block size for STPS warp (default: 4)\n");
	printf("  -d <int>     DF interpolation: 0=trilinear, 1=bspline (default: 1)\n");
	printf("  -i <int>     Image interp: 0=bilinear, 1=nearest (default: 0)\n");
	printf("  -R <W,H,D>   Output dimensions override (default: from input)\n");
	printf("  -W           Enable STPS warp in batch mode\n");
	printf("  -h           Print this help message\n");
	printf("\n");
}


// ============================================================================
// process_batch_sample: Process one sample in batch mode
// (批处理模式下处理单个样本)
//
// Workflow:
//   1. Load global.v3draw (and optional label.v3draw)
//   2. Downsample by the given factor
//   3. Read marker files, adjust coordinates for downsampled space
//   4. Export downsampled images as NIfTI (.nii.gz)
//   5. Export adjusted markers as .txt
//   6. Optionally run STPS warp and save result
//
// Parameters:
//   sample_name  - sample identifier (样本名称)
//   data_dir     - data root directory (数据根目录)
//   out_dir      - output root directory (输出根目录)
//   resample     - downsample factor (降采样因子)
//   do_warp      - whether to run STPS warp (是否执行STPS变形)
//   block_size   - block size for warp (变形块大小)
//   df_method    - DF interpolation: 0=trilinear, 1=bspline (位移场插值方法)
//   img_method   - image interpolation: 0=bilinear, 1=NN (图像插值方法)
// Returns: 0 on success, -1 on error
// ============================================================================
int process_batch_sample(const string &sample_name,
                         const string &data_dir,
                         const string &out_dir,
                         int resample, bool do_warp,
                         int block_size, int df_method, int img_method)
{
	printf("Processing sample: %s\n", sample_name.c_str());

	// ---- Construct file paths (构建文件路径) ----
	string sep = "/";
	string path_global = data_dir + sep + sample_name + sep + "global.v3draw";
	string path_label  = data_dir + sep + sample_name + sep + "label.v3draw";
	string path_sub_mk = data_dir + sep + sample_name + sep + "sub.marker";
	string path_tar_mk = data_dir + sep + sample_name + sep + "tar.marker";

	string out_global_nii = out_dir + sep + sample_name + sep + "global.nii.gz";
	string out_label_nii  = out_dir + sep + sample_name + sep + "label.nii.gz";
	string out_sub_txt    = out_dir + sep + sample_name + sep + "sub.txt";
	string out_tar_txt    = out_dir + sep + sample_name + sep + "tar.txt";

	clock_t t_start = clock();

	// ---- 1. Load global image (加载全局配准图像) ----
	unsigned char *p_img_sub = 0;
	long long *sz_img_sub = 0;
	int datatype_sub = 0;

	if (!loadImage(const_cast<char *>(path_global.c_str()), p_img_sub, sz_img_sub, datatype_sub))
	{
		printf("ERROR: loadImage() failed for [%s]\n", path_global.c_str());
		return -1;
	}
	printf("  Image: [w=%lld, h=%lld, z=%lld, c=%lld] dtype=%d\n",
	       sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3], datatype_sub);

	// ---- 2. Load label image if exists (加载标签图像, 可选) ----
	unsigned char *p_img_label = 0;
	long long *sz_img_label = 0;
	int datatype_label = 0;
	bool has_label = false;

	FILE *fp_test = fopen(path_label.c_str(), "rb");
	if (fp_test)
	{
		fclose(fp_test);
		if (loadImage(const_cast<char *>(path_label.c_str()), p_img_label, sz_img_label, datatype_label))
		{
			has_label = true;
			printf("  Label: [w=%lld, h=%lld, z=%lld] dtype=%d\n",
			       sz_img_label[0], sz_img_label[1], sz_img_label[2], datatype_label);
		}
	}

	// ---- 3. Downsample (降采样) ----
	unsigned char *p_img_sub_ds = 0;
	long long *sz_img_sub_ds = new long long[4];
	downsample3dvol(p_img_sub_ds, p_img_sub, sz_img_sub, sz_img_sub_ds, resample, 0);

	unsigned char *p_img_label_ds = 0;
	long long *sz_img_label_ds = 0;
	if (has_label)
	{
		sz_img_label_ds = new long long[4];
		downsample3dvol(p_img_label_ds, p_img_label, sz_img_label, sz_img_label_ds, resample, 1);
	}

	// ---- 4. Read markers (读取标记点) ----
	QString qs_tar = QString::fromStdString(path_tar_mk);
	QString qs_sub = QString::fromStdString(path_sub_mk);
	QList<ImageMarker> ql_marker_tar = readMarker_file(qs_tar);
	QList<ImageMarker> ql_marker_sub = readMarker_file(qs_sub);
	printf("  Markers: tar=%d, sub=%d\n", ql_marker_tar.size(), ql_marker_sub.size());

	// Adjust marker coordinates for downsampled space.
	// (调整标记点坐标到降采样空间)
	// NOTE: offsets (+9, +8, +7) account for image padding applied during
	//       global registration; change if your pipeline uses different padding.
	// (注意: 偏移量+9/+8/+7对应全局配准的 padding, 如流程不同需修改)
	for (int m = 0; m < ql_marker_tar.size(); m++)
	{
		ql_marker_tar[m].x = ql_marker_tar[m].x / resample + 9;
		ql_marker_tar[m].y = ql_marker_tar[m].y / resample + 8;
		ql_marker_tar[m].z = ql_marker_tar[m].z / resample + 7;
	}
	for (int m = 0; m < ql_marker_sub.size(); m++)
	{
		ql_marker_sub[m].x = ql_marker_sub[m].x / resample + 9;
		ql_marker_sub[m].y = ql_marker_sub[m].y / resample + 8;
		ql_marker_sub[m].z = ql_marker_sub[m].z / resample + 7;
	}

	// ---- 5. Export downsampled images as NIfTI (导出降采样图像为NIfTI) ----
	v3draw2nii(out_global_nii, p_img_sub_ds, sz_img_sub_ds, 1);
	if (has_label && p_img_label_ds)
		v3draw2nii(out_label_nii, p_img_label_ds, sz_img_label_ds, 1);

	// ---- 6. Export markers as txt (导出标记点为txt) ----
	ofstream ofs_sub(out_sub_txt.c_str());
	for (int m = 0; m < ql_marker_sub.size(); m++)
		ofs_sub << ql_marker_sub[m].x << ", " << ql_marker_sub[m].y << ", " << ql_marker_sub[m].z << endl;
	ofs_sub.close();

	ofstream ofs_tar(out_tar_txt.c_str());
	for (int m = 0; m < ql_marker_tar.size(); m++)
		ofs_tar << ql_marker_tar[m].x << ", " << ql_marker_tar[m].y << ", " << ql_marker_tar[m].z << endl;
	ofs_tar.close();

	// ---- 7. Optional STPS warp (可选: 执行STPS变形) ----
	if (do_warp)
	{
		unsigned char *p_img_out = 0;
		long long sz_resize[4] = { sz_img_sub_ds[0], sz_img_sub_ds[1],
		                           sz_img_sub_ds[2], 1 };

		// Note: marker order determines warp direction.
		// ql_marker_sub → target parameter, ql_marker_tar → subject parameter
		// (注意: 标记点顺序决定变形方向, sub作为target参数, tar作为subject参数)
		if (!imgwarp_smallmemory(p_img_sub_ds, sz_resize,
			ql_marker_sub, ql_marker_tar,
			(V3DLONG)block_size, (V3DLONG)block_size, (V3DLONG)block_size,
			df_method, img_method, p_img_out, sz_img_sub_ds))
		{
			printf("ERROR: imgwarp_smallmemory() failed for [%s]\n", sample_name.c_str());
		}
		else
		{
			string out_warp = out_dir + sep + sample_name + sep + "warped.v3draw";
			saveImage(const_cast<char *>(out_warp.c_str()), p_img_out, sz_resize, 1);
			printf("  Warped image saved to [%s]\n", out_warp.c_str());
		}
		if (p_img_out) { delete[] p_img_out; p_img_out = 0; }
	}

	// ---- 8. Free memory (释放内存) ----
	printf("  Time: %.2f s\n", (float)(clock() - t_start) / CLOCKS_PER_SEC);

	if (p_img_sub)        { delete[] p_img_sub;        p_img_sub = 0; }
	if (p_img_label)      { delete[] p_img_label;      p_img_label = 0; }
	if (p_img_sub_ds)     { delete[] p_img_sub_ds;     p_img_sub_ds = 0; }
	if (p_img_label_ds)   { delete[] p_img_label_ds;   p_img_label_ds = 0; }
	if (sz_img_sub)       { delete[] sz_img_sub;       sz_img_sub = 0; }
	if (sz_img_label)     { delete[] sz_img_label;     sz_img_label = 0; }
	if (sz_img_sub_ds)    { delete[] sz_img_sub_ds;    sz_img_sub_ds = 0; }
	if (sz_img_label_ds)  { delete[] sz_img_label_ds;  sz_img_label_ds = 0; }

	return 0;
}


// ============================================================================
// main: Entry point with getopt switch-case CLI argument parsing
// (主函数入口: 使用 getopt switch-case 解析命令行参数)
//
// Supports two modes:
//   1) Single-sample STPS warp  (单样本 STPS 变形)
//   2) Batch preprocessing      (批处理预处理)
// ============================================================================
int main(int argc, char *argv[])
{
	// ---- Default parameters (默认参数) ----
	char *fn_img_sub  = 0;    // -s: subject image (样本图像)
	char *fn_label    = 0;    // -L: label image (标签图像, optional)
	char *fn_tar      = 0;    // -T: target marker file (目标标记文件)
	char *fn_sub      = 0;    // -S: subject marker file (样本标记文件)
	char *fn_output   = 0;    // -o: output file (输出文件)
	char *fn_batch    = 0;    // -f: batch data file (批处理数据文件)
	char *dir_data    = 0;    // -D: data root directory (数据根目录)
	char *dir_out     = 0;    // -O: output root directory (输出根目录)
	char *sz_override = 0;    // -R: output dimension override (输出尺寸覆盖)
	int resample      = 4;    // -r: downsample factor (降采样因子)
	int block_size    = 4;    // -b: block size (块大小)
	int df_method     = 1;    // -d: DF interpolation 0=trilinear, 1=bspline
	int img_method    = 0;    // -i: image interpolation 0=bilinear, 1=NN
	bool do_warp      = false; // -W: enable warp in batch mode

	// ============================================================
	// Parse CLI arguments using getopt switch-case
	// (使用 getopt + switch-case 解析命令行参数)
	// ============================================================
	int c;
	while ((c = getopt(argc, argv, "s:L:T:S:o:f:D:O:r:b:d:i:R:Wh")) != -1)
	{
		switch (c)
		{
		case 's': fn_img_sub  = optarg; break;   // subject image
		case 'L': fn_label    = optarg; break;   // label image
		case 'T': fn_tar      = optarg; break;   // target markers
		case 'S': fn_sub      = optarg; break;   // subject markers
		case 'o': fn_output   = optarg; break;   // output file
		case 'f': fn_batch    = optarg; break;   // batch data file
		case 'D': dir_data    = optarg; break;   // data root dir
		case 'O': dir_out     = optarg; break;   // output root dir
		case 'r': resample    = atoi(optarg); break;  // downsample factor
		case 'b': block_size  = atoi(optarg); break;  // block size
		case 'd': df_method   = atoi(optarg); break;  // DF interp method
		case 'i': img_method  = atoi(optarg); break;  // image interp method
		case 'R': sz_override = optarg; break;   // output size W,H,D
		case 'W': do_warp     = true;   break;   // enable warp in batch
		case 'h':
		default:
			printHelp();
			return 0;
		}
	}

	// ---- Determine operating mode (判断运行模式) ----
	bool single_mode = (fn_img_sub && fn_tar && fn_sub && fn_output);
	bool batch_mode  = (fn_batch && dir_data && dir_out);

	if (!single_mode && !batch_mode)
	{
		fprintf(stderr, "ERROR: insufficient arguments. Use -h for help.\n");
		printHelp();
		return -1;
	}

	// ================================================================
	// Mode 1: Single-sample STPS warp
	// (模式1: 单样本 STPS 变形)
	//
	// Flow: load image → read markers → STPS warp → save output
	// ================================================================
	if (single_mode)
	{
		printf("=== Single-sample STPS warp mode ===\n");
		clock_t t_start = clock();

		// 1. Load subject image (加载样本图像)
		unsigned char *p_img_sub = 0;
		long long *sz_img_sub = 0;
		int datatype_sub = 0;

		if (!loadImage(fn_img_sub, p_img_sub, sz_img_sub, datatype_sub))
		{
			printf("ERROR: loadImage() failed for [%s]\n", fn_img_sub);
			return -1;
		}
		printf("  Image: [w=%lld, h=%lld, z=%lld, c=%lld] dtype=%d\n",
		       sz_img_sub[0], sz_img_sub[1], sz_img_sub[2], sz_img_sub[3], datatype_sub);

		// 2. Read marker files (读取标记点文件)
		QList<ImageMarker> ql_marker_tar = readMarker_file(QString(fn_tar));
		QList<ImageMarker> ql_marker_sub = readMarker_file(QString(fn_sub));
		printf("  Markers: tar=%d, sub=%d\n", ql_marker_tar.size(), ql_marker_sub.size());

		// 3. Determine output dimensions (确定输出尺寸)
		//    Default: use input image size; override with -R W,H,D
		long long sz_img_resize[4];
		if (sz_override)
		{
			if (sscanf(sz_override, "%lld,%lld,%lld",
			    &sz_img_resize[0], &sz_img_resize[1], &sz_img_resize[2]) != 3)
			{
				printf("ERROR: invalid -R format. Expected W,H,D (e.g. 568,320,456)\n");
				delete[] p_img_sub; delete[] sz_img_sub;
				return -1;
			}
			sz_img_resize[3] = 1;
		}
		else
		{
			// Default: use input image dimensions (默认使用输入尺寸)
			sz_img_resize[0] = sz_img_sub[0];
			sz_img_resize[1] = sz_img_sub[1];
			sz_img_resize[2] = sz_img_sub[2];
			sz_img_resize[3] = 1;
		}
		printf("  Output size: [%lld, %lld, %lld]\n",
		       sz_img_resize[0], sz_img_resize[1], sz_img_resize[2]);

		// 4. Run STPS warp (执行 STPS 变形)
		//    Note on marker order: ql_marker_sub is passed as the "target"
		//    parameter and ql_marker_tar as "subject" to define the warp
		//    direction from subject space → target space.
		//    (注意: sub标记作为target参数, tar标记作为subject参数,
		//     定义从 subject 空间到 target 空间的变形方向)
		unsigned char *p_img_out = 0;
		V3DLONG szB = (V3DLONG)block_size;

		if (!imgwarp_smallmemory(p_img_sub, sz_img_resize,
			ql_marker_sub, ql_marker_tar,
			szB, szB, szB, df_method, img_method,
			p_img_out, sz_img_sub))
		{
			printf("ERROR: imgwarp_smallmemory() failed.\n");
			delete[] p_img_sub; delete[] sz_img_sub;
			return -1;
		}

		// 5. Save output (保存输出图像)
		saveImage(fn_output, p_img_out, sz_img_resize, 1);
		printf("  Output saved to [%s]\n", fn_output);
		printf("  Total time: %.2f s\n", (float)(clock() - t_start) / CLOCKS_PER_SEC);

		// 6. Free memory (释放内存)
		if (p_img_sub)  { delete[] p_img_sub;  p_img_sub = 0; }
		if (sz_img_sub) { delete[] sz_img_sub; sz_img_sub = 0; }
		if (p_img_out)  { delete[] p_img_out;  p_img_out = 0; }
	}

	// ================================================================
	// Mode 2: Batch preprocessing
	// (模式2: 批处理预处理)
	//
	// Flow: read sample list → for each: load, downsample, export NIfTI,
	//       export markers as txt, optional STPS warp
	// ================================================================
	if (batch_mode)
	{
		printf("=== Batch preprocessing mode ===\n");
		printf("  Data dir:   %s\n", dir_data);
		printf("  Output dir: %s\n", dir_out);
		printf("  Resample:   %d\n", resample);
		printf("  Warp:       %s\n", do_warp ? "enabled" : "disabled");

		// Read sample names from batch file (从批处理文件读取样本列表)
		vector<string> samples;
		ifstream fin(fn_batch);
		if (!fin.is_open())
		{
			printf("ERROR: cannot open batch file [%s]\n", fn_batch);
			return -1;
		}
		string line;
		while (getline(fin, line))
		{
			if (!line.empty())
				samples.push_back(line);
		}
		fin.close();
		printf("  Total samples: %d\n", (int)samples.size());

		// Process each sample (逐样本处理)
		for (int idx = 0; idx < (int)samples.size(); idx++)
		{
			printf("\n[%d/%d] ", idx + 1, (int)samples.size());
			int ret = process_batch_sample(
				samples[idx], string(dir_data), string(dir_out),
				resample, do_warp, block_size, df_method, img_method);
			if (ret != 0)
				printf("WARNING: sample [%s] returned error %d\n", samples[idx].c_str(), ret);
		}
	}

	printf("\nProgram exit success.\n");
	return 0;
}
