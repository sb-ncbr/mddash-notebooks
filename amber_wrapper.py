"""Thin typed wrapper around AmberTools/PMEMD binaries."""

import shutil
import subprocess


def _run(binary: str, **kwargs: object) -> None:
    """Run an AMBER binary with CLI flags built from kwargs.

    Boolean values become bare flags (e.g., ``O=True`` → ``-O``).
    All other values are emitted as ``-flag value``.
    ``None`` and ``False`` values are omitted.

    Output is printed directly to stdout/stderr as the command runs.
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

    subprocess.run(cmd, check=True)


def tleap(
    f: str | None = None,
    I: str | None = None,
    s: bool = False,
) -> None:
    """
    Run ``tleap``.

    Args:
        f: Source script file.
        I: Add directory to search path.
        s: Ignore leaprc startup file.
    """
    return _run("tleap", f=f, I=I, s=s)


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
) -> None:
    """
    Run ``pmemd`` (or ``pmemd.cuda``).

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
) -> None:
    """Run ``sander`` (free CPU engine).

    Args match ``pmemd`` except no ``cuda`` flag.
    """
    return _run("sander", i=i, o=o, p=p, c=c, r=r, x=x, ref=ref, O=O)


def cpptraj(
    p: str | None = None,
    i: str | None = None,
    input: str | None = None,
    y: str | None = None,
    O: bool = False,
) -> None:
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

        with tempfile.NamedTemporaryFile(mode="w", suffix=".in", delete=False) as tmp:
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
) -> None:
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
) -> None:
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
) -> None:
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
) -> None:
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
    flags: dict[str, object] = dict(i=i, fi=fi, fo=fo, c=c, o=o, nc=nc)
    flags.update(extra)
    return _run("antechamber", **flags)
