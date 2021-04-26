import numpy as np
from scipy.integrate import quad
from numba import jit, float64
import os.path
from pathlib import Path

import vega


@jit(nopython=True)
def sinc(x):
    return np.sin(x)/x


def _tracer_bias_beta(params, name):
    """Get the bias and beta values for a tracer

    Parameters
    ----------
    params : dict
        Computation parameters
    name : string
        Name of tracer

    Returns
    -------
    float, float
        bias, beta
    """
    growth_rate = params.get("growth_rate", 1.)

    bias = params.get('bias_' + name, None)
    bias_eta = params.get('bias_eta_' + name, None)
    beta = params.get('beta_' + name, None)

    err_msg = ("For each tracer, you need to specify two of these three:"
               " (bias, bias_eta, beta)."
               " If all three are given, we use bias and beta.")

    if bias is None:
        assert bias_eta is not None and beta is not None, err_msg
        bias = bias_eta * growth_rate / beta

    if bias_eta is None:
        assert bias is not None and beta is not None, err_msg

    if beta is None:
        assert bias is not None and bias_eta is not None, err_msg
        beta = bias_eta * growth_rate / bias

    return bias, beta


def bias_beta(params, tracer1, tracer2):
    """Get bias and beta values for the two tracers

    Parameters
    ----------
    params : dict
        Computation parameters
    tracer1 : dict
        Config of tracer 1
    tracer2 : dict
        Config of tracer 2

    Returns
    -------
    float, float, float, float
        bias_1, beta_1, bias_2, beta_2
    """
    bias1, beta1 = _tracer_bias_beta(params, tracer1['name'])
    if tracer1['name'] == tracer2['name']:
        bias2, beta2 = bias1, beta1
    else:
        bias2, beta2 = _tracer_bias_beta(params, tracer2['name'])

    return bias1, beta1, bias2, beta2


def ap_at(pars):
    if pars['peak'] or pars['full-shape']:
        return pars['ap'], pars['at']

    if pars['smooth_scaling']:
        return pars['ap_sb'], pars['at_sb']

    return 1., 1.


def ap_at_custom(pars):
    if pars['peak'] or pars['full-shape']:
        ap = pars['ap']
        at = pars['at']
    elif pars['smooth_scaling']:
        phi = pars['phi_smooth']
        gamma = pars['gamma_smooth']
        ap = 2. * gamma / (1. + phi)
        at = phi * ap
    else:
        ap = 1.
        at = 1.

    return ap, at


def phi_gamma(pars):
    if pars['peak'] or pars['full-shape']:
        phi = pars['phi']
        gamma = pars['gamma']
    elif pars['smooth_scaling']:
        phi = pars['phi_smooth']
        gamma = pars['gamma_smooth']
    else:
        phi = 1.
        gamma = 1.

    ap = gamma / np.sqrt(phi)
    at = gamma * np.sqrt(phi)
    return ap, at


def aiso_epsilon(pars):
    if pars['peak'] or pars['full-shape']:
        aiso = pars['aiso']
        eps = pars['1+epsilon']
        ap = aiso*eps*eps
        at = aiso/eps
    else:
        ap = 1.
        at = 1.
    return ap, at


def convert_instance_to_dictionary(inst):
    dic = dict((name, getattr(inst, name)) for name in dir(inst) if not name.startswith('__'))
    return dic


@jit(float64(float64, float64, float64))
def hubble(z, Omega_m, Omega_de):
    """Hubble parameter in LCDM + curvature
    No H0/radiation/neutrinos

    Parameters
    ----------
    z : float
        Redshift
    Omega_m : float
        Matter fraction at z = 0
    Omega_de : float
        Dark Energy fraction at z = 0

    Returns
    -------
    float
        Hubble parameter
    """
    Omega_k = 1 - Omega_m - Omega_de
    e_z = np.sqrt(Omega_m * (1 + z)**3 + Omega_de + Omega_k * (1 + z)**2)
    return e_z


@jit(float64(float64, float64, float64))
def growth_integrand(a, Omega_m, Omega_de):
    """Integrand for the growth factor

    Parameters
    ----------
    a : float
        Scale factor
    Omega_m : float
        Matter fraction at z = 0
    Omega_de : float
        Dark Energy fraction at z = 0

    Returns
    -------
    float
        Growth integrand
    """
    z = 1 / a - 1
    inv_int = (a * hubble(z, Omega_m, Omega_de))**3
    return 1./inv_int


def growth_function(z, Omega_m, Omega_de):
    """Compute growth factor at redshift z

    Parameters
    ----------
    z : float
        redshift
    Omega_m : float
        Matter fraction at z = 0
    Omega_de : float
        Dark Energy fraction at z = 0
    """
    a = 1 / (1 + z)
    args = (Omega_m, Omega_de)
    growth_int = quad(growth_integrand, 0, a, args=args)[0]
    hubble_par = hubble(z, Omega_m, Omega_de)
    return 5./2. * Omega_m * hubble_par * growth_int


def find_file(path):
    """ Find files on the system.

    Checks if it's an absolute path or something inside vega,
    and returns a proper path.

    Relative paths are checked from the vega main path,
    vega/models and tests

    Parameters
    ----------
    path : string
        Input path. Can be absolute or relative to vega
    """
    input_path = Path(os.path.expandvars(path))

    # First check if it's an absolute path
    if input_path.is_file():
        return input_path

    # Get the vega path and check inside vega (this returns vega/vega)
    vega_path = Path(os.path.dirname(vega.__file__))

    # Check if it's a model
    model = vega_path / 'models' / input_path
    if model.is_file():
        return model

    # Check if it's something used for tests
    test = vega_path.parents[0] / 'tests' / input_path
    if test.is_file():
        return test

    # Check from the main vega folder
    in_vega = vega_path.parents[0] / input_path
    if in_vega.is_file():
        return in_vega

    raise RuntimeError('The path/file does not exists: ', input_path)
