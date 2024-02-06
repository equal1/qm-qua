from typing import List, Union

from betterproto.lib.google.protobuf import Value, ListValue

from qm.grpc.qua import QuaResultAnalysis

_RESULT_SYMBOL = "@re"


class _ResultAnalysis:
    def __init__(self, result_analysis: QuaResultAnalysis):
        super().__init__()
        self._result_analysis = result_analysis
        self._saves = []

    def get_outputs(self):
        names = []
        for save in self._saves:
            if save.tag is not None:
                names.append(save.tag)
        return names

    def save(self, tag, expression):
        for save in self._saves:
            if save.tag == tag:
                raise Exception("can not save two streams with the same tag")
        self._saves.append(_OutputStream(expression, ["save", tag], tag))

    def save_all(self, tag, expression):
        for save in self._saves:
            if save.tag == tag:
                raise Exception("can not save two streams with the same tag")
        self._saves.append(_OutputStream(expression, ["saveAll", tag], tag))

    def auto_save_all(self, tag, expression):
        for save in self._saves:
            if save.tag == tag:
                raise Exception("can not save two streams with the same tag")
        self._saves.append(_OutputStream(expression, ["saveAll", tag, "auto"], tag))

    def _to_list_value(self, from_list: List[Union[str, List[str]]]) -> ListValue:
        res = ListValue()
        for item in from_list:
            if isinstance(item, str):
                res.values.append(Value(string_value=item))
            elif isinstance(item, list):
                res.values.append(Value(list_value=self._to_list_value(item)))
        return res

    def _add_pipeline(self, output):
        proto_output = output._to_proto()
        value = self._to_list_value(proto_output)
        self._result_analysis.model.append(value)

    def generate_proto(self):
        for save in self._saves:
            self._add_pipeline(save)
        # print(self._result_analysis.model)

    def build(self):
        copy = QuaResultAnalysis()
        copy.CopyFrom(self._result_analysis)
        return copy


class _OutputStream(object):
    def __init__(self, input_stream, operator_array: List[str], tag):
        super().__init__()
        self._input_stream = input_stream
        self._operator_array = operator_array
        self.tag = tag

    def _to_proto(self) -> List[Union[List[str], str]]:
        return self._operator_array + [self._input_stream._to_proto()]

    def input_stream(self):
        return self._input_stream

    def set_input_stream(self, new_stream):
        self._input_stream = new_stream


class _Node(object):
    def __init__(self, input_stream, output):
        self._input_stream = input_stream
        self._outputs = [output]

    def input_stream(self):
        return self._input_stream

    def outputs(self):
        return self._outputs
