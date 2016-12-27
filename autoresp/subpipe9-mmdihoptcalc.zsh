#!/usr/bin/zsh

# Assumes subpipe6-optdih is done
if [[ -z $4 ]]; then
    echo "Usage: $0 (base-only structure) (base constraint) (dihedral) (atomtype) (resname)" 1>&2
    echo "Example: $0 inosine.pdb constraint-rna-opt2.txt O4\'-C1\'-N9-C8 CP INO" 1>&2
    echo "The final atom in dihedral angle specification will be given the new atom type"
    exit 1
fi

echo TODO transplant the program to Laurel
exit 1

basedir=${0:h}
basestructure=$1
baseconstraint=$basedir/$2
dihedral=$3
newatomtype=$4
resname=$5

basestructurename=${basestructure:r}
basename=${basestructure:t:r}

dihoptprep=$basestructurename.dihopt.prep
dihoptfrcmod=$basestructurename.dihopt.frcmod
external_param=$basestructurename.ext.parameter
ambtop=$basestructurename.dihopt.ambtop
ambcrd=$basestructurename.dihopt.crd

pbfile=${basedir}/sander_pb.in

if [[ ! ( -e $dihoptprep && -e $dihoptfrcmod && -e $external_param && -e $ambtop && -e $ambcrd ) ]]; then
    echo "Missing required files (should be generated at subpie6-optdih.zsh)" 2>&1
    exit 1
fi

if [[ -z $CHARGE ]]; then
    CHARGE=0
fi

source $basedir/defaults.zsh

# generate pdb
dihoptpdb=$basestructurename.dihopt.pdb
$AMBPDB -p $ambtop < $ambcrd > $dihoptpdb

# With current protocol mm atom names shall match gaussian atom ordering. Thus it is not a bug (at least AFAIK) duplicated lines
grep '^ATOM' $dihoptpdb | cut -c 13-16 | tr -d ' ' > $basestructurename.mm.atoms

grep '^ATOM' $dihoptpdb | cut -c 13-16 | tr -d ' ' > $basestructurename.gaussian.atoms

natom=$(wc -l < $basestructurename.gaussian.atoms)
{
    echo $basestructurename.dihopt.ambtop
    echo $natom
    cat $basestructurename.mm.atoms
    cat $basestructurename.gaussian.atoms
} > $external_param


# generate "External" Gaussian inputs
mmoptpre=$basestructurename.optmmpre.gau
$OPENBABEL $dihoptpdb -ogzmat -xk "#OPT(ModRedundant,MaxCyc=9999) External=\"../../external_sander.py inosine.ext.parameter\"" $mmoptpre
sed -i "/^0 /c $CHARGE 1" $mmoptpre

for i in {0..35}; do
    mmopt=$basestructurename.optmm.$i.gau
    constr=$basestructurename.cons$i.txt # this is generated by subpipe6-optdih
    python $basedir/mod-zmatrix.py --redundant $mmoptpre $dihoptpdb $constr > $mmopt
    sed -i "1i %chk=${mmopt:r}.chk" $mmopt
done

# works only with the g03 (g09 series has a serious bug that ignores ModRedundant)
# TODO: move back to laurel
for i in {0..35}; do
    mmopt=$basestructurename.optmm.$i.gau
    NOWAIT=y subg09='~/subg09local' EXTRA=$external_param,$ambtop,$pbfile CMD="source /opt/intel/compilers_and_libraries_2016.2.181/linux/bin/compilervars.sh intel64; export AMBERHOME=/local/apl/pg/amber16-bf3" GMAJOR=03 GMINOR=e01 zsh $basedir/g09rccs.zsh $basename $mmopt
    sleep 300
done
