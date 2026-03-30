// tps_solver.cpp — TPS and STPS displacement field computation
//
// This is the math core. All formulas are identical to the original
// q_imgwarp_tps_quicksmallmemory.cpp, ported from Newmat to Eigen.
//
// IMPORTANT: This is CPU-only, replacing the CUDA path with Eigen.
// The original code's `cdd == 1` CPU path is used as the reference
// implementation (which uses Newmat QRZ + extend_orthonormal + .i()).

#include "stps/tps_solver.hpp"
#include "stps/logger.hpp"
#include <cmath>
#include <cassert>

namespace stps {

// -----------------------------------------------------------------------
// Classical TPS displacement field
// Identical to original compute_df_tps_subsampled_volume
// -----------------------------------------------------------------------
Volume3D<Displacement3D> compute_df_tps(
    const std::vector<Point3D>& target,
    const std::vector<Point3D>& subject,
    int64_t sz0, int64_t sz1, int64_t sz2,
    int64_t gfactor_x, int64_t gfactor_y, int64_t gfactor_z)
{
    int nCpt = static_cast<int>(target.size());
    if (nCpt != static_cast<int>(subject.size()) || nCpt <= 0) {
        LOG_ERROR("Invalid control point vectors for TPS");
        return {};
    }

    LOG_INFO("Computing TPS displacement field, nCpt=%d", nCpt);

    // Build kernel matrix wR: wR(i,j) = 2 * s * log(s + 1e-20), s = r^2
    Eigen::MatrixXd wR(nCpt, nCpt);
    for (int j = 0; j < nCpt; j++) {
        for (int i = 0; i < nCpt; i++) {
            double dx = target[i].x - target[j].x;
            double dy = target[i].y - target[j].y;
            double dz = target[i].z - target[j].z;
            double s = dx*dx + dy*dy + dz*dz;
            wR(i, j) = 2.0 * s * std::log(s + 1e-20);
        }
    }

    // Build polynomial matrix wP: [1, x, y, z]
    Eigen::MatrixXd wP(nCpt, 4);
    for (int j = 0; j < nCpt; j++) {
        wP(j, 0) = 1.0;
        wP(j, 1) = target[j].x;
        wP(j, 2) = target[j].y;
        wP(j, 3) = target[j].z;
    }

    // Build augmented matrix wL = [wR, wP; wP^T, 0]
    Eigen::MatrixXd wL = Eigen::MatrixXd::Zero(nCpt + 4, nCpt + 4);
    wL.block(0, 0, nCpt, nCpt) = wR;
    wL.block(0, nCpt, nCpt, 4) = wP;
    wL.block(nCpt, 0, 4, nCpt) = wP.transpose();
    // Bottom-right 4x4 block remains zero

    // Build target coordinate matrix wY
    Eigen::MatrixXd wY = Eigen::MatrixXd::Zero(nCpt + 4, 3);
    for (int j = 0; j < nCpt; j++) {
        wY(j, 0) = subject[j].x;
        wY(j, 1) = subject[j].y;
        wY(j, 2) = subject[j].z;
    }

    // Solve wW = wL^{-1} * wY
    // Using FullPivLU for robustness (original used Newmat .i() which is complete inverse)
    Eigen::MatrixXd wW;
    Eigen::FullPivLU<Eigen::MatrixXd> lu(wL);
    if (!lu.isInvertible()) {
        LOG_ERROR("wL matrix is singular, cannot compute TPS weights");
        return {};
    }
    wW = lu.solve(wY);

    // Compute sub-sampled displacement field
    int64_t gsz0 = static_cast<int64_t>(std::ceil(double(sz0) / gfactor_x)) + 1;
    int64_t gsz1 = static_cast<int64_t>(std::ceil(double(sz1) / gfactor_y)) + 1;
    int64_t gsz2 = static_cast<int64_t>(std::ceil(double(sz2) / gfactor_z)) + 1;

    Volume3D<Displacement3D> df(gsz0, gsz1, gsz2);
    LOG_INFO("TPS sub-DF grid: %lldx%lldx%lld", (long long)gsz0, (long long)gsz1, (long long)gsz2);

    int ndimpt = 3;
    std::vector<double> dist(nCpt + ndimpt + 1);

    for (int64_t k = 0; k < gsz2; k++) {
        for (int64_t j = 0; j < gsz1; j++) {
            for (int64_t i = 0; i < gsz0; i++) {
                double px = i * gfactor_x;
                double py = j * gfactor_y;
                double pz = k * gfactor_z;

                // Compute kernel values for this grid point
                for (int n = 0; n < nCpt; n++) {
                    double dx = px - target[n].x;
                    double dy = py - target[n].y;
                    double dz = pz - target[n].z;
                    double s = dx*dx + dy*dy + dz*dz;
                    dist[n] = 2.0 * s * std::log(s + 1e-20);
                }
                dist[nCpt] = 1.0;
                dist[nCpt + 1] = px;
                dist[nCpt + 2] = py;
                dist[nCpt + 3] = pz;

                // Compute warped position
                double sx = 0, sy = 0, sz = 0;
                for (int p = 0; p < nCpt + ndimpt + 1; p++) {
                    sx += dist[p] * wW(p, 0);
                    sy += dist[p] * wW(p, 1);
                    sz += dist[p] * wW(p, 2);
                }

                // Store displacement (warped - original)
                df(i, j, k).sx = static_cast<float>(sx - px);
                df(i, j, k).sy = static_cast<float>(sy - py);
                df(i, j, k).sz = static_cast<float>(sz - pz);
            }
        }
        if (gsz2 > 10 && k % 10 == 0) LOG_DEBUG("TPS DF: z=%lld/%lld", (long long)k, (long long)gsz2);
    }

    return df;
}

// -----------------------------------------------------------------------
// STPS displacement field (B-spline interpolation path)
// Identical to original compute_df_stps_subsampled_volume_4bspline
// Uses the CPU path (cdd==1) as reference:
//   QRZ → extend_orthonormal → split q1/q2 → A = q2^T*K*q2 + lambda*I
//   → c = q2 * (A^{-1} * q2^T * Y) → d = R^{-1} * q1^T * (Y - K*c)
// -----------------------------------------------------------------------
Volume3D<Displacement3D> compute_df_stps(
    const std::vector<Point3D>& target,
    const std::vector<Point3D>& subject,
    int64_t sz0, int64_t sz1, int64_t sz2,
    int64_t gfactor_x, int64_t gfactor_y, int64_t gfactor_z,
    double lambda)
{
    int nCpt = static_cast<int>(target.size());
    if (nCpt != static_cast<int>(subject.size()) || nCpt <= 0) {
        LOG_ERROR("Invalid control point vectors for STPS");
        return {};
    }
    if (nCpt <= 4) {
        LOG_ERROR("STPS requires at least 5 control points (got %d)", nCpt);
        return {};
    }

    LOG_INFO("Computing STPS displacement field, nCpt=%d, lambda=%.4f", nCpt, lambda);

    // Store subject control point coordinates for distance computation
    std::vector<float> H_X(nCpt), H_Y(nCpt), H_Z(nCpt);
    for (int i = 0; i < nCpt; i++) {
        H_X[i] = static_cast<float>(subject[i].x);
        H_Y[i] = static_cast<float>(subject[i].y);
        H_Z[i] = static_cast<float>(subject[i].z);
    }

    // Build kernel K: K(i,j) = -|xi - xj| (negative Euclidean distance, SUBJECT coords)
    // This is the key difference from classical TPS: uses -r instead of r^2*log(r)
    Eigen::MatrixXd xnxn_K(nCpt, nCpt);
    for (int i = 0; i < nCpt; i++) {
        for (int j = 0; j < nCpt; j++) {
            double dx = subject[i].x - subject[j].x;
            double dy = subject[i].y - subject[j].y;
            double dz = subject[i].z - subject[j].z;
            xnxn_K(i, j) = -std::sqrt(dx*dx + dy*dy + dz*dz);
        }
    }

    // Build Q (=P) and Y matrices
    // Q = [1, x, y, z] using SUBJECT coordinates
    // Y = [1, x, y, z] using TARGET coordinates
    Eigen::MatrixXd Q_mat(nCpt, nCpt);
    Q_mat.setZero();
    Eigen::MatrixXd Y(nCpt, 4);
    for (int i = 0; i < nCpt; i++) {
        Q_mat(i, 0) = 1.0;
        Q_mat(i, 1) = subject[i].x;
        Q_mat(i, 2) = subject[i].y;
        Q_mat(i, 3) = subject[i].z;

        Y(i, 0) = 1.0;
        Y(i, 1) = target[i].x;
        Y(i, 2) = target[i].y;
        Y(i, 3) = target[i].z;
    }

    // ── QR decomposition of the first 4 columns ──
    // Original code: QRZ(Q, R) on the nCpt×4 submatrix, then extend_orthonormal
    // We use Eigen's HouseholderQR on the first 4 columns to get the thin QR,
    // then use the full Q (nCpt×nCpt) via completeOrthogonalDecomposition.
    //
    // Step 1: Extract the first 4 columns (the polynomial basis P)
    Eigen::MatrixXd P = Q_mat.block(0, 0, nCpt, 4);

    // Step 2: QR factorization of P (nCpt × 4)
    // This gives Q_full (nCpt × nCpt) orthogonal, R_upper (4 × 4) upper triangular
    Eigen::HouseholderQR<Eigen::MatrixXd> qr(P);
    Eigen::MatrixXd Q_full = qr.householderQ() * Eigen::MatrixXd::Identity(nCpt, nCpt);
    Eigen::MatrixXd R_upper = qr.matrixQR().triangularView<Eigen::Upper>().toDenseMatrix().block(0, 0, 4, 4);

    // Step 3: Split Q into q1 (first 4 columns) and q2 (remaining n-4 columns)
    Eigen::MatrixXd q1 = Q_full.block(0, 0, nCpt, 4);
    Eigen::MatrixXd q2 = Q_full.block(0, 4, nCpt, nCpt - 4);

    // ── Compute non-affine term c ──
    // A = q2^T * K * q2 + lambda * I
    Eigen::MatrixXd A = q2.transpose() * xnxn_K * q2
                       + lambda * Eigen::MatrixXd::Identity(nCpt - 4, nCpt - 4);

    // c = q2 * (A^{-1} * q2^T * Y)
    Eigen::MatrixXd A_inv = A.inverse();
    Eigen::MatrixXd xnx4_c = q2 * (A_inv * (q2.transpose() * Y));

    // ── Compute affine term d ──
    // d = R^{-1} * q1^T * (Y - K * c)
    Eigen::MatrixXd R_inv = R_upper.inverse();
    Eigen::MatrixXd x4x4_d = R_inv * (q1.transpose() * (Y - xnxn_K * xnx4_c));

    LOG_INFO("STPS decomposition complete: d=[4x4], c=[%dx4]", nCpt);

    // ── Compute displacement field on sub-sampled grid ──
    // Grid size with +2 border for B-spline support (identical to original)
    int64_t gsz0 = static_cast<int64_t>(std::ceil(double(sz0) / gfactor_x)) + 1 + 2;
    int64_t gsz1 = static_cast<int64_t>(std::ceil(double(sz1) / gfactor_y)) + 1 + 2;
    int64_t gsz2 = static_cast<int64_t>(std::ceil(double(sz2) / gfactor_z)) + 1 + 2;

    Volume3D<Displacement3D> df(gsz0, gsz1, gsz2);
    LOG_INFO("STPS sub-DF grid: %lldx%lldx%lld (with +2 bspline border)",
             (long long)gsz0, (long long)gsz1, (long long)gsz2);

    // For each grid point, compute displacement
    // x_stps = x_ori * d + K_point * c
    // displacement = x_stps - position
    // NOTE: grid indexing uses (i-1)*gfactor, matching original code
    for (int64_t k = 0; k < gsz2; k++) {
        for (int64_t j = 0; j < gsz1; j++) {
            for (int64_t i = 0; i < gsz0; i++) {
                double px = (i - 1) * gfactor_x;
                double py = (j - 1) * gfactor_y;
                double pz = (k - 1) * gfactor_z;

                // x_ori = [1, px, py, pz]
                Eigen::RowVector4d x_ori(1.0, px, py, pz);

                // K_point(n) = -|point - subject_n|
                Eigen::RowVectorXd xmxn_K(nCpt);
                for (int n = 0; n < nCpt; n++) {
                    double dx = px - H_X[n];
                    double dy = py - H_Y[n];
                    double dz = pz - H_Z[n];
                    xmxn_K(n) = -std::sqrt(dx*dx + dy*dy + dz*dz);
                }

                // x_stps = x_ori * d + K_point * c   (both produce 1×4 row vectors)
                Eigen::RowVector4d x_stps = x_ori * x4x4_d + xmxn_K * xnx4_c;

                // Displacement = warped position - original position
                df(i, j, k).sx = static_cast<float>(x_stps(1) - px);
                df(i, j, k).sy = static_cast<float>(x_stps(2) - py);
                df(i, j, k).sz = static_cast<float>(x_stps(3) - pz);
            }
        }
        if (gsz2 > 10 && k % 10 == 0) LOG_DEBUG("STPS DF: z=%lld/%lld", (long long)k, (long long)gsz2);
    }

    return df;
}

// -----------------------------------------------------------------------
// Build 3D cubic B-spline basis matrix via Kronecker product
// Identical to original q_nonrigid_ini_bsplinebasis_3D
// -----------------------------------------------------------------------
Eigen::MatrixXd build_bspline_basis_3d(int n) {
    if (n <= 0) {
        LOG_ERROR("B-spline basis: n must be > 0");
        return {};
    }

    // Cubic B-spline basis matrix (4×4)
    Eigen::Matrix4d B;
    B << -1,  3, -3,  1,
          3, -6,  3,  0,
         -3,  0,  3,  0,
          1,  4,  1,  0;
    B /= 6.0;

    // Parameter matrix T: T(i,:) = [t^3, t^2, t, 1]
    Eigen::MatrixXd T(n, 4);
    double t_step = 1.0 / n;
    for (int i = 0; i < n; i++) {
        double t = t_step * i;
        T(i, 0) = t * t * t;
        T(i, 1) = t * t;
        T(i, 2) = t;
        T(i, 3) = 1.0;
    }

    // 1D basis: TB = T * B (n × 4)
    Eigen::MatrixXd TB = T * B;

    // 2D basis via Kronecker product: BxB = KP(TB, TB) → (n² × 16)
    int n2 = n * n;
    Eigen::MatrixXd BxB(n2, 16);
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            for (int ci = 0; ci < 4; ci++) {
                for (int cj = 0; cj < 4; cj++) {
                    BxB(i * n + j, ci * 4 + cj) = TB(i, ci) * TB(j, cj);
                }
            }
        }
    }

    // 3D basis via Kronecker product: BxBxB = KP(BxB, TB) → (n³ × 64)
    int n3 = n * n * n;
    Eigen::MatrixXd BxBxB(n3, 64);
    for (int i = 0; i < n2; i++) {
        for (int j = 0; j < n; j++) {
            for (int ci = 0; ci < 16; ci++) {
                for (int cj = 0; cj < 4; cj++) {
                    BxBxB(i * n + j, ci * 4 + cj) = BxB(i, ci) * TB(j, cj);
                }
            }
        }
    }

    LOG_DEBUG("B-spline basis 3D: [%d x %d]", n3, 64);
    return BxBxB;
}

} // namespace stps
