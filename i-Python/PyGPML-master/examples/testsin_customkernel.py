import numpy as np
from scipy import optimize as sopt
from scipy import io as sio
import pylab as pl

# Adds the GP code directory to the system path
# so we can call the library from this subdir.
import addpath
import gaussian_process as gp

# Generate some test data
ff = 10
f = lambda x: np.sin(2*np.pi*ff*x) + np.sin(2*np.pi*(ff+3)*x)/3.
Fs = 150.0
Ts = 1.0/Fs
x = np.matrix(np.arange(0,1,Ts)).T
xt = np.matrix(np.arange(0,2,Ts)).T
y = np.matrix(f(x).ravel()).T
dy = 0.5 + 1.e-1 * np.random.random(y.shape)
noise = np.random.normal(0, dy)
y += noise

def rqkernel(hyp, x=None, z=None, diag=False):
    """
    Implements a rational-quadratic kernel:
    k(x,x') = hscale^2 * (1 + (x-x')^2/(alpha*lamb^2))^{-alpha}
    """
    hscale = np.exp(hyp[0])
    alpha = np.exp(hyp[1])
    lamb = np.exp(hyp[2])
    if diag:
        K = np.zeros((x.shape[0],1))
    else:
        if x is z:
            K = gp.core.sq_dist(x.T/lamb**2)
        else:
            K = gp.core.sq_dist(x.T/lamb**2, z.T/lamb**2)
    K = hscale**2 * np.power(1 + K/alpha, -alpha)
    return K

def perkernel(hyp, x=None, z=None, diag=False):
    """
    Implements a periodic kernel:
    k(x,x') = sigma^2 * exp(-2/ell^2 * sin^2(pi*|x-x'|/per))
    """
    sigma = np.exp(hyp[0])
    ell = np.exp(hyp[1])
    per = np.exp(hyp[2])
    if diag:
        K = np.zeros((x.shape[0],1))
    else:
        if x is z:
            K = gp.core.sq_dist(x.T)
        else:
            K = gp.core.sq_dist(x.T, z.T)
    K = np.sqrt(K)  # need the absolute distance, not squared
    K = sigma**2 * np.exp(-2/ell**2 * np.power(np.sin(np.pi*K/per), 2))
    return K

def wrapperkernel(hyp, x=None, z=None, diag=False):
    """
    This is a wrapper kernel that multiplies an RQ kernel
    with a periodic one.
    """
    hyp1, hyp2, hyp3 = hyp[0:3], hyp[3:7], hyp[7:11]
    Kper1 = perkernel(hyp1, x, z, diag)
    Kper2 = perkernel(hyp1, x, z, diag)
    Krq = rqkernel(hyp2, x, z, diag)
    # You can also call the built-in kernels by doing
    # Ksomething = gp.kernels.somekernel(**args)
    return np.multiply(Kper1+Kper2, Krq)

# Initialize some params
negLogML = np.inf
hypInit = None
nItr = 1

# Define core functions
likFunc = gp.likelihoods.gaussian
meanFunc = gp.means.zero
infFunc = gp.inferences.exact
# covFunc = rqkernel
covFunc = wrapperkernel

# Set the optimizer types and options
# l1 is for the random starts, l2 does more
# optimization for the best one from l1.
l1Optimizer = 'COBYLA'
l1Options = {'maxiter':100}
l2Optimizer = 'L-BFGS-B'
l2Options = {'maxiter':100}

# Noise std. deviation
sn = 1.0

# Initialize hyperparams
# hypGuess = np.log([0.1, 0.1, 0.1])  # for the RQ kernel
# hypGuess = np.log([0.05, 0.1, 1.0])  # for the periodic kernel
hypGuess = {
    'cov': np.log([0.05, 0.1, 1.0, 
                   0.05, 0.1, 1.0, 
                   0.1, 0.1, 0.1]),  # for the periodic-RQ kernel
    'lik': np.atleast_1d(np.log(sn)),
    'mean': np.array([])
    }
# Optimize the guessed hyperparams
hypGP = gp.GaussianProcess(hyp=hypGuess, inf=infFunc, mean=meanFunc, cov=covFunc, 
                           lik=likFunc, xtrain=x, ytrain=y, xtest=xt)
# Random starts
for itr in range(nItr):
    # Start over
    hypGP.hyp = hypGuess
    # Optimize the guessed hyperparams
    try:
        hypGP.train(l1Optimizer, l1Options)
    except Exception as e:
        print "Iteration: ", itr, "FAILED"
        print "\t", e
        continue
    # Best random initialization
    if hypGP.nlml < negLogML:
        hypInit = hypGP.hyp
        negLogML = hypGP.nlml
    print "Iteration: ", itr, hypGP.nlml
# Give the GP object the proper params
hypGP.hyp = hypInit
hypGP.nlml = negLogML
# Optimize the best hyperparams even more
hypGP.hyp, hypGP.nlml = hypGP.train(method=l2Optimizer, options=l2Options)
print "Final hyperparams likelihood: ", negLogML
print "Noise parameter: ", np.exp(hypGP.hyp['lik'])
print "Reoptimized: ", hypGP.nlml
print np.exp(hypGP.hyp['cov'])

# Do the extrapolation
prediction = hypGP.predict()
mean = prediction['ymu']
sigma2 = prediction['ys2']

# Plot the stuff
pl.plot(x, y, 'b', label=u'Training Data')
pl.plot(xt[x.size:], f(xt)[x.size:], 'k', label=u'Test Data')
pl.plot(xt, mean, 'r', label=u'SM Prediction')
sigma = np.power(sigma2, 0.5)
fillx = np.concatenate([np.array(xt.ravel()).ravel(), 
                        np.array(xt.ravel()).ravel()[::-1]])
filly = np.concatenate([(np.array(mean.ravel()).ravel() - 1.9600 * 
                         np.array(sigma.ravel()).ravel()),
                        (np.array(mean.ravel()).ravel() + 1.9600 * 
                         np.array(sigma.ravel()).ravel())[::-1]])
pl.fill(fillx, filly, alpha=.5, fc='0.5', ec='None', 
        label='95% confidence interval')
pl.legend()
pl.show()
