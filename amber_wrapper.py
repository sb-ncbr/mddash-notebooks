"""Thin typed wrapper around AmberTools/PMEMD binaries."""

import shutil
import subprocess


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
