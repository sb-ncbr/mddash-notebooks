# AMBER Protein MD Setup — Design Spec

## Goal
Create `amber-protein-setup.ipynb`, an AMBER counterpart to `protein-setup.ipynb`.
Follow the same notebook philosophy (parameter block, file-template generation,
wrapper execution, inline plotting) but use an authentically AMBER workflow.

## Scope
- One new file: `amber-protein-setup.ipynb`
- One new module: `amber_wrapper.py` (no simulation logic, thin subprocess wrapper)

## Out of Scope
- Analysis steps (there is already `protein-analysis.ipynb`)
- Ligand parameterization (`antechamber` usage noted in wrapper for future extension)
- Constant-pH or advanced enhanced-sampling methods

---

## 1. `amber_wrapper.py`

A thin Python wrapper around AmberTools/PMEMD binaries already present in `PATH`.
No simulation logic: the wrapper validates types, builds CLI arguments, runs the binary,
and returns stdout / stderr.

### Design Philosophy
Mirror `import gromacs as gmx` from the existing notebook:
```python
import amber_wrapper as amb
amb.tleap(f="setup.leap.in")
amb.pmemd(i="min.mdin", o="min.mdout", p="system.prmtop", c="system.rst7", O=True)
amb.cpptraj(p="system.prmtop", input="trajin mdcrd.nc\nrmsd first @CA")
```

### Binaries Covered
| Function | AMBER Binary | Purpose |
|----------|--------------|---------|
| `tleap` | `tleap` | System preparation (force field, solvation, ions) |
| `pmemd` | `pmemd` / `pmemd.cuda` * | Minimization, heating, equilibration, production |
| `sander` | `sander` | Fallback CPU engine |
| `cpptraj` | `cpptraj` | Trajectory manipulation, energy extraction |
| `pdb4amber` | `pdb4amber` | Clean incoming PDBs |
| `ambpdb` | `ambpdb` | Generate PDB from prmtop for NGLView |
| `parmed` | `parmed` | Topology inspection / editing |
| `antechamber` | `antechamber` | Small-molecule parameterization (future use) |

\* `pmemd.cuda` should be selectable via a `cuda=True` flag.

### Type Support
Every CLI flag becomes a typed keyword argument:
- `-f str` → `f: str`
- `-i str` → `i: str`
- `-O` (boolean switch) → `O: bool = False`
- `ntmin` (0 | 1 | 2 | 3) → `ntmin: Literal[0, 1, 2, 3]`

### Error Handling
Use `subprocess.run(..., check=True, capture_output=True, text=True)`.
Non-zero exit raises `subprocess.CalledProcessError` with `.stderr` attached so
Amber error messages surface directly in notebook cells.

---

## 2. `amber-protein-setup.ipynb`

Follows the same high-level cell structure as `protein-setup.ipynb` but with an
AMBER-specific pipeline.

### Cell Outline

#### 1. Parameter Block
```python
name = "protein"
nanoseconds = 0.05
nsteps = int(nanoseconds * 500000)  # 2 fs timestep
nmin = 5000          # minimization cycles per stage
nheat = 25000        # heating steps (50 ps)
nnvt = 50000         # NVT equilibration steps (100 ps)
nnpt = 125000        # NPT equilibration steps (250 ps)
temp0 = 300.0        # target temperature (K)
salt_mM = 150.0      # salt concentration
buffer = 12.0        # solvation buffer (angstroms)
```

#### 2. Imports
```python
import amber_wrapper as amb
import nglview as nv
import mdtraj as md
import numpy as np
import matplotlib.pyplot as plt
```

#### 3. Visual Inspection
```python
nv.show_file("input.pdb")
```

#### 4. PDB Preparation (`pdb4amber`)
Clean incoming PDB: standardize residue names, handle disulfides, remove CONECT.
```python
amb.pdb4amber(input="input.pdb", output=f"{name}_clean.pdb", reduce=True)
```

#### 5. System Preparation (`tleap`)
Generate `tleap.in` via Python f-string:
- `source leaprc.protein.ff19SB`
- `source leaprc.water.opc`
- `protein = loadpdb {name}_clean.pdb`
- `check protein` (catch missing parameters early)
- `saveamberparm protein {name}_gas.prmtop {name}_gas.rst7`
- `addions protein Na+ 0` (neutralize; adds Na+ for negative net charge)
- `addions protein Cl- 0` (neutralize; adds Cl- for positive net charge)
- `solvateoct protein OPCBOX {buffer}`
- `addionsrand protein Na+ X Cl- X` (salt buffer; count from tleap water count)
- `saveamberparm protein {name}_solv.prmtop {name}_solv.rst7`

**Salt calculation:** After solvation, parse the tleap log for the number of added water
molecules (`N_wat`). Then:
```python
n_ion_pairs = int(0.0187 * salt_mM * N_wat)
```
(Rounded to nearest integer; one Na+ and one Cl- per pair.)

Execute:
```python
amb.tleap(f=f"{name}.leap.in")
```

#### 6. Energy Minimization — Stage 1 (Restrained)
Write `min1.mdin`:
```fortran
&cntrl
  imin=1, ncyc={nmin//2}, maxcyc={nmin}, ntmin=1,
  ntb=1, cut=10.0,
  ntr=1,
  restraint_wt=2.0,
  restraintmask=":@CA,C,N",
  ntpr=50,
/
```
```python
amb.pmemd(i="min1.mdin", o="min1.mdout", p=f"{name}_solv.prmtop",
          c=f"{name}_solv.rst7", r="min1.rst7", ref=f"{name}_solv.rst7", O=True)
```

#### 7. Energy Minimization — Stage 2 (Unrestrained)
Write `min2.mdin`:
```fortran
&cntrl
  imin=1, ncyc={nmin//2}, maxcyc={nmin}, ntmin=1,
  ntb=1, cut=10.0,
  ntr=0,
  ntpr=50,
/
```
```python
amb.pmemd(i="min2.mdin", o="min2.mdout", p=f"{name}_solv.prmtop",
          c="min1.rst7", r="min2.rst7", O=True)
```

#### 8. Heating (NVT with Restraints)
Write `heat.mdin`:
```fortran
&cntrl
  imin=0, irest=0, ntx=1,
  ntb=1, cut=10.0,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=1.0, ig=-1,
  tempi=0.0, temp0={temp0},
  ntr=1,
  restraint_wt=1.0,
  restraintmask=":@CA,C,N",
  nstlim={nheat}, dt=0.002,
  ntpr=100, ntwx=1000, ntwr=5000,
  ioutfm=1, iwrap=1, ntxo=2,
/
```
```python
amb.pmemd(i="heat.mdin", o="heat.mdout", p=f"{name}_solv.prmtop",
          c="min2.rst7", r="heat.rst7", ref=f"{name}_solv.rst7", O=True)
```

Extract temperature curve from mdout (or `cpptraj` energy extraction) and plot.

#### 9. NVT Equilibration (Restrained)
Write `nvt.mdin`:
```fortran
&cntrl
  imin=0, irest=1, ntx=5,
  ntb=1, cut=10.0,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=1.0, ig=-1, temp0={temp0},
  ntr=1,
  restraint_wt=0.5,
  restraintmask=":@CA,C,N,O",
  nstlim={nnvt}, dt=0.002,
  ntpr=100, ntwx=1000, ntwr=5000,
  ioutfm=1, iwrap=1, ntxo=2,
/
```
```python
amb.pmemd(i="nvt.mdin", o="nvt.mdout", p=f"{name}_solv.prmtop",
          c="heat.rst7", r="nvt.rst7", ref=f"{name}_solv.rst7", O=True)
```

Extract and plot temperature.

#### 10. NPT Equilibration (Unrestrained)
Write `npt.mdin`:
```fortran
&cntrl
  imin=0, irest=1, ntx=5,
  ntb=2, cut=10.0,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=1.0, ig=-1, temp0={temp0},
  ntp=1, barostat=1, pres0=1.0, taup=2.0,
  ntr=0,
  nstlim={nnpt}, dt=0.002,
  ntpr=100, ntwx=1000, ntwr=5000,
  ioutfm=1, iwrap=1, ntxo=2,
/
```
```python
amb.pmemd(i="npt.mdin", o="npt.mdout", p=f"{name}_solv.prmtop",
          c="nvt.rst7", r="npt.rst7", O=True)
```

Extract pressure, density, temperature and plot.

#### 11. Production Setup
Write `prod.mdin`:
```fortran
&cntrl
  imin=0, irest=1, ntx=5,
  ntb=2, cut=10.0,
  ntc=2, ntf=2,
  ntt=3, gamma_ln=1.0, ig=-1, temp0={temp0},
  ntp=1, barostat=2, pres0=1.0,
  ntr=0,
  nstlim={nsteps}, dt=0.002,
  ntpr=5000, ntwx=5000, ntwr=5000,
  ioutfm=1, iwrap=1, ntxo=2,
/
```
```python
amb.pmemd(i="prod.mdin", o="prod.mdout", p=f"{name}_solv.prmtop",
          c="npt.rst7", r="prod.rst7", x="prod.nc", O=True)
```

---

## 3. AMBER-Specific Rationale

These choices come from the canonical AMBER Tutorials (Tutorial 1 Section 5,
Tutorial 7, ComputeCanada molmodsim-amber workshop, and BioExcel biobb
workflows), **not** from analogies to GROMACS:

| Choice | AMBER Equivalent | Difference from GROMACS |
|--------|-----------------|------------------------|
| Two-stage minimization | Restrained then unrestrained | GROMACS runs a single minimization pass |
| SHAKE (`ntc=2, ntf=2`) | Required for 2 fs timestep | GROMACS uses LINCS (`constraint_algorithm = lincs`) |
| Explicit heating | `tempi=0` → `temp0=300` under NVT | GROMACS assigns Maxwell velocities and jumps into NVT |
| NVT equilibration | Restrained NVT before NPT | GROMACS has no explicit NVT-only equilibration step |
| Langevin thermostat (`ntt=3`) | `gamma_ln=1.0` | GROMACS uses V-rescale (`tcoupl = V-rescale`) |
| Berendsen barostat (`barostat=1`) | NPT equilibration only | GROMACS uses Parrinello-Rahman or C-rescale |
| MC barostat (`barostat=2`) | Production (correct NPT ensemble) | GROMACS uses Parrinello-Rahman or C-rescale |
| NetCDF output (`ioutfm=1`) | Binary compressed `.nc` trajectories | GROMACS uses `.xtc` |
| Restart via `ntx=5, irest=1` | Read coordinates + velocities from `.rst7` | GROMACS uses `.tpr` + binary `.cpt` |
| Nonbonded cutoff | `cut=10.0` (angstroms) | GROMACS uses `rcoulomb=1.0` (nm) |

### Research Sources
- [AMBER Tutorial 1: Section 5](https://ambermd.org/tutorials/basic/tutorial1/section5.php)
  — Classic explicit-solvent DNA workflow (min → heat → NPT equil → production)
- [AMBER Tutorial 7: Building Protein Systems in Explicit Solvent](https://ambermd.org/tutorials/basic/tutorial7/index.php)
  — tleap workflow for proteins (ff19SB + OPC)
- [ComputeCanada molmodsim-amber](https://computecanada.github.io/molmodsim-amber-md-lesson/)
  — Modern protein MD on HPC (pmemd, pmemd.cuda)
- [BioExcel biobb AMBER MD Setup](https://mmb.irbbarcelona.org/biobb/workflows/tutorials/biobb_wf_amber_md_setup)
  — Full pipeline using AmberTools (based on MDWeb Amber FULL)

---

## 4. Independent Scientist Review

An unbiased AMBER scientist was asked to review this spec. Key findings and fixes applied:

| Finding | Severity | Fix Applied |
|---------|----------|-------------|
| Production `barostat=1` (Berendsen) does not sample correct NPT ensemble | **Critical** | Production switched to `barostat=2` (MC barostat); NPT equil keeps `barostat=1` |
| `nsteps` formula off by 1000× | **Critical** | Changed `nanoseconds * 1000 * 500000` → `nanoseconds * 500000` |
| `addions` only adds Na+; cationic proteins remain charged | **Critical** | Added `addions protein Cl- 0` alongside Na+ |
| `restraintmask=":1-999"` fails for proteins >999 residues | **Critical** | Changed to `:@CA,C,N` (selects all residues) |
| Equilibration lengths too short for physical equilibration | Major | NVT 10 ps → 100 ps; NPT 50 ps → 250 ps; heating 20 ps → 50 ps |
| Parameter block variables ignored in `.mdin` templates | Major | All `mdin` blocks now use f-string interpolation |
| No random seed (`ig=-1`) for Langevin thermostat | Major | Added `ig=-1` to all dynamics phases |
| Solvation buffer 10 Å is marginal with 10 Å cutoff | Minor | Buffer increased to 12 Å default |
| No `check protein` in tleap script | Minor | Added `check protein` before saving |
| NetCDF restart format (`ntxo=2`) not used | Minor | Added `ntxo=2` to all dynamics |
| Salt calculation vague | Minor | Added explicit `0.0187 * salt_mM * N_wat` formula |

---

## 5. File Layout

```
/workspaces/mddash/private/mddash-notebooks/
├── amber_wrapper.py              (new)
├── amber-protein-setup.ipynb     (new)
├── protein-setup.ipynb           (existing)
├── protein-analysis.ipynb        (existing)
├── mdanalysis_utils.py           (existing)
└── docs/superpowers/specs/2026-05-15-amber-setup-design.md
```
