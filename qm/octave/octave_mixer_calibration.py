import abc
import time
import logging
from enum import Enum, auto
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, Mapping, Optional, cast

import numpy as np
from octave_sdk import Octave, RFInputLOSource
from octave_sdk._errors import InvalidLoSource
from octave_sdk._octave_client import OctaveClient
from octave_sdk.octave import UnableToSetFrequencyError
from octave_sdk.grpc.quantummachines.octave.api.v1 import (
    SynthUpdate,
    OctaveModule,
    SingleUpdate,
    RfUpConvUpdate,
    ModuleReference,
    IfDownConvUpdate,
    RfDownConvUpdate,
    IfDownConvUpdateMode,
    SynthUpdateMainOutput,
    SynthUpdateSynthOutput,
    IfDownConvUpdateChannel,
    RfDownConvUpdateLoInput,
    RfDownConvUpdateRfInput,
    IfDownConvUpdateCoupling,
    SynthUpdateSecondaryOutput,
    SynthUpdateSynthOutputPower,
    RfUpConvUpdateFastSwitchMode,
)

from qm.program import Program
from qm.type_hinting import Number
from qm.elements.element import Element
from qm.jobs.running_qm_job import RunningQmJob
from qm.grpc.qua_config import QuaConfigMixInputs
from qm.elements.up_converted_input import UpconvertedInput
from qm.exceptions import QmQuaException, CantCalibrateElementError
from qm.octave._calibration_names import SavedVariablesNames, CalibrationElementsNames
from qm.octave._calibration_analysis import (
    Array,
    LOAnalysisDebugData,
    ImageDataAnalysisResult,
    _get_and_analyze_lo_data,
    _get_and_analyze_image_data,
)
from qm.qua import (
    IO1,
    IO2,
    Util,
    amp,
    if_,
    for_,
    play,
    save,
    align,
    else_,
    fixed,
    pause,
    assign,
    while_,
    declare,
    measure,
    program,
    dual_demod,
    reset_phase,
    update_correction,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from qm.QuantumMachine import QuantumMachine

CALIBRATION_INPUT = 2


class DConvQuadrature(Enum):
    I = auto()
    Q = auto()
    IQ = auto()


@dataclass
class LOFrequencyDebugData:
    prev_result: Optional[Tuple[float, ...]]
    power_amp_attn: Optional[int]
    coarse: List[LOAnalysisDebugData]
    fine: List[LOAnalysisDebugData]


@dataclass
class ImageResult:
    prev_result: Optional[Tuple[float, float]]
    coarse: ImageDataAnalysisResult
    fine: ImageDataAnalysisResult


@dataclass
class LOFrequencyCalibrationResult:
    i0: float
    q0: float
    dc_gain: float
    dc_phase: float
    temperature: float
    image: Dict[Number, ImageResult]
    debug: LOFrequencyDebugData
    plugin_data: Any = None


MixerCalibrationResults = Dict[Tuple[Number, float], LOFrequencyCalibrationResult]


@dataclass
class DeprecatedCalibrationResult:
    correction: List[float]
    i_offset: float
    q_offset: float
    lo_frequency: float
    if_frequency: float
    temperature: float
    mixer_id: str
    optimizer_parameters: Dict[str, Any]


DeprecatedMixerCalibrationResults = Dict[Tuple[int, int], DeprecatedCalibrationResult]


class CalibrationCallback(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __call__(self, lo_freq: float, lo_calibration_result: LOFrequencyCalibrationResult) -> Any:
        pass


@dataclass
class AutoCalibrationParams:
    use_main_lo: bool = False
    external_loopback: bool = False
    offset_frequency: float = 7e6
    dconv_quadrature: DConvQuadrature = DConvQuadrature.IQ
    if_amplitude: float = 0.125
    calibrate_lo_with_if: bool = True
    callback: Optional[CalibrationCallback] = None


class NoCalibrationElements(QmQuaException):
    pass


def convert_to_old_calibration_result(
    calibration_result: MixerCalibrationResults, mixer_id: str
) -> DeprecatedMixerCalibrationResults:
    to_return = {}
    for (lo_freq, _), lo_result in calibration_result.items():
        for if_freq, if_result in lo_result.image.items():
            curr_result = DeprecatedCalibrationResult(
                correction=list(if_result.fine.correction),
                i_offset=lo_result.i0,
                q_offset=lo_result.q0,
                lo_frequency=lo_freq,
                if_frequency=if_freq,
                temperature=lo_result.temperature,
                mixer_id=mixer_id,
                optimizer_parameters={},
            )
            to_return[(int(lo_freq), int(if_freq))] = curr_result
    return to_return


class OctaveMixerCalibration:
    def __init__(self, quantum_machine: "QuantumMachine", client: Octave):
        self._qm = quantum_machine
        if not self._qm._octave_calibration_elements:
            raise NoCalibrationElements(
                "No calibration elements were found, if you want to use the calibration "
                "please open the QM with the flag 'add_calibration_elements_to_config'."
            )
        self._calibration_elements = self._qm._octave_calibration_elements
        self._client = client

        self._lo_step = 2**-3
        self._lo_range = 2**1
        self._n_lo = int(self._lo_range / self._lo_step) + 1

        self._image_step = 2**-6
        self._image_range = 2**-1
        self._n_image = int(self._image_range / self._image_step) + 1

    @property
    def _low_level_client(self) -> OctaveClient:
        return self._client._client

    def _generate_program(self, elements_names: CalibrationElementsNames, params: AutoCalibrationParams) -> Program:
        def read_lo_and_image_power() -> None:
            align()

            reset_phase(elements_names.iq_mixer)
            reset_phase(elements_names.lo_analyzer)
            reset_phase(elements_names.image_analyzer)

            play("DC_offset" * amp(i0_curr), elements_names.i_offset)
            play("DC_offset" * amp(q0_curr), elements_names.q_offset)
            play("calibration" * amp(scale_cal), elements_names.iq_mixer)

            if params.dconv_quadrature == DConvQuadrature.I:
                measure(
                    "Analyze",
                    elements_names.lo_analyzer,
                    None,
                    dual_demod.full("integW_cos", "out1", "integW_zero", "out2", I2),
                    dual_demod.full("integW_minus_sin", "out1", "integW_zero", "out2", Q2),
                )
                measure(
                    "Analyze",
                    elements_names.image_analyzer,
                    None,
                    dual_demod.full("integW_cos", "out1", "integW_zero", "out2", I3),
                    dual_demod.full("integW_minus_sin", "out1", "integW_zero", "out2", Q3),
                )
            elif params.dconv_quadrature == DConvQuadrature.Q:
                measure(
                    "Analyze",
                    elements_names.lo_analyzer,
                    None,
                    dual_demod.full("integW_zero", "out1", "integW_sin", "out2", I2),
                    dual_demod.full("integW_zero", "out1", "integW_cos", "out2", Q2),
                )
                measure(
                    "Analyze",
                    elements_names.image_analyzer,
                    None,
                    dual_demod.full("integW_zero", "out1", "integW_sin", "out2", I3),
                    dual_demod.full("integW_zero", "out1", "integW_cos", "out2", Q3),
                )
            else:
                measure(
                    "Analyze",
                    elements_names.lo_analyzer,
                    None,
                    dual_demod.full("integW_cos", "out1", "integW_sin", "out2", I2),
                    dual_demod.full("integW_minus_sin", "out1", "integW_cos", "out2", Q2),
                )
                measure(
                    "Analyze",
                    elements_names.image_analyzer,
                    None,
                    dual_demod.full("integW_cos", "out1", "integW_sin", "out2", I3),
                    dual_demod.full("integW_minus_sin", "out1", "integW_cos", "out2", Q3),
                )

            assign(lo_power, (I2 * I2 + Q2 * Q2))
            assign(image_power, (I3 * I3 + Q3 * Q3))

        def update_correction_g_phi() -> None:
            assign(s_mat, p_curr)
            assign(s2, s_mat * s_mat)
            assign(c_mat, 1 + 1.5 * s2 - 3.125 * (s2 * s2))
            assign(g_mat_plus, 1 + g_curr + 0.5 * g_curr * g_curr)
            assign(g_mat_minus, 1 - g_curr + 0.5 * g_curr * g_curr)
            assign(c00, g_mat_plus * c_mat)
            assign(c01, g_mat_plus * s_mat)
            assign(c10, g_mat_minus * s_mat)
            assign(c11, g_mat_minus * c_mat)
            update_correction(elements_names.iq_mixer, c00, c01, c10, c11)

        with program() as prog:

            # variables for getting IQ data
            Q2 = declare(fixed)
            Q3 = declare(fixed)
            I2 = declare(fixed)
            I3 = declare(fixed)

            lo_power = declare(fixed)
            image_power = declare(fixed)

            i0_center = declare(fixed)
            q0_center = declare(fixed)
            i0_offset = declare(fixed)
            q0_offset = declare(fixed)
            i0_curr = declare(fixed)
            q0_curr = declare(fixed)
            i0_best = declare(fixed)
            q0_best = declare(fixed)

            scale_iq = declare(fixed)
            scale_gp = declare(fixed)
            scale_cal = declare(fixed)

            g_center = declare(fixed)
            p_center = declare(fixed)
            g_offset = declare(fixed)
            p_offset = declare(fixed)
            g_curr = declare(fixed)
            p_curr = declare(fixed)

            # variables for correction matrix
            g_mat_plus = declare(fixed)
            g_mat_minus = declare(fixed)
            s2 = declare(fixed)
            c_mat = declare(fixed)
            s_mat = declare(fixed)
            c00 = declare(fixed)
            c01 = declare(fixed)
            c10 = declare(fixed)
            c11 = declare(fixed)

            best_lo_power = declare(fixed)

            task = declare(int)
            go_on = declare(bool, value=True)

            with while_(go_on):

                pause()
                assign(task, IO1)

                with if_(task < 2):

                    assign(scale_cal, 1.0 if params.calibrate_lo_with_if else 0.0)
                    assign(scale_iq, Util.cond(task == 0, 1.0, 0.125))
                    assign(i0_center, Util.cond(task == 0, 0.0, i0_center))
                    assign(q0_center, Util.cond(task == 0, 0.0, q0_center))

                    # # I-Q scans are done with no mixer correction!
                    # update_correction(elements_names.iq_mixer, 1.0, 0.0, 0.0, 1.0)

                    assign(best_lo_power, 7.96875)
                    with for_(
                        i0_offset, -self._lo_range / 2, i0_offset <= self._lo_range / 2, i0_offset + self._lo_step
                    ):
                        with for_(
                            q0_offset, -self._lo_range / 2, q0_offset <= self._lo_range / 2, q0_offset + self._lo_step
                        ):
                            assign(i0_curr, i0_offset * scale_iq + i0_center)
                            assign(q0_curr, q0_offset * scale_iq + q0_center)
                            read_lo_and_image_power()

                            with if_(lo_power < best_lo_power):
                                assign(i0_best, i0_curr)
                                assign(q0_best, q0_curr)
                                assign(best_lo_power, lo_power)

                            save(i0_curr, SavedVariablesNames.i_scan)
                            save(q0_curr, SavedVariablesNames.q_scan)

                            save(lo_power, SavedVariablesNames.lo)

                    assign(i0_center, Util.cond(task == 1, i0_best, 0.0))
                    assign(q0_center, Util.cond(task == 1, q0_best, 0.0))

                    with if_(task == 0):
                        measure("Analyze", elements_names.lo_analyzer, "lo_adc_data")

                with else_():

                    with if_(task < 4):

                        assign(scale_cal, 1.0)
                        assign(scale_gp, Util.cond(task == 2, params.if_amplitude * 8, params.if_amplitude))
                        assign(i0_curr, 0.0)
                        assign(q0_curr, 0.0)

                        pause()
                        assign(g_center, IO1)
                        assign(p_center, IO2)

                        with for_(
                            g_offset,
                            -self._image_range / 2,
                            g_offset <= self._image_range / 2,
                            g_offset + self._image_step,
                        ):
                            with for_(
                                p_offset,
                                -self._image_range / 2,
                                p_offset <= self._image_range / 2,
                                p_offset + self._image_step,
                            ):
                                assign(g_curr, g_offset * scale_gp + g_center)
                                assign(p_curr, p_offset * scale_gp + p_center)

                                update_correction_g_phi()

                                read_lo_and_image_power()

                                save(g_curr, SavedVariablesNames.g_scan)
                                save(p_curr, SavedVariablesNames.p_scan)

                                save(image_power, SavedVariablesNames.image)

                    with else_():
                        assign(go_on, False)

        return cast(Program, prog)

    def _set_octave_for_calibration(
        self, output_channel_index: int, params: AutoCalibrationParams, element_input: UpconvertedInput
    ) -> Tuple[float, List[SingleUpdate]]:
        current_state = self._low_level_client.aquire_modules(
            modules=[
                ModuleReference(type=OctaveModule.OCTAVE_MODULE_RF_UPCONVERTER, index=1),
                ModuleReference(type=OctaveModule.OCTAVE_MODULE_RF_UPCONVERTER, index=2),
                ModuleReference(type=OctaveModule.OCTAVE_MODULE_RF_UPCONVERTER, index=3),
                ModuleReference(type=OctaveModule.OCTAVE_MODULE_RF_UPCONVERTER, index=4),
                ModuleReference(type=OctaveModule.OCTAVE_MODULE_RF_UPCONVERTER, index=5),
                ModuleReference(type=OctaveModule.OCTAVE_MODULE_RF_DOWNCONVERTER, index=CALIBRATION_INPUT),
                ModuleReference(type=OctaveModule.OCTAVE_MODULE_IF_DOWNCONVERTER, index=CALIBRATION_INPUT),
            ]
        ).state.updates

        state_restore_updates = [
            current_state[5],  # take RF-downconverter #2 as is
            current_state[6],  # take IF-downconverter #2 as is
            SingleUpdate(
                synth=SynthUpdate(
                    index=4,
                    synth_output=SynthUpdateSynthOutput(disabled=True),
                    gain=0,
                    digital_attn=63,
                    main_output=SynthUpdateMainOutput.MAIN_OUTPUT_OFF,
                    secondary_output=SynthUpdateSecondaryOutput.SECONDARY_OUTPUT_OFF,
                )
            ),
        ]
        for upconverter_index in (1, 2, 3, 4, 5):
            upconverter_state = current_state[upconverter_index - 1].rf_up_conv
            state_restore_updates.append(
                SingleUpdate(
                    rf_up_conv=RfUpConvUpdate(
                        index=upconverter_index,
                        enabled=upconverter_state.enabled,
                        mixer_output_attn=upconverter_state.mixer_output_attn,
                        power_amp_attn=upconverter_state.power_amp_attn,
                        fast_switch_mode=upconverter_state.fast_switch_mode,
                    )
                )
            )

        restore_lo_frequency = element_input.lo_frequency

        if params.external_loopback:
            rf_input = RfDownConvUpdateRfInput.RF_INPUT_MAIN
        else:
            rf_input = {
                1: RfDownConvUpdateRfInput.RF_INPUT_DEBUG_1,
                2: RfDownConvUpdateRfInput.RF_INPUT_DEBUG_2,
                3: RfDownConvUpdateRfInput.RF_INPUT_DEBUG_3,
                4: RfDownConvUpdateRfInput.RF_INPUT_DEBUG_4,
                5: RfDownConvUpdateRfInput.RF_INPUT_DEBUG_5,
            }[output_channel_index]

        # Shut down all the over up-converters while doing the calibration
        updates = [
            SingleUpdate(
                rf_down_conv=RfDownConvUpdate(
                    index=CALIBRATION_INPUT,
                    enabled=True,
                    lo_input=RfDownConvUpdateLoInput.LO_INPUT_1
                    if params.use_main_lo
                    else RfDownConvUpdateLoInput.LO_INPUT_2,
                    rf_input=rf_input,
                )
            ),
            SingleUpdate(
                synth=SynthUpdate(
                    index=4,
                    gain=0xFFFF,
                    synth_output_power=SynthUpdateSynthOutputPower.SYNTH_OUTPUT_POWER_POS5DB,
                    main_output=SynthUpdateMainOutput.MAIN_OUTPUT_MAIN
                    if params.use_main_lo
                    else SynthUpdateMainOutput.MAIN_OUTPUT_OFF,
                    secondary_output=SynthUpdateSecondaryOutput.SECONDARY_OUTPUT_OFF,
                )
            ),
            SingleUpdate(
                if_down_conv=IfDownConvUpdate(
                    index=CALIBRATION_INPUT,
                    channel1=IfDownConvUpdateChannel(
                        mode=IfDownConvUpdateMode.MODE_BYPASS
                        if params.dconv_quadrature != DConvQuadrature.I
                        else IfDownConvUpdateMode.MODE_OFF,
                        coupling=IfDownConvUpdateCoupling.COUPLING_AC,
                    ),
                    channel2=IfDownConvUpdateChannel(
                        mode=IfDownConvUpdateMode.MODE_BYPASS
                        if params.dconv_quadrature != DConvQuadrature.Q
                        else IfDownConvUpdateMode.MODE_OFF,
                        coupling=IfDownConvUpdateCoupling.COUPLING_AC,
                    ),
                )
            ),
        ]

        for index in (1, 2, 3, 4, 5):
            if index != output_channel_index:
                updates.append(
                    SingleUpdate(
                        rf_up_conv=RfUpConvUpdate(
                            index=index,
                            mixer_output_attn=63,
                            power_amp_attn=63,
                            fast_switch_mode=RfUpConvUpdateFastSwitchMode.FAST_SWITCH_MODE_OFF,
                        )
                    )
                )
            else:
                updates.append(
                    SingleUpdate(
                        rf_up_conv=RfUpConvUpdate(
                            index=index,
                            fast_switch_mode=RfUpConvUpdateFastSwitchMode.FAST_SWITCH_MODE_ON,
                            enabled=True
                            # YR - I added the enabled update to make the assertion down the code pass
                        )
                    )
                )

        self._low_level_client.update(updates=updates)
        return restore_lo_frequency, state_restore_updates

    def _set_if_freq(self, element_names: CalibrationElementsNames, if_freq: Number, down_mixer_offset: Number) -> None:
        element_name_to_if_freq = {
            element_names.iq_mixer: if_freq,
            element_names.signal_analyzer: if_freq - down_mixer_offset,
            element_names.lo_analyzer: -down_mixer_offset,
            element_names.image_analyzer: -if_freq - down_mixer_offset,
        }
        for element_name, freq_to_set in element_name_to_if_freq.items():
            self._calibration_elements[element_name].set_intermediate_frequency(freq_to_set)

    @staticmethod
    def _set_input_lo_frequency(element_input: UpconvertedInput, lo_freq: Number) -> None:
        """Even if the LO source is external, we will have to update the attenuators."""
        try:
            element_input.set_lo_frequency(lo_freq, set_source=False)
        except (UnableToSetFrequencyError, InvalidLoSource):
            element_input.inform_element_about_lo_frequency(lo_freq)
            if element_input.lo_frequency != lo_freq:
                logger.warning(
                    "Could not set the external LO frequency to the desired value, "
                    "make sure to calibrate the declared LO frequency."
                )

    def _set_before_coarse_scan(
        self,
        element_input: UpconvertedInput,
        lo_freq: Number,
        names: CalibrationElementsNames,
        offset_frequency: float,
    ) -> None:

        self._set_input_lo_frequency(element_input, lo_freq)
        self._client.rf_inputs[2].set_lo_source(source_name=RFInputLOSource.Internal, ignore_shared_errors=True)
        self._client.rf_inputs[2].set_lo_frequency(
            source_name=RFInputLOSource.Internal, frequency=lo_freq + offset_frequency
        )

        # IQ-mixer set to 0
        iq_mixer_elem = self._calibration_elements[names.iq_mixer]
        assert isinstance(iq_mixer_elem.input, UpconvertedInput)
        iq_mixer_elem.input.set_output_dc_offset(i_offset=0.0, q_offset=0.0)
        self._set_if_freq(names, 50.0e6, down_mixer_offset=offset_frequency)

    def _perform_coarse_iq_scan(
        self, job: RunningQmJob, n_lo: int, lo_offset: int
    ) -> Tuple[Array, Array, List[LOAnalysisDebugData], Array]:
        self._qm.set_io1_value(0)
        job.resume()
        i0_coarse, q0_coarse, debug_coarse = _get_and_analyze_lo_data(job, n_lo, lo_offset, 1)

        lo_adc_data_input1 = job.result_handles.get("lo_adc_data_input1")
        lo_adc_data_input2 = job.result_handles.get("lo_adc_data_input2")
        assert lo_adc_data_input1 is not None
        assert lo_adc_data_input2 is not None

        lo_adc_data_input1.wait_for_values(1)
        lo_adc_data_input2.wait_for_values(1)
        lo_adc_data = np.array(
            [
                lo_adc_data_input1.fetch(slice(0, 1), flat_struct=True),
                lo_adc_data_input2.fetch(slice(0, 1), flat_struct=True),
            ]
        )
        return i0_coarse, q0_coarse, debug_coarse, lo_adc_data

    def _perform_fine_iq_scan(
        self,
        job: RunningQmJob,
        n_lo: int,
        lo_offset: int,
    ) -> Tuple[Array, Array, List[LOAnalysisDebugData]]:
        self._qm.set_io1_value(1)

        for _ in range(2):
            job.resume()
            while not job.is_paused():
                time.sleep(0.001)

        i0_shift, q0_shift, debug_fine = _get_and_analyze_lo_data(job, n_lo, lo_offset, 2)
        return i0_shift, q0_shift, debug_fine

    def _restore_octave_state(
        self,
        element_input: UpconvertedInput,
        restore_lo_frequency: float,
        state_restore_updates: List[SingleUpdate],
    ) -> None:
        self._low_level_client.update(state_restore_updates)
        self._set_input_lo_frequency(element_input, restore_lo_frequency)

    def calibrate(
        self,
        element: Element[QuaConfigMixInputs],
        lo_if_dict: Mapping[float, Tuple[float, ...]],
        params: AutoCalibrationParams,
    ) -> MixerCalibrationResults:
        if not isinstance(element.input, UpconvertedInput):
            raise CantCalibrateElementError(
                f"Element {element.name} has input of type {type(element.input)} and is not connected to an Octave. "
                f"Hence, it cannot be calibrated."
            )

        t_start = time.time()
        octave = self._client

        octave_port = element.input.port

        port_idx = octave_port[1]

        restore_lo_frequency, state_restore_updates = self._set_octave_for_calibration(port_idx, params, element.input)

        names = CalibrationElementsNames(self._low_level_client.octave_name, port_idx)

        compiled = self._qm.compile(self._generate_program(names, params))

        n_lo_samples, n_image_samples = self._n_lo, self._n_image

        # Now we go through the LO frequencies. For each LO we calibrate the DC
        # offsets, and then calibrate the image for each if freq.
        result = {}
        start_lo_sweep = time.time()
        logger.debug(f"time to start LO sweep {start_lo_sweep - t_start}")
        iq_mixer_elem = self._calibration_elements[names.iq_mixer]
        analyzer_elem = self._calibration_elements[names.lo_analyzer]
        assert isinstance(iq_mixer_elem.input, UpconvertedInput)

        for lo_freq in lo_if_dict:
            t0_lo = time.time()
            logger.debug(f"Calibrating {lo_freq / 1e9:0.3f} GHz")

            pending_job = self._qm.queue.add_compiled(compiled)
            job = pending_job.wait_for_execution()
            lo_offset, image_offset = 0, 0

            while not job.is_paused():
                time.sleep(0.01)

            # Let's look if there is a previous calibration value (to compate with at the end)
            prev_lo_cal = None

            logger.debug(f"Calibrating {lo_freq / 1e9:0.3f} GHz")
            self._set_before_coarse_scan(element.input, lo_freq, names, params.offset_frequency)

            analyzer_elem.set_input_dc_offset("out1", 0.0)
            analyzer_elem.set_input_dc_offset("out2", 0.0)

            i0_coarse, q0_coarse, debug_coarse, lo_adc_data = self._perform_coarse_iq_scan(job, n_lo_samples, lo_offset)
            lo_offset += 1

            analyzer_elem.set_input_dc_offset("out1", -np.mean(lo_adc_data[0]) / 4096)
            analyzer_elem.set_input_dc_offset("out2", -np.mean(lo_adc_data[1]) / 4096)

            # The first scan is coarse and use to find a good starting point
            iq_mixer_elem.input.set_output_dc_offset(i_offset=i0_coarse[0], q_offset=q0_coarse[0])

            i0_shift, q0_shift, debug_fine = self._perform_fine_iq_scan(job, n_lo_samples, lo_offset)
            lo_offset += 2

            curr_lo_freq_result = LOFrequencyCalibrationResult(
                i0=i0_shift[0] + i0_coarse[0],
                q0=q0_shift[0] + q0_coarse[0],
                dc_gain=debug_coarse[0].corrections.dc_gain,
                dc_phase=debug_coarse[0].corrections.dc_phase,
                temperature=octave.rf_outputs[port_idx].get_temperature(),
                image={},
                debug=LOFrequencyDebugData(
                    prev_result=prev_lo_cal, power_amp_attn=None, coarse=debug_coarse, fine=debug_fine
                ),
            )

            iq_mixer_elem.input.set_output_dc_offset(i_offset=curr_lo_freq_result.i0, q_offset=curr_lo_freq_result.q0)

            logger.debug(f"Pre IF sweep time - {time.time() - t0_lo}")
            for if_freq in lo_if_dict[lo_freq]:
                prev_if_cal = None

                t0_if = time.time()
                logger.debug(f"if_freq = {if_freq / 1e6:0.1f} MHz")

                self._set_if_freq(names, float(if_freq), params.offset_frequency)

                # 2 - image scan
                self._qm.set_io1_value(2)
                job.resume()
                #  Set the initial guess for the gain and phase from the coarse DC scan
                coarse_gain, coarse_phase = curr_lo_freq_result.dc_gain, curr_lo_freq_result.dc_phase
                self._qm.set_io_values(value_1=coarse_gain, value_2=coarse_phase)
                logger.debug(f"coarse. gain = {coarse_gain:.5f}, phase = {coarse_phase:0.5f}")
                while not job.is_paused():
                    time.sleep(0.001)
                job.resume()

                gp_coarse = _get_and_analyze_image_data(job, n_image_samples, image_offset, 1)[0]
                image_offset += 1

                # prepare for fine scan
                self._qm.set_io1_value(3)
                job.resume()

                # Set the initial guess for the gain and phase from the coarse gate-phase scan
                coarse_gain, coarse_phase = gp_coarse.gain, gp_coarse.phase
                self._qm.set_io_values(value_1=coarse_gain, value_2=coarse_phase)
                logger.debug(f"coarse. gain = {coarse_gain:.5f}, phase = {coarse_phase:0.5f}")
                while not job.is_paused():
                    time.sleep(0.001)
                job.resume()

                gp_fine = _get_and_analyze_image_data(job, n_image_samples, image_offset, 1)[0]

                if abs(gp_fine.gain) > 0.3 or abs(gp_fine.phase) > 0.3:
                    logger.debug(
                        f"Failed to calibrate LO={lo_freq / 1e9:0.3f}GHz, IF={if_freq / 1e6:0.3f}MHz, "
                        f"setting to identity"
                    )
                    gp_fine.gain = 0.0
                    gp_fine.phase = 0.0

                curr_lo_freq_result.image[if_freq] = ImageResult(
                    prev_result=prev_if_cal, coarse=gp_coarse, fine=gp_fine
                )
                image_offset += 1
                logger.debug(f"fine. gain = {gp_fine.gain:.5f}, phase = {gp_fine.phase:0.5f}")

                logger.debug(f"Calibration for {lo_freq}, {if_freq} took {time.time() - t0_if}")

            result[(lo_freq, element.input.gain)] = curr_lo_freq_result

            self._qm.set_io1_value(4)
            job.resume()

            if params.callback is not None:
                curr_lo_freq_result.plugin_data = params.callback(lo_freq, curr_lo_freq_result)
            logger.debug(f"Calibration for LO {lo_freq} took {time.time() - t0_lo}")

        # set to previous state
        self._restore_octave_state(element.input, restore_lo_frequency, state_restore_updates)

        logger.debug(f"Total calibration sweep process took {time.time() - start_lo_sweep}")
        logger.debug(f"Total calibration process took {time.time() - t_start}")
        return result
