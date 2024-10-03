from .TopLevelProgram import TopLevelProgram
from .FunctionVariables import FunctionVariableExtraction
from ..generators.DynamicMemoryAllocation import DynamicMemoryAllocation
import ast


class GeneralizedProgram(TopLevelProgram):
    """We inherit from TopLevelProgram and support function calls"""

    def __init__(self, entry_point) -> None:
        super().__init__(entry_point)
        # store the name of the function that is currently being examined
        self.func_name = ''
        self.current_tl = 1     # store the id for the current function
        self.num_local_vars = 0

    ####
    # Handling function calls
    ####

    def visit_FunctionDef(self, node):
        self.func_name = node.name
        self.func_name = self.st.convert(self.func_name, True)

        # Initialize another instance of GeneralizedProgram to visit the
        # current FunctionDef
        func_visitor = GeneralizedProgram(self.func_name)
        func_visitor._update_const(self.st)
        func_visitor.st.update_labels(self.st.get_labels())

        # Initialize a functional variable extractor to extract
        # all parameters, local variables, and return variables
        var_extractor = FunctionVariableExtraction()
        var_extractor.visit(node)
        self.num_local_vars = sum(
            [t[1] for t in var_extractor.results['local_var']])
        self.slicing_vars = self.slicing_vars.union(var_extractor.slicing_vars)

        # check whether the function has return
        if var_extractor.results['return']:
            self._func_info[node.name] = True
        else:
            self._func_info[node.name] = False

        # Update the new function visitor's attribute to match the
        # current (general) visitor
        func_visitor._func_info.update(self._func_info)
        func_visitor.current_tl = self.current_tl
        func_visitor._elem_id = self._elem_id
        func_visitor._if_id = self._if_id
        func_visitor.num_local_vars = self.num_local_vars
        func_visitor.array_names = self.array_names

        # Output Pep9 code for local memory allocation
        memory_alloc = DynamicMemoryAllocation(
            var_extractor.results, func_visitor.st, node.name)
        memory_alloc.generate()

        func_visitor._in_function = True

        self.current_tl += 1

        # ======================= Translation begins here =======================
        self._record_instruction(f'BR tl_{self.current_tl}')
        func_visitor._stack_operation(self.num_local_vars, 1)

        for contents in node.body:
            func_visitor.visit(contents)

        if not self._func_info[node.name]:
            func_visitor._stack_operation(self.num_local_vars)
            func_visitor._record_instruction('RET')

        # Update the attributes of the general visitor to match the
        # FunctionDef visitor
        self._instructions += func_visitor._instructions
        self._elem_id = func_visitor._elem_id
        self._if_id = func_visitor._if_id

        self._record_instruction(
            'NOP1', label=f'tl_{self.current_tl}')

    def visit_Return(self, node):
        # Need to load value from an array element if return a subscript
        if isinstance(node.value, ast.Subscript):
            self._load_arr_val(node.value)
        else:
            self.visit(node.value)

        # Store the return value to the accumulator
        self._record_instruction(
            f'STWA {self.st.get_name("retVal")},s')
        self._stack_operation(self.num_local_vars)
        self._record_instruction('RET')

    ##################
    # Helper functions
    ##################

    def _stack_operation(self, byte: int, op: int = 0):
        # push and pop bytes from the stack
        # op: 1 - push from stack, 0 - pop to stack
        if not byte:
            return
        if op:
            self._record_instruction(f'SUBSP {byte},i')
            return
        self._record_instruction(f'ADDSP {byte},i')

    def _update_const(self, st):
        # Extract all constant variables
        const = st.identify_const()
        self.st.update_const(const)
