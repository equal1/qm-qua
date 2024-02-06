import os
import traceback
from pathlib import Path


def _get_loc() -> str:
    qm_package_dir = Path(os.path.abspath(__file__)).parent
    trace = [i for i in traceback.extract_stack() if qm_package_dir not in Path(i.filename).parents][-1]
    return f'File "{trace.filename}", line {trace.lineno}: {trace.line} '
