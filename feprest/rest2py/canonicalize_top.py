#!/usr/bin/python
# Copyright 2018-2023 Shun Sakuraba
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import argparse
import sys
import copy

# I love this in C++.
def next_permutation(ls):
    if len(ls) <= 1:
        return (False, ls)
    i = len(ls) - 1
    while True:
        j = i
        i -= 1
        if ls[i] < ls[j]:
            k = len(ls) - 1
            while not (ls[i] < ls[k]):
                k -= 1
            tmp = ls[i]
            ls[i] = ls[k]
            ls[k] = tmp
            ls[j:] = ls[j:][::-1]
            return (True, ls)
        if i == 0:
            ls = ls[::-1]
            return (False, ls)

# based on gromacs 5.1.3+ behaviour, best match first.
# (see https://redmine.gromacs.org/issues/1901 )
def find_matching_dihedral(dihtype, ai, aj, ak, al, dfun):
    origindex = [ai, aj, ak, al]
    for nmatch in [4,3,2,1,0]:
        wildcards = [i >= nmatch for i in range(4)]
        while True:
            for fwddir in [True, False]:
                if fwddir:
                    ixs = copy.deepcopy(origindex)
                else:
                    ixs = origindex[::-1]
                for i in range(4):
                    if wildcards[i]:
                        ixs[i] = "X"
                key = tuple(ixs + [dfun])
                if key in dihtype:
                    return dihtype[key]
            (ret, wildcards) = next_permutation(wildcards)
            if not ret:
                break
    raise RuntimeError("Could not find dihedral for %s-%s-%s-%s-%d" % (ai, aj, ak, al, dfun))

def find_matching_bond(bondtype_params, ai, aj, fun):
    for key in [(ai, aj, fun), (aj, ai, fun)]:
        if key in bondtype_params:
            return bondtype_params[key]
    raise RuntimeError("Could not find bond for %s-%s-%d" % ai, aj, fun)
        

def find_matching_angle(angletype_params, ai, aj, ak, fun):
    for key in [(ai, aj, ak, fun), (ak, aj, ai, fun)]:
        if key in angletype_params:
            return angletype_params[key]
    raise RuntimeError("Could not find angle for %s-%s-%d" % ai, aj, ak, fun)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""Removes [ bondtypes ] [ angletypes ] [ dihedraltypes ] from the topology file.

    Input topology must be preprocessed topology (generated by gmx grompp -pp).
    """)
    parser.add_argument('topology', action='store', type=str, 
                        help='Topology file (must be preprocessed and underlined)')
    parser.add_argument('output', action='store', type=str, 
                        help='Topology file output')
    parser.add_argument('--ignore-noninteger-periodicity', dest='ignore_noninteger_periodicity', action='store_true',
                        help='Some dihedral parameters require periodicity sections, which should typically be integer. Instead of aborting on float, this option ignores non-integer input.')

    args = parser.parse_args()



    with open(args.topology) as fh, open(args.output, "w") as ofh:
        bondtype_of_atomtype = {} # confusing but this is atom->bondatom mapping
        atomtype_info = {}
        dummy_atomtypes = set()
        dihtype = {}
        angtype = {}
        bondtype_params = {}
        molecule = None
        sectiontype = None
        coulombrule = None
        residues = None
        atomnames = None

        def print_parameters(params, n_nonfep, n_fep, intind, atoms, funcno):
            if len(params) not in [n_nonfep, n_nonfep + n_fep]:
                directive = [None, None, "bonds", "angles", "dihedrals"][len(atoms)]
                raise RuntimeError("Number of args in %s: expected %d or %d, but was %d (%s:%d)" %
                                   (directive,
                                    n_nonfep, n_nonfep + n_fep, len(params),
                                    "-".join([str(x) for x in atoms]), funcno))
            for (i, v) in enumerate(params):
                if i in intind:
                    try:
                        v = int(v)
                    except ValueError:
                        print(params)
                        if args.ignore_noninteger_periodicity:
                            vf = float(v)
                            vi = int(vf)
                            if abs(vi - vf) > 1e-2:
                                raise RuntimeError("Periodicity should be integer but was %f" % vf)
                            v = vi
                        else:
                            raise RuntimeError("Periodicity should be integer")
                    fmts = "%1d" % v
                else:
                    v = float(v)
                    fmts = "%16.8e" % v
                ofh.write(" %s" % fmts)
            ofh.write("\n")
                
        for lraw in fh:
            ltmp = lraw.split(';', 1)
            if len(ltmp) == 1:
                l = ltmp[0]
                comment = ""
            else:
                l = ltmp[0]
                comment = ";" + ltmp[1]
            l = l.strip()
            ls = l.split()
            if l.startswith('#'):
                sys.stderr.write("The topology file is not preprocessed")
                sys.exit(1)
            if l.startswith('['):
                sectiontype = ls[1]
                if sectiontype not in ["bondtypes", "angletypes", "dihedraltypes"]:
                    ofh.write(lraw)
                continue

            # blank line
            if len(ls) == 0:
                ofh.write(lraw)
                continue

            if sectiontype is None:
                pass
            elif sectiontype == 'defaults':
                pass
            elif sectiontype == 'atomtypes':
                if len(ls) < 6:
                    raise RuntimeError("Atomtype contains < 6 fields")
                # here everything is mess but toppush.cpp is actually super mess 
                if len(ls[5]) == 1 and ls[5].isalpha():
                    # "If field 5 is a single char we have both."
                    have_bonded_type = True
                    have_atomic_number = True
                elif len(ls[3]) == 1 and ls[3].isalpha():
                    # "If field 3 (starting from 0) is a single char, 
                    #  we have neither bonded_type or atomic numbers."
                    have_bonded_type = False
                    have_atomic_number = False
                else:
                    # "If field 4 is a single char we check field 1. If this begins with
                    #  an alphabetical character we have bonded types, otherwise atomic numbers.""
                    # --> After GROMACS resolved issue 4120, the logic was changed.
                    # "Attempt parsing field 1 to integer. If conversion fails, we do not have an atomic number but a bonded type.
                    # Unfortunately, int() in Python is more permissive (e.g. "3_10" is 310), so I change this part to be more restrictive
                    have_atomic_number = all((c.isdigit() for c in ls[1]))
                    have_bonded_type = not have_atomic_number

                atomtype = ls[0]
                (mass, charge, particle, sigc6, epsc12) = ls[1 + int(have_bonded_type) + int(have_atomic_number):]

                if have_bonded_type:
                    bondtype = ls[1]
                    if all((c.isdigit() for c in ls[1])):
                        sys.stderr.write("""
                        [ atomtypes ] contains bondtype "%s", but the bondtype consists of all digits.
                        This is considered invalid atomtype in GROMACS.
                        """ % atomtype)
                    raise RuntimeError("Invalid force field")
                else:
                    bondtype = atomtype
                if have_atomic_number:
                    atomic_ix = 1 + int(have_bonded_type)
                    atomic_number = int(ls[atomic_ix])
                else:
                    atomic_number = 0 # ??
                    
                # store this because we use in [ atoms ] section
                bondtype_of_atomtype[atomtype] = bondtype

                mass = float(mass)
                charge = float(charge)
                sigc6 = float(sigc6)
                epsc12 = float(epsc12)
                is_dummy = epsc12 == 0.

                atomtype_info[atomtype] = (charge, mass)
                if is_dummy:
                    dummy_atomtypes.add(atomtype)

            elif sectiontype == 'dihedraltypes':
                (ai, aj, ak, al) = ls[0:4]
                dihfun = int(ls[4])
                values = ls[5:]
                key = (ai, aj, ak, al, dihfun)
                if dihfun == 9:
                    # allows multiple dihedraltype for fn = 9
                    if key not in dihtype:
                        dihtype[key] = []
                    dihtype[key].append(values)
                else:
                    if key in dihtype:
                        for (i, e) in enumerate(dihtype[key]):
                            d = abs(float(values[i]) - float(e))
                            if d > 1e-20:
                                raise RuntimeError("Multiple dihedral for dihfun = %d, %s-%s-%s-%s"
                                                   % (dihfun, ai, aj, ak, al))
                    else:
                        dihtype[key] = values
                continue # suppress printing, we won't use dihedraltypes.
            elif sectiontype == 'angletypes':
                (ai, aj, ak) = ls[0:3]
                anglefun = int(ls[3])
                values = ls[4:]
                key = (ai, aj, ak, anglefun)
                angtype[key] = values
                continue # suppress printing
            elif sectiontype == 'bondtypes':
                (ai, aj) = ls[0:2]
                bondfun = int(ls[2])
                values = ls[3:]
                key = (ai, aj, bondfun)
                bondtype_params[key] = values
                continue # suppress printing
            elif sectiontype == 'moleculetype':
                molecule = ls[0]
                # These None are sentinels for 1-origin access
                bondtype_list = [None]
                scaled = [None]
                atomnames = []
                residues = []
            elif sectiontype == 'atoms':
                aindex = int(ls[0])
                atomtype = ls[1]
                bondtype_list.append(bondtype_of_atomtype[atomtype])

                # charge & mass is optional parameters, oof...
                charge, mass = atomtype_info[atomtype]
                if len(ls) > 6:
                    charge = float(ls[6])
                if len(ls) > 7:
                    mass = float(ls[7])

                if len(ls) > 8:
                    atomtypeB = ls[8]
                    (chargeB, massB) = atomtype_info[atomtypeB]
                    fep = True
                else:
                    fep = False
                    chargeB = 0.
                    massB = 0.
                    atomtypeB = None
                if len(ls) > 9:
                    chargeB = float(ls[9])
                if len(ls) > 10:
                    massB = float(ls[10])

                _resnr = ls[2]
                resid = ls[3]
                residues.append(resid)
                atomname = ls[4]
                atomnames.append(atomname)
                
                ofh.write("%5d %4s %4s %4s %4s %5s %16.8e %16.8e" % (aindex, atomtype, ls[2], ls[3], ls[4], ls[5], charge, mass))
                if fep:
                    ofh.write(" %4s %16.8e %16.8e%s\n" % (atomtypeB, chargeB, massB, comment.rstrip()))
                else:
                    ofh.write(" %s\n" % comment.rstrip())
                continue
            elif sectiontype == 'dihedrals':
                dihfun = int(ls[4])
                values = ls[5:]
                (ai, aj, ak, al) = [int(x) for x in ls[0:4]]
                if len(ls) == 5:
                    # must load dihedral table
                    (ti, tj, tk, tl) = [bondtype_list[x] for x in [ai, aj, ak, al]]
                    ofh.write("; parameters for %s-%s-%s-%s, fn=%d\n" % (ti, tj, tk, tl, dihfun))

                    params_tmp = find_matching_dihedral(dihtype, ti, tj, tk, tl, dihfun)
                    matched = True
                else:
                    params_tmp = ls[5:]
                    matched = False
                if dihfun == 9 and matched:
                    params_list = params_tmp
                else:
                    params_list = [params_tmp]

                for params in params_list:
                    ofh.write("%5d %5d %5d %5d %2d" % (ai, aj, ak, al, dihfun))
                    # This table slightly eases the mess for dihfun / fep
                    (n_nonfep, n_fep, intind) = {
                        1: (3, 2, [2]),
                        2: (2, 2, []),
                        3: (6, 6, []),
                        4: (3, 2, [2]),
                        5: (4, 4, []),
                        8: (2, 1, [0]),
                        9: (3, 2, [2]),
                        10: (1, 0, []),
                        11: (4, 0, [])
                    }[dihfun]
                    print_parameters(params, n_nonfep, n_fep, intind, [ai, aj, ak, al], dihfun)
                continue
            elif sectiontype == 'angles':
                angfun = int(ls[3])
                (ai, aj, ak) = [int(x) for x in ls[0:3]]
                if len(ls) == 4:
                    # must load angle table
                    (ti, tj, tk) = [bondtype_list[x] for x in [ai, aj, ak]]
                    ofh.write("; parameters for %s-%s-%s, fn=%d\n" % (ti, tj, tk, angfun))

                    params = find_matching_angle(angtype, ti, tj, tk, angfun)
                    matched = True
                else:
                    params = ls[4:]
                    matched = False
                ofh.write("%5d %5d %5d %2d" % (ai, aj, ak, angfun))
                # This table slightly eases the mess for dihfun / fep
                (n_nonfep, n_fep, intind) = {
                    1: (2, 2, []),
                    2: (2, 2, []),
                    3: (3, 0, []),
                    4: (4, 0, []),
                    5: (4, 4, []),
                    6: (6, 0, []),
                    8: (2, 1, []),
                    10: (2, 0, []),
                }[angfun]
                print_parameters(params, n_nonfep, n_fep, intind, [ai, aj, ak], angfun)
                continue

            elif sectiontype == 'bonds':
                bondfun = int(ls[2])
                (ai, aj) = [int(x) for x in ls[0:2]]
                if len(ls) == 3:
                    # must load angle table
                    (ti, tj) = [bondtype_list[x] for x in [ai, aj]]
                    ofh.write("; parameters for %s-%s, fn=%d\n" % (ti, tj, bondfun))

                    params = find_matching_bond(bondtype_params, ti, tj, bondfun)
                    matched = True
                else:
                    params = ls[3:]
                    matched = False
                ofh.write("%5d %5d %2d" % (ai, aj, bondfun))
                # This table slightly eases the mess for dihfun / fep
                (n_nonfep, n_fep, intind) = {
                    1: (2, 2, []),
                    2: (2, 2, []),
                    3: (2, 2, []),
                    4: (3, 0, []),
                    5: (0, 0, []),
                    6: (2, 2, []),
                    7: (2, 0, []),
                    8: (2, 1, [0]),
                    9: (2, 1, [0]),
                    10: (4, 4, [])
                }[bondfun]
                print_parameters(params, n_nonfep, n_fep, intind, [ai, aj], bondfun)
                continue

            # With a few exceptions, we just print as-is
            ofh.write(lraw)






