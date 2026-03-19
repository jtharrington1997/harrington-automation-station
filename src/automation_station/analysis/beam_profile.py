"""
utils/analysis.py
Beam analysis: clip-level extraction, caustic fitting, and plotting.
"""

import numpy as np
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d


def beam_caustic(z, w0, z0, M2, wavelength_um=2.94):
    """Hyperbolic beam caustic model."""
    lam = wavelength_um
    return np.sqrt(w0**2 * (1 + (z - z0)**2 * ((M2 * lam) / (np.pi * w0**2))**2))


def find_clip_positions(x_arr, p_arr, P_full):
    """
    Interpolate knife-edge sweep to find X at 16% and 84% of P_full.
    Returns (x_16, x_84) or (None, None).
    """
    if P_full < 1e-12 or len(x_arr) < 3:
        return None, None
    p_norm = p_arr / P_full
    order = np.argsort(x_arr)
    x_s, p_s = x_arr[order], p_norm[order]
    try:
        f = interp1d(p_s, x_s, kind="linear", bounds_error=False,
                     fill_value="extrapolate")
        return float(f(0.16)), float(f(0.84))
    except Exception:
        return None, None


def compute_beam_radius(x_16, x_84):
    """Returns beam radius in µm given clip positions in mm."""
    d_clip = abs(x_84 - x_16)
    w_mm = d_clip / np.sqrt(2)
    return w_mm * 1000.0  # µm


def fit_caustic(z_um, w_um, wavelength_um=2.94):
    """
    Fit beam caustic to measured w(z) data.
    Returns dict with w0, z0, M2, z_R, uncertainties, and fit curve.
    """
    if len(z_um) < 3:
        return None

    z_data = np.array(z_um)
    w_data = np.array(w_um)

    try:
        p0 = [w_data.min(), z_data[np.argmin(w_data)], 1.2]
        popt, pcov = curve_fit(
            lambda z, w0, z0, M2: beam_caustic(z, w0, z0, M2, wavelength_um),
            z_data, w_data, p0=p0
        )
        w0, z0, M2 = abs(popt[0]), popt[1], abs(popt[2])
        perr = np.sqrt(np.diag(pcov))
        z_R = (np.pi * w0**2) / (M2 * wavelength_um)

        z_fine = np.linspace(z_data.min(), z_data.max(), 300)
        w_fine = beam_caustic(z_fine, w0, z0, M2, wavelength_um)

        return {
            "w0": w0, "w0_err": perr[0],
            "z0": z0, "z0_err": perr[1],
            "M2": M2, "M2_err": perr[2],
            "z_R": z_R,
            "wavelength": wavelength_um,
            "z_data": z_data, "w_data": w_data,
            "z_fit": z_fine, "w_fit": w_fine,
        }
    except RuntimeError:
        return None
