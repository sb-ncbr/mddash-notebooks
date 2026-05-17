"""Thin typed wrapper around AmberTools/PMEMD binaries."""

import shutil
import subprocess
import sys
from contextlib import nullcontext


def _has_gpu() -> bool:
    """Return True if an NVIDIA GPU is available."""
    if not shutil.which("nvidia-smi"):
        return False
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
        return result.returncode == 0 and b"GPU" in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


class AmberError(Exception):
    """Raised when an AMBER binary exits with a non-zero status."""

    def __init__(self, cmd: list[str], returncode: int):
        self.cmd = cmd
        self.returncode = returncode
        super().__init__(f"{' '.join(cmd)} exited with status {returncode}")

    def _render_traceback_(self):
        return [str(self)]


def _run(
    binary: str,
    long_flags: set[str] | None = None,
    stdout_file: str | None = None,
    **kwargs: object,
) -> None:
    """
    Run an AMBER binary with CLI flags built from kwargs.

    Boolean values become bare flags (e.g., ``O=True`` → ``-O``).
    Long flags in ``long_flags`` become ``--flag``; all others become ``-flag``.
    ``None`` and ``False`` values are omitted.

    If ``stdout_file`` is given the binary's stdout is redirected to that file.
    Output is otherwise streamed to stdout/stderr in real time.
    """
    exe = shutil.which(binary)
    if exe is None:
        raise RuntimeError(f"Binary not found in PATH: {binary}")

    long_flags = long_flags or set()
    cmd = [exe]
    for key, val in kwargs.items():
        if val is None or val is False:
            continue
        flag = f"--{key}" if key in long_flags else f"-{key}"
        if isinstance(val, bool):
            cmd.append(flag)
        else:
            cmd.extend([flag, str(val)])

    stdout_context = open(stdout_file, "w") if stdout_file else nullcontext(None)
    with stdout_context as stdout:
        process = subprocess.Popen(
            cmd,
            stdout=stdout if stdout_file else subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if process.stdout is not None:
            for chunk in iter(lambda: process.stdout.read(4096), ""):
                sys.stdout.write(chunk)
                sys.stdout.flush()

        process.wait()

    if process.returncode != 0:
        raise AmberError(cmd, process.returncode)


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
) -> None:
    """
    Run ``pmemd`` with automatic engine selection.

    Automatically selects the best engine:
    - ``pmemd.cuda`` when an NVIDIA GPU is available.
    - Serial ``pmemd`` otherwise.

    The selected engine and command are printed before execution.

    Args:
        i: Input control file (``.mdin``).
        o: Output log file (``.mdout``).
        p: Topology file (``.prmtop``).
        c: Input coordinates (``.rst7`` / ``.ncrst``).
        r: Restart file output.
        x: Trajectory file output.
        ref: Reference structure for restraints.
        O: Overwrite output files.
    """
    checked_engines: list[str] = []
    if _has_gpu():
        checked_engines.append("pmemd.cuda")
        if shutil.which("pmemd.cuda"):
            print("amber_wrapper: using pmemd.cuda (GPU detected)")
            return _run("pmemd.cuda", i=i, o=o, p=p, c=c, r=r, x=x, ref=ref, O=O)

    checked_engines.append("pmemd")
    if shutil.which("pmemd"):
        if "pmemd.cuda" in checked_engines:
            print("amber_wrapper: pmemd.cuda not found; falling back to serial pmemd")
        else:
            print("amber_wrapper: using serial pmemd")
        return _run("pmemd", i=i, o=o, p=p, c=c, r=r, x=x, ref=ref, O=O)

    checked = ", ".join(checked_engines)
    raise RuntimeError(f"No usable pmemd engine found in PATH; checked: {checked}")


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
    """
    Run ``sander`` (free CPU engine).

    Uses OpenMP threading automatically (respects ``OMP_NUM_THREADS``).
    """
    return _run("sander", i=i, o=o, p=p, c=c, r=r, x=x, ref=ref, O=O)


def cpptraj(
    p: str | None = None,
    i: str | None = None,
    y: str | None = None,
    o: str | None = None,
) -> None:
    """
    Run ``cpptraj``.

    Args:
        p: Topology file.
        i: Input control script.
        y: Input trajectory.
        o: Redirect stdout to file.
    """
    return _run("cpptraj", p=p, i=i, y=y, o=o)


def pdb4amber(
    i: str | None = None,
    o: str | None = None,
    reduce: bool = False,
    y: bool = False,
    d: bool = False,
) -> None:
    """
    Run ``pdb4amber``.

    Args:
        i: PDB input file.
        o: PDB output file.
        reduce: Run ``reduce`` to add hydrogens.
        y: Remove all hydrogen atoms.
        d: Remove water.
    """
    return _run("pdb4amber", long_flags={"reduce"}, i=i, o=o, reduce=reduce, y=y, d=d)


def ambpdb(
    p: str,
    c: str | None = None,
    o: str | None = None,
) -> None:
    """
    Run ``ambpdb``.

    Args:
        p: Topology file (``.prmtop``).
        c: Coordinate/restart file.
        o: Output PDB file (stdout is redirected here).
    """
    return _run("ambpdb", p=p, c=c, stdout_file=o)


def parmed(
    input: str | None = None,
    p: str | None = None,
    O: bool = False,
) -> None:
    """
    Run ``parmed``.

    Args:
        input: Input script.
        p: Topology file.
        O: Overwrite output files.
    """
    return _run("parmed", long_flags={"input"}, input=input, p=p, O=O)


def antechamber(
    i: str,
    fi: str = "gaff",
    o: str | None = None,
    fo: str = "mol2",
    c: str = "bcc",
    nc: int | None = None,
    **extra: object,
) -> None:
    """
    Run ``antechamber``.

    Args:
        i: Input file.
        fi: Input format.
        o: Output file.
        fo: Output format.
        c: Charge method.
        nc: Net molecular charge.
        **extra: Additional CLI flags.
    """
    flags: dict[str, object] = {"i": i, "fi": fi, "fo": fo, "c": c, "o": o, "nc": nc}
    flags.update(extra)
    return _run("antechamber", **flags)
