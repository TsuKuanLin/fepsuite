# function optimization
# determines both angle and coefficients

import sys
import numpy as np
import cma
import math
import copy

Nfit = 4

def basefuncs(x, n, p):
    return 1.0 + math.cos((n * x - p) * math.pi / 180.0)
vecbases = np.vectorize(basefuncs)

def getlinear(angles, delta_es, weights, phases):
    allevals = []
    allevals.append(np.array([1.0] * len(angles)))
    for i in range(len(phases)):
        n = i + 1
        p = phases[i]
        bases = vecbases(angles, n, p)
        allevals.append(bases)
    allevals = np.array(allevals)
    sqweights = np.sqrt(weights)
    weighted_delta = copy.deepcopy(delta_es)
    for j in range(len(sqweights)):
        allevals[:, j] *= sqweights[j]
        weighted_delta[j] *= sqweights[j]
    (x, residuals, rank, sing) = np.linalg.lstsq(allevals.T, weighted_delta)
    residsum = np.linalg.norm(residuals)
    return (residsum, x)

def test_linear():
    angles = np.array(range(36)) * 10.0
    weights = [1.0] * 36
    delta = (100 + 
             0.9656 * vecbases(angles, 1,  68.79) +
             1.0740 * vecbases(angles, 2,  15.64) +
             0.4575 * vecbases(angles, 3, 171.58) +
             0.3092 * vecbases(angles, 4,  19.09))
    print getlinear(angles, delta, weights, [68.79, 15.64, 171.58, 19.09])
    print getlinear(angles, delta, weights, [70, 15, 170, 19])

test_linear()

if len(sys.argv) <= 3:
    print >> sys.stderr, "Usage: %s (qm) (mm) (weight)" % sys.argv[0]
    sys.exit(1)

qms = file(sys.argv[1]).readlines()
mms = file(sys.argv[2]).readlines()
weights = file(sys.argv[3]).readlines()

qms = [float(x.strip()) for x in qms]
mms = [float(x.strip()) for x in mms]
weights = [float(x.strip()) for x in weights]

qms = np.array(qms)
qmsmin = np.min(qms)
qms -= qmsmin

mms = np.array(mms)
mmsmin = np.min(mms)
mms -= mmsmin

deltaes = qms - mms

# assumes equal angle partition
dangle = 360.0 / len(deltaes)
angles = np.array(range(len(deltaes))) * dangle

# find initial guess of phases
phaseguess = np.array([0.0] * Nfit)
for i in range(Nfit):
    k = i + 1
    bestguess = 0.
    bestscore = 1e+9
    for a in angles:
        if a >= (359.9 / k):
            break
        phaseguess[i] = a
        (sc, _coeffs) = getlinear(angles, deltaes, weights, phaseguess)
        print i, a, sc
        if sc < bestscore:
            bestscore = sc
            bestguess = a
    phaseguess[i] = bestguess

def ffun(phases):
    (r, _x) = getlinear(angles, deltaes, weights, phases)
    return r
cmaret = cma.fmin(ffun, phaseguess, dangle)

print "Initial guess: ", phaseguess
print "Final result: ", cmaret[0]



        
