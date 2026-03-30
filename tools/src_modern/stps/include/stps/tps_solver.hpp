// tps_solver.hpp — TPS and STPS displacement field computation
// Faithfully reimplements the original algorithms using Eigen.
#pragma once

#include "stps/types.hpp"
#include <vector>

namespace stps {

// -----------------------------------------------------------------------
// Classical TPS displacement field (trilinear DF interpolation path)
//
// Algorithm (identical to original compute_df_tps_subsampled_volume):
//   1. Build kernel: wR(i,j) = 2 * r^2 * log(r + 1e-20),  r^2 = |t_i - t_j|^2
//   2. Build augmented matrix wL = [wR, wP; wP^T, 0],  wP = [1, x, y, z]
//   3. Solve wW = wL^{-1} * wY
//   4. For each sub-grid point, compute displacement via TPS kernel sum
//
// Returns sub-sampled displacement field of size (gsz0, gsz1, gsz2).
// -----------------------------------------------------------------------
Volume3D<Displacement3D> compute_df_tps(
    const std::vector<Point3D>& target,
    const std::vector<Point3D>& subject,
    int64_t sz0, int64_t sz1, int64_t sz2,
    int64_t gfactor_x, int64_t gfactor_y, int64_t gfactor_z);

// -----------------------------------------------------------------------
// STPS displacement field (B-spline DF interpolation path)
//
// Algorithm (identical to original compute_df_stps_subsampled_volume_4bspline):
//   1. Build K(i,j) = -|xi - xj| (negative Euclidean distance, subject coords)
//   2. Build P = [1, x, y, z] for control points
//   3. QR-decompose P via Householder → Q*R, extend Q to full orthonormal
//   4. Split Q → q1 (first 4 cols), q2 (remaining n-4 cols)
//   5. Non-affine:  A = q2^T * K * q2 + lambda*I;  c = q2 * A^{-1} * q2^T * Y
//   6. Affine:      d = R^{-1} * q1^T * (Y - K*c)
//   7. For each grid point:  x_stps = x_ori * d + K_point * c
//      displacement = x_stps - position
//
// Grid has +2 border for B-spline support, using (i-1)*gfactor indexing.
// -----------------------------------------------------------------------
Volume3D<Displacement3D> compute_df_stps(
    const std::vector<Point3D>& target,
    const std::vector<Point3D>& subject,
    int64_t sz0, int64_t sz1, int64_t sz2,
    int64_t gfactor_x, int64_t gfactor_y, int64_t gfactor_z,
    double lambda = 0.2);

// -----------------------------------------------------------------------
// Build 3D cubic B-spline basis matrix (Kronecker product)
// Returns matrix of size (n^3, 64) where n = block_size.
// Identical to original q_nonrigid_ini_bsplinebasis_3D.
// -----------------------------------------------------------------------
Eigen::MatrixXd build_bspline_basis_3d(int n);

} // namespace stps
