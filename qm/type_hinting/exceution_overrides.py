from typing import Dict, List
from typing_extensions import TypedDict


class WaveformOverrideType(TypedDict):
    samples: List[float]


class ExecutionOverridesType(TypedDict, total=False):
    waveforms: Dict[str, WaveformOverrideType]
