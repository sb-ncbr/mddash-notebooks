# AMBER Protein MD Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `amber_wrapper.py` (thin typed subprocess wrapper around AmberTools) and `amber-protein-setup.ipynb` (setup notebook following validated AMBER workflow).

**Architecture:** A thin Python wrapper exposes AmberTools CLI programs as typed functions (`amb.tleap(...)`, `amb.pmemd(...)`). The notebook generates `.mdin` control files via f-strings and calls the wrapper step-by-step, mirroring the existing GROMACS notebook philosophy.

**Wrapper design:** One `_run(binary, **kwargs)` helper builds the CLI from a dict and invokes `subprocess.run`. Every wrapper function declares typed parameters and forwards them directly to `_run` (e.g., `_run("pmemd", i=i, o=o, p=p, O=O)`). `_run` skips `None` and `False` values, emitting booleans as bare flags and everything else as `-flag value`. This keeps wrappers DRY, readable, and avoids the long `if` chains that would otherwise duplicate the same filtering logic in every function.

**Tech Stack:** Python 3.12, AmberTools/PMEMD (host binaries), NGLView, MDTraj, NumPy, Matplotlib

---

## File Structure

| File | Role |
|------|------|
| `amber_wrapper.py` | New. Typed subprocess wrapper for AmberTools binaries. No simulation logic. |
| `amber-protein-setup.ipynb` | New. Jupyter notebook: parameter block → PDB prep → tleap → min → heat → NVT → NPT → prod → plots. |

---

### Task 1: Amber Wrapper — Core `_run` Helper + `tleap`

**Files:**
- Create: `amber_wrapper.py`

- [ ] **Step 1: Write `amber_wrapper.py` base helper and `tleap`**

```python
"""Thin typed wrapper around AmberTools/PMEMD binaries."""

import shutil
import subprocess
from typing import Literal


def _run(binary: str, **kwargs: object) -> str:
    """Run an AMBER binary with CLI flags built from kwargs.

    Boolean values become bare flags (e.g., ``O=True`` → ``-O``).
    All other values are emitted as ``-flag value``.
    ``None`` and ``False`` values are omitted.
    """
    exe = shutil.which(binary)
    if exe is None:
        raise RuntimeError(f"Binary not found in PATH: {binary}")

    cmd = [exe]
    for key, val in kwargs.items():
        if val is None or val is False:
            continue
        flag = f"-{key}"
        if isinstance(val, bool):
            cmd.append(flag)
        else:
            cmd.extend([flag, str(val)])

    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


def tleap(
    f: str | None = None,
    I: str | None = None,
    s: bool = False,
) -> str:
    """Run ``tleap``.

    Args:
        f: Source script file.
        I: Add directory to search path.
        s: Ignore leaprc startup file.
    """
    return _run("tleap", f=f, I=I, s=s)
```

- [ ] **Step 2: Verify `tleap` builds correct command**

Run: `python -c "import amber_wrapper as amb; print(amb.tleap(f='test.in'))"`

*(If `tleap` is not in PATH, expect `RuntimeError`. Otherwise it runs and returns stdout.)*

- [ ] **Step 3: Commit**

```bash
git add amber_wrapper.py
git commit -m "feat(amber): Add base wrapper helper and tleap"
```

---

### Task 2: Amber Wrapper — `pmemd`, `sander`, `pmemd.cuda`

**Files:**
- Modify: `amber_wrapper.py`

- [ ] **Step 1: Add `pmemd`, `sander`, and GPU variant**

Append to `amber_wrapper.py`:

```python
def pmemd(
    i: str | None = None,
    o: str | None = None,
    p: str | None = None,
    c: str | None = None,
    r: str | None = None,
    x: str | None = None,
    ref: str | None = None,
    O: bool = False,
    cuda: bool = False,
) -> str:
    """Run ``pmemd`` (or ``pmemd.cuda``).

    Args:
        i: Input control file (``.mdin``).
        o: Output log file (``.mdout``).
        p: Topology file (``.prmtop``).
        c: Input coordinates (``.rst7`` / ``.ncrst``).
        r: Restart file output.
        x: Trajectory file output.
        ref: Reference structure for restraints.
        O: Overwrite output files.
        cuda: Use ``pmemd.cuda`` instead of ``pmemd``.
    """
    binary = "pmemd.cuda" if cuda else "pmemd"
    return _run(binary, i=i, o=o, p=p, c=c, r=r, x=x, ref=ref, O=O)


def sander(
    i: str | None = None,
    o: str | None = None,
    p: str | None = None,
    c: str | None = None,
    r: str | None = None,
    x: str | None = None,
    ref: str | None = None,
    O: bool = False,
) -> str:
    """Run ``sander`` (free CPU engine).

    Args match ``pmemd`` except no ``cuda`` flag.
    """
    return _run("sander", i=i, o=o, p=p, c=c, r=r, x=x, ref=ref, O=O)
```

- [ ] **Step 2: Verify command-line construction**

Run: `python -c "import amber_wrapper as amb; print(amb.pmemd(i='min.mdin', o='min.mdout', p='top.prmtop', c='in.rst7', r='out.rst7', O=True))"`

*(Expect RuntimeError if pmemd not in PATH; otherwise it executes.)*

- [ ] **Step 3: Commit**

```bash
git add amber_wrapper.py
git commit -m "feat(amber): Add pmemd, pmemd.cuda, and sander wrappers"
```

---

### Task 3: Amber Wrapper — `cpptraj`, `pdb4amber`, `ambpdb`, `parmed`

**Files:**
- Modify: `amber_wrapper.py`

- [ ] **Step 1: Add remaining utility wrappers**

Append to `amber_wrapper.py`:

```python
def cpptraj(
    p: str | None = None,
    i: str | None = None,
    input: str | None = None,
    y: str | None = None,
    O: bool = False,
) -> str:
    """Run ``cpptraj``.

    Args:
        p: Topology file.
        i: Input control script.
        input: Inline input string (written to a temp file internally).
        y: Input trajectory.
        O: Overwrite output files.
    """
    if input is not None:
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".in", delete=False
        ) as tmp:
            tmp.write(input)
            tmp.flush()
            i = tmp.name

    return _run("cpptraj", p=p, i=i, y=y, O=O)


def pdb4amber(
    input: str,
    output: str,
    reduce: bool = False,
    nohydrogens: bool = False,
    dry: bool = False,
    justify: bool = False,
    resmap: str | None = None,
    addatomicnumbers: bool = False,
) -> str:
    """Run ``pdb4amber``.

    Args:
        input: Input PDB file.
        output: Output PDB file.
        reduce: Run ``reduce`` to add hydrogens.
        nohydrogens: Do not run ``reduce``.
        dry: Strip water.
        justify: Right-justify atom names.
        resmap: Residue mapping file.
        addatomicnumbers: Add atomic numbers.
    """
    return _run(
        "pdb4amber",
        input=input,
        output=output,
        reduce=reduce,
        nohydrogens=nohydrogens,
        dry=dry,
        justify=justify,
        resmap=resmap,
        addatomicnumbers=addatomicnumbers,
    )


def ambpdb(
    p: str,
    c: str | None = None,
    o: str | None = None,
) -> str:
    """Run ``ambpdb``.

    Args:
        p: Topology file (``.prmtop``).
        c: Coordinate/restart file.
        o: Output PDB file.
    """
    return _run("ambpdb", p=p, c=c, o=o)


def parmed(
    input: str | None = None,
    p: str | None = None,
    O: bool = False,
) -> str:
    """Run ``parmed``.

    Args:
        input: Input script.
        p: Topology file.
        O: Overwrite output files.
    """
    return _run("parmed", input=input, p=p, O=O)


def antechamber(
    i: str,
    fi: str = "gaff",
    o: str | None = None,
    fo: str = "mol2",
    c: str = "bcc",
    nc: int | None = None,
    **extra: object,
) -> str:
    """Run ``antechamber``.

    Args:
        i: Input file.
        fi: Input format.
        o: Output file.
        fo: Output format.
        c: Charge method.
        nc: Net molecular charge.
        **extra: Additional CLI flags.
    """
    flags = dict(i=i, fi=fi, fo=fo, c=c, o=o, nc=nc)
    flags.update(extra)
    return _run("antechamber", **flags)
```

- [ ] **Step 2: Commit**

```bash
git add amber_wrapper.py
git commit -m "feat(amber): Add cpptraj, pdb4amber, ambpdb, parmed, antechamber"
```

---

### Task 4: Amber Wrapper — Smoke Test

**Files:**
- Create: `test_amber_wrapper.py`

- [ ] **Step 1: Write a smoke test that validates command-line construction**

```python
import subprocess
from unittest.mock import patch

import amber_wrapper as amb


def test_pmemd_command_building():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "ok"
        mock_run.return_value.stderr = ""
        amb.pmemd(i="min.mdin", o="min.mdout", p="top.prmtop", c="in.rst7", O=True)

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0].endswith("pmemd")
        assert "-i" in cmd and "min.mdin" in cmd
        assert "-o" in cmd and "min.mdout" in cmd
        assert "-p" in cmd and "top.prmtop" in cmd
        assert "-c" in cmd and "in.rst7" in cmd
        assert "-O" in cmd
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest test_amber_wrapper.py -v`
Expected: `test_amber_wrapper.py::test_pmemd_command_building PASSED`

- [ ] **Step 3: Commit**

```bash
git add test_amber_wrapper.py
git commit -m "test(amber): Add smoke test for wrapper CLI construction"
```

---

### Task 5: Notebook — Skeleton, Imports, Parameter Block

**Files:**
- Create: `amber-protein-setup.ipynb`

- [ ] **Step 1: Create notebook with parameter block and imports**

Create `amber-protein-setup.ipynb` with the first three cells:

**Cell 1 (Markdown):**
```markdown
# AMBER simulation setup for basic protein MD

Heavily based on the AMBER Tutorial 1 (Section 5), Tutorial 7, and the BioExcel biobb workflow.

The dashboard provides you with the molecule as `input.pdb`.
First, give it a nice name, specify the main simulation length, and adjust equilibration steps if necessary.
```

**Cell 2 (Code):**
```python
name = "protein"  # give me a better name

nanoseconds = 0.05  # just for fun
nsteps = int(nanoseconds * 500000)  # assumes 2 fs timestep

nmin = 5000          # minimization cycles per stage
nheat = 25000        # heating steps (50 ps)
nnvt = 50000         # NVT equilibration steps (100 ps)
nnpt = 125000        # NPT equilibration steps (250 ps)
temp0 = 300.0        # target temperature (K)
salt_mM = 150.0      # salt concentration
buffer = 12.0        # solvation buffer (angstroms)
```

**Cell 3 (Code):**
```python
import amber_wrapper as amb
import nglview as nv
import mdtraj as md
import numpy as np
import matplotlib.pyplot as plt
```

**Cell 4 (Code):**
```python
nv.show_file("input.pdb")
```

- [ ] **Step 2: Commit**

```bash
git add amber-protein-setup.ipynb
git commit -m "feat(amber): Create notebook skeleton with params and imports"
```

---

### Task 6: Notebook — PDB Prep and tleap

**Files:**
- Modify: `amber-protein-setup.ipynb`

- [ ] **Step 1: Add PDB prep and tleap cells**

**Cell 5 (Markdown):**
```markdown
## Initial setup

### Prepare PDB

Run `pdb4amber` to clean the input: rename residues, handle disulfides, remove CONECT records.
```

**Cell 6 (Code):**
```python
amb.pdb4amber(input="input.pdb", output=f"{name}_clean.pdb", reduce=True)
```

**Cell 7 (Markdown):**
```markdown
### Build topology and solvate with tleap

Generate force field, neutralize, solvate, and add salt.
```

**Cell 8 (Code):**
```python
with open(f"{name}.leap.in", "w") as leap:
    leap.write(f"""\
source leaprc.protein.ff19SB
source leaprc.water.opc
protein = loadpdb {name}_clean.pdb
check protein
saveamberparm protein {name}_gas.prmtop {name}_gas.rst7
addions protein Na+ 0
addions protein Cl- 0
solvateoct protein OPCBOX {buffer}
""")

# Salt calculation: run tleap once to get water count,
# then append addionsrand and final saveamberparm.
amb.tleap(f=f"{name}.leap.in")

# Parse leap.log for number of water residues
import re
with open("leap.log") as log:
    content = log.read()
match = re.search(r"Added\s+(\d+)\s+residues", content)
if match:
    n_wat = int(match.group(1))
    n_ion_pairs = int(0.0187 * salt_mM * n_wat)
    print(f"Water molecules: {n_wat}, adding {n_ion_pairs} ion pairs")
else:
    n_ion_pairs = 0
    print("Could not detect water count; skipping salt buffer")

# Append neutralization + salt + final save
with open(f"{name}.leap.in", "a") as leap:
    if n_ion_pairs > 0:
        leap.write(f"addionsrand protein Na+ {n_ion_pairs} Cl- {n_ion_pairs}\n")
    leap.write(f"saveamberparm protein {name}_solv.prmtop {name}_solv.rst7\n")
    leap.write("quit\n")

amb.tleap(f=f"{name}.leap.in")
```

- [ ] **Step 2: Commit**

```bash
git add amber-protein-setup.ipynb
git commit -m "feat(amber): Add PDB prep and tleap solvation cells"
```

---

### Task 7: Notebook — Minimization

**Files:**
- Modify: `amber-protein-setup.ipynb`

- [ ] **Step 1: Add minimization cells**

**Cell 9 (Markdown):**
```markdown
### Minimize — Stage 1 (restrained)

Relax solvent around the restrained protein.
```

**Cell 10 (Code):**
```python
with open("min1.mdin", "w") as m:
    m.write(f"""&cntrl
  imin=1, ncyc={nmin//2}, maxcyc={nmin}, ntmin=1,
  ntb=1, cut=10.0,
  ntr=1,
  restraint_wt=2.0,
  restraintmask=":@CA,C,N",
  ntpr=50,
/
""")

amb.pmemd(i="min1.mdin", o="min1.mdout", p=f"{name}_solv.prmtop",
          c=f"{name}_solv.rst7", r="min1.rst7", ref=f"{name}_solv.rst7", O=True)
```

**Cell 11 (Markdown):**
```markdown
### Minimize — Stage 2 (unrestrained)

Relax the entire system.
```

**Cell 12 (Code):**
```python
with open("min2.mdin", "w") as m:
    m.write(f"""&cntrl
  imin=1, ncyc={nmin//2}, maxcyc={nmin}, ntmin=1,
  ntb=1, cut=10.0,
  ntr=0,
  ntpr=50,
/
""")

amb.pmemd(i="min2.mdin", o="min2.mdout", p=f"{name}_solv.prmtop",
          c="min1.rst7", r="min2.rst7", O=True)
```

**Cell 13 (Code):**
```python
# Convert restart to PDB for visualization
amb.ambpdb(p=f"{name}_solv.prmtop", c="min2.rst7", o="min2.pdb")
nv.show_file("min2.pdb")
```

- [ ] **Step 2: Commit**

```bash
git add amber-protein-setup.ipynb
git commit -m "feat(amber): Add two-stage minimization cells"
```

---

### Task 8: Notebook — Heating and NVT Equilibration

**Files:**
- Modify: `amber-protein-setup.ipynb`

- [ ] **Step 1: Add heating and NVT cells**

**Cell 14 (Markdown):**
```markdown
## Equilibration

### Heat the system (NVT with restraints)

Ramp from 0 K to target temperature with weak restraints on the protein.
```

**Cell 15 (Code):**
```python
with open("heat.mdin", "w") as h:
    h.write(f"""&cntrl
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
""")

amb.pmemd(i="heat.mdin", o="heat.mdout", p=f"{name}_solv.prmtop",
          c="min2.rst7", r="heat.rst7", ref=f"{name}_solv.rst7", O=True)
```

**Cell 16 (Markdown):**
```markdown
### NVT equilibration (restrained)

Hold the box at constant volume while maintaining temperature.
```

**Cell 17 (Code):**
```python
with open("nvt.mdin", "w") as nvt:
    nvt.write(f"""&cntrl
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
""")

amb.pmemd(i="nvt.mdin", o="nvt.mdout", p=f"{name}_solv.prmtop",
          c="heat.rst7", r="nvt.rst7", ref=f"{name}_solv.rst7", O=True)
```

**Cell 18 (Code):**
```python
# Extract temperature from mdout and plot
temp = []
with open("heat.mdout") as f:
    for line in f:
        if line.startswith(" NSTEP"):
            break
    for line in f:
        if "TEMP(K)" in line:
            parts = line.split()
            if len(parts) >= 8:
                try:
                    temp.append(float(parts[7]))
                except ValueError:
                    pass

if temp:
    plt.figure(figsize=(10, 4))
    plt.plot(temp)
    plt.title("Heating phase temperature")
    plt.xlabel("Output step")
    plt.ylabel("Temperature (K)")
    plt.grid()
    plt.show()
```

- [ ] **Step 2: Commit**

```bash
git add amber-protein-setup.ipynb
git commit -m "feat(amber): Add heating and NVT equilibration cells"
```

---

### Task 9: Notebook — NPT Equilibration and Production

**Files:**
- Modify: `amber-protein-setup.ipynb`

- [ ] **Step 1: Add NPT and production cells**

**Cell 19 (Markdown):**
```markdown
### NPT equilibration (unrestrained)

Allow the box volume to relax at constant pressure.
```

**Cell 20 (Code):**
```python
with open("npt.mdin", "w") as npt:
    npt.write(f"""&cntrl
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
""")

amb.pmemd(i="npt.mdin", o="npt.mdout", p=f"{name}_solv.prmtop",
          c="nvt.rst7", r="npt.rst7", O=True)
```

**Cell 21 (Code):**
```python
# Plot pressure, density, temperature from NPT
data = {"Press": [], "Density": [], "Temp": []}
labels = {"Press": 15, "Density": 16, "Temp": 7}  # mdout column indices (0-based)

with open("npt.mdout") as f:
    for line in f:
        if line.startswith(" NSTEP"):
            break
    for line in f:
        parts = line.split()
        if len(parts) < 17:
            continue
        try:
            data["Press"].append(float(parts[15]))
            data["Density"].append(float(parts[16]))
            data["Temp"].append(float(parts[7]))
        except (ValueError, IndexError):
            pass

fig, axes = plt.subplots(3, 1, figsize=(10, 10))
for ax, key in zip(axes, ["Press", "Density", "Temp"]):
    if data[key]:
        ax.plot(data[key])
        ax.set_ylabel(key)
        ax.grid()
axes[-1].set_xlabel("Step")
plt.suptitle("NPT equilibration")
plt.tight_layout()
plt.show()
```

**Cell 22 (Markdown):**
```markdown
## Prepare production simulation

Run unrestrained production MD in the NPT ensemble.
```

**Cell 23 (Code):**
```python
with open("prod.mdin", "w") as prod:
    prod.write(f"""&cntrl
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
""")

amb.pmemd(i="prod.mdin", o="prod.mdout", p=f"{name}_solv.prmtop",
          c="npt.rst7", r="prod.rst7", x="prod.nc", O=True)
```

- [ ] **Step 2: Commit**

```bash
git add amber-protein-setup.ipynb
git commit -m "feat(amber): Add NPT equilibration and production cells"
```

---

### Task 10: Final Review and Cleanup

**Files:**
- Modify: `amber-protein-setup.ipynb` (if needed)
- Modify: `amber_wrapper.py` (if needed)

- [ ] **Step 1: Validate spec coverage**

Cross-check the notebook against the spec:
- `ff19SB` + `OPC` force field — yes (tleap cell)
- `addions` both Na+ and Cl- — yes
- Salt calculation from water count — yes
- Two-stage minimization with restraints — yes
- `cut=10.0`, `ntc=2, ntf=2` everywhere — yes
- Langevin thermostat `ntt=3, gamma_ln=1.0, ig=-1` — yes
- Heating `tempi=0.0` — yes
- Production `barostat=2` — yes
- `ioutfm=1`, `ntxo=2`, `iwrap=1` — yes
- `restraintmask=":@CA,C,N"` — yes
- f-string interpolation from parameter block — yes

- [ ] **Step 2: Run notebook cell-by-cell in a clean directory**

Run: Execute each cell sequentially with a sample `input.pdb`.

Expected: No crashes, all output files generated (`*_solv.prmtop`, `min1.rst7`, `heat.rst7`, `prod.nc`, etc.).

- [ ] **Step 3: Final commit**

```bash
git add amber-protein-setup.ipynb amber_wrapper.py test_amber_wrapper.py
git commit -m "feat(amber): Complete AMBER protein setup notebook and wrapper"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** Every cell outline in the spec has a corresponding task.
- [ ] **No placeholders:** All code is complete; no TBD, TODO, or "implement later."
- [ ] **Type consistency:** `pmemd` signature uses same arg names (`i`, `o`, `p`, `c`, `r`, `x`, `ref`, `O`) across all notebook cells.
- [ ] **File paths:** All paths are exact relative paths from repo root.
