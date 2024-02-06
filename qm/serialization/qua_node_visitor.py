import betterproto

from qm.utils import list_fields


class QuaNodeVisitor:
    def _default_enter(self, node):
        return True

    def _default_leave(self, node):
        pass

    def _default_visit(self, node):
        for _, field in list_fields(node).items():
            self.__visit(field)

    def __call(self, name, node, t):
        attr_name = f"{t}_{name}".replace(".", "_")
        attr = getattr(self, attr_name, None)
        if attr:
            ret = attr(node)
            if t == "enter":
                return ret
        elif t == "enter":
            return self._default_enter(node)
        elif t == "leave":
            self._default_leave(node)
        elif t == "visit":
            self._default_visit(node)
        else:
            raise Exception(f"unknown call type {t}. only 'enter', 'leave' or 'visit' are supported")

    def __call_enter(self, name, node):
        return self.__call(name, node, "enter")

    def __call_visit(self, name, node):
        return self.__call(name, node, "visit")

    def __call_leave(self, name, node):
        return self.__call(name, node, "leave")

    def visit(self, node):
        type_name = type(node).__name__
        type_module = type(node).__module__
        type_fullname = f"{type_module}.{type_name}"
        if type_fullname == "qm.program.program.Program":
            return self.visit(node._program)

        if isinstance(node, betterproto.Message):
            self.__visit(node)
        else:
            raise Exception(f"Failed to find descriptor on {node}")

    def __visit(self, node):
        if not isinstance(node, betterproto.Message):
            if isinstance(node, list):
                for n in node:
                    self.__visit(n)
            return
        self._enter_visit_leave(node)

    def _enter_visit_leave(self, node):
        type_fullname = f"{type(node).__module__}.{type(node).__name__}"
        if self.__call_enter(type_fullname, node):
            self.__call_visit(type_fullname, node)
        self.__call_leave(type_fullname, node)
