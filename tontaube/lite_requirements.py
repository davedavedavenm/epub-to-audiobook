"""Keep the pinned upstream lock entries used by the lite backend."""
from pathlib import Path
import re
import sys

# CPU PyTorch wheels are installed at the same version from PyTorch's own
# index. These remaining distributions only support the separate GPU paths.
OMIT = {
    "cupy-cuda12x",
    "flashinfer-python",
    "torch",
    "torchaudio",
    "torchvision",
    "triton",
    "vllm",
}
PREFIXES = ("cuda-", "nvidia-")


def lite_requirements(export):
    include = True
    for line in export.splitlines():
        requirement = re.match(r"([a-z0-9-]+)==", line)
        if requirement:
            name = requirement.group(1)
            include = name not in OMIT and not name.startswith(PREFIXES)
        if include:
            yield line


if __name__ == "__main__":
    print("\n".join(lite_requirements(Path(sys.argv[1]).read_text(encoding="utf-8"))))
