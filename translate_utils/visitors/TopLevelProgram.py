import ast
from ..utils.symbol_table import SymbolTable as st

LabeledInstruction = tuple[str, str]


class TopLevelProgram(ast.NodeVisitor):
    """We supports assignments and input/print calls"""

    def __init__(self, entry_point) -> None:
        super().__init__()
        self.st = st()     # symbol tables
        self.entry_point = entry_point
        self._instructions = list()
        self._record_instruction('NOP1', label=entry_point)
        self._should_save = True
        self._current_variable = None
        self._modify_index = False      # if the visitor is modifying an array index
        self._elem_id = 0     # id for while loops
        self._if_id = 0       # id for if-statements
        self._in_function = False       # if the visitor is visiting a function
        self._func_info = {}            # if each function has a return value
        self.slicing_vars = set()       # stores variables that are array indices
        self.array_names = set()        # stores names of arrays

    def finalize(self):
        self._instructions.append((None, '.END'))
        return self._instructions

    ####
    # Handling Assignments (variable = ...)
    ####

    def visit_Assign(self, node):
        # remembering the name of the target
        if isinstance(node.targets[0], ast.Subscript):
            # Example: word_[i] = data + key
            var_name = node.targets[0].value.id
            slicer = node.targets[0].slice.id
            # Load the index to the index register
            addressing_mode = self._identify_addressing_mode(slicer)
            self._record_instruction(
                f'LDWX {self.st.get_name(slicer)},{addressing_mode}')
            # Add instruction 'ASLX' if accessing the array
            self.visit(node.targets[0])
        else:
            var_name = node.targets[0].id
        self._current_variable = self.st.get_name(var_name)

        # Set _modify_index to true so that the following instructions are
        # done in the index register
        if var_name in self.slicing_vars:
            self._modify_index = True

        # Add its name to array_names set if encounter an array initializaation
        if var_name[-1] == '_':
            self.array_names.add(self.st.get_name(var_name))

        # visiting the left part, now knowing where to store the result
        if self.st.check_loaded(self._current_variable):
            self.st.remove_special_var(self._current_variable)
            return
        if TopLevelProgram._check_constant(self._current_variable):
            raise ValueError('Cannot reassign value to a constant')

        # Visit the RHS of an assignment
        self.visit(node.value)

        if self._should_save:
            addressing_mode = self._identify_addressing_mode(
                self._current_variable)
            if self._modify_index:
                # Store the value to the index register
                # if assigning value to index
                self._record_instruction(
                    f'STWX {self._current_variable},{addressing_mode}')
            else:
                self._record_instruction(
                    f'STWA {self._current_variable},{addressing_mode}')
        else:
            self._should_save = True

        self._current_variable = None
        self._modify_index = False

    def visit_Constant(self, node):
        if self._modify_index:
            self._record_instruction(f'LDWX {node.value},i')
        else:
            self._record_instruction(f'LDWA {node.value},i')

    def visit_Name(self, node):
        var_name = node.id
        addressing_mode = self._identify_addressing_mode(var_name)
        self._record_instruction(
            f'LDWA {self.st.get_name(node.id)},{addressing_mode}')

    def visit_BinOp(self, node):
        self._access_memory(node.left, 'LDWA')
        if isinstance(node.op, ast.Add):
            self._access_memory(node.right, 'ADDA')
        elif isinstance(node.op, ast.Sub):
            self._access_memory(node.right, 'SUBA')
        else:
            raise ValueError(f'Unsupported binary operator: {node.op}')

    def visit_Call(self, node):
        match node.func.id:
            case 'int':
                # Let's visit whatever is casted into an int
                self.visit(node.args[0])
            case 'input':
                # We are only supporting integers for now
                if self._in_function:
                    self._record_instruction(
                        f'DECI {self._current_variable},s')
                else:
                    self._record_instruction(
                        f'DECI {self._current_variable},d')
                self._should_save = False  # DECI already save the value in memory
            case 'print':
                # loading for printing an array element
                if isinstance(node.args[0], ast.Subscript):
                    slicer = self.st.get_name(node.args[0].slice.id)
                    s_mode = self._identify_addressing_mode(slicer)
                    self._record_instruction(f'LDWX {slicer},{s_mode}')
                    self._record_instruction('ASLX')
                    var_name = self.st.get_name(node.args[0].value.id)
                else:
                    # We are only supporting integers for now
                    var_name = self.st.get_name(node.args[0].id)
                addressing_mode = self._identify_addressing_mode(var_name)
                self._record_instruction(f'DECO {var_name},{addressing_mode}')
            case 'exit':
                self._record_instruction('STOP')
            case _:
                # Raise an error if the called function is not defined
                if node.func.id not in self._func_info:
                    raise ValueError(
                        f'Unsupported function call: {node.func.id}')
                has_return = self._func_info[node.func.id]
                params = node.args
                # Calculate the required space on the stack
                required_bytes = (len(params) + has_return) * 2

                # Load required parameters and store them onto the stack
                for i, param in enumerate(params):
                    self._access_memory(param, 'LDWA')
                    if not isinstance(param, ast.Constant) and param.id in self.slicing_vars:
                        self._record_instruction(
                            f'STWX {-(required_bytes - i*2)},s')
                    else:
                        self._record_instruction(
                            f'STWA {-(required_bytes - i*2)},s')

                # Push parameters and return values to the stack
                self._record_instruction(f'SUBSP {required_bytes},i')

                # Call the function
                self._record_instruction(
                    f'CALL {self.st.get_label(node.func.id)}')

                # Extract the returned value from the function if it has one
                if has_return:
                    self._record_instruction(f'ADDSP {required_bytes - 2},i')
                    self._record_instruction('LDWA 0,s')
                    # Pop from the stack
                    self._record_instruction('ADDSP 2,i')
                else:
                    self._record_instruction(f'ADDSP {required_bytes},i')

    ####
    # Handling While loops (only variable OP variable)
    ####

    def visit_While(self, node):
        loop_id = self._identify()
        inverted = {
            ast.Lt:  'BRGE',  # '<'  in the code means we branch if '>='
            ast.LtE: 'BRGT',  # '<=' in the code means we branch if '>'
            ast.Gt:  'BRLE',  # '>'  in the code means we branch if '<='
            ast.GtE: 'BRLT',  # '>=' in the code means we branch if '<'
            ast.NotEq: 'BREQ',  # '!=' in the code means we branch if '=='
            ast.Eq: 'BRNE',  # '==' in the code means we branch if '!='
        }
        # left part can only be a variable
        # loading an array element
        if isinstance(node.test.left, ast.Subscript):
            self._load_arr_val(node.test.left, f'test_{loop_id}')
        else:
            self._access_memory(node.test.left, 'LDWA',
                                label=f'test_{loop_id}')

        # loading from index register if the variable is used as the array's index
        if node.test.left.id in self.slicing_vars:
            self._access_memory(node.test.comparators[0], 'CPWX')
        else:
            # right part can only be a variable
            self._access_memory(node.test.comparators[0], 'CPWA')

        # Branching is condition is not true (thus, inverted)
        self._record_instruction(
            f'{inverted[type(node.test.ops[0])]} end_l_{loop_id}')
        # Visiting the body of the loop
        for contents in node.body:
            self.visit(contents)
        self._record_instruction(f'BR test_{loop_id}')
        # Sentinel marker for the end of the loop
        self._record_instruction(f'NOP1', label=f'end_l_{loop_id}')

    ####
    # Handling Conditional Statements (only variable OP variable)
    ####

    def visit_If(self, node):
        if_id = self._identify_if()
        inverted = {
            ast.Lt:  'BRGE',  # '<'  in the code means we branch if '>='
            ast.LtE: 'BRGT',  # '<=' in the code means we branch if '>'
            ast.Gt:  'BRLE',  # '>'  in the code means we branch if '<='
            ast.GtE: 'BRLT',  # '>=' in the code means we branch if '<'
            ast.NotEq: 'BREQ',  # '!=' in the code means we branch if '=='
            ast.Eq: 'BRNE'  # '==' in the code means we branch if '!='
        }
        # Load the variable that is being compared
        # loading an array element
        if isinstance(node.test.left, ast.Subscript):
            var_name = node.test.left.value.id
            self._load_arr_val(node.test.left, f'if_{if_id}')
        else:
            var_name = node.test.left.id
            self._access_memory(node.test.left, 'LDWA', label=f'if_{if_id}')

        # Compare in the index register if the variable is an array index
        if var_name in self.slicing_vars:
            self._access_memory(node.test.comparators[0], 'CPWX')
        else:
            self._access_memory(node.test.comparators[0], 'CPWA')

        # Record appropriate branching instruction if the if-statement has
        # else or elif
        if node.orelse:
            self._record_instruction(
                f'{inverted[type(node.test.ops[0])]} else_{if_id}')
        else:
            self._record_instruction(
                f'{inverted[type(node.test.ops[0])]} end_if_{if_id}')

        # Visit contents in the body of if
        for contents in node.body:
            self.visit(contents)

        # Branch to the end-if state
        self._record_instruction(f'BR end_if_{if_id}')

        # Visite contents in the body of else or elif
        if node.orelse:
            self._record_instruction('NOP1', label=f'else_{if_id}')
            for contents in node.orelse:
                self.visit(contents)
            self._record_instruction(f'BR end_if_{if_id}')

        self._record_instruction(f'NOP1', label=f'end_if_{if_id}')

    ####
    # Handling Array Slicing
    ####

    def visit_Subscript(self, node):
        self._record_instruction('ASLX')

    ####
    # Not handling function calls
    ####

    def visit_FunctionDef(self, node):
        """We do not visit function definitions, they are not top level"""
        pass

    ####
    # Helper functions to
    ####

    def _record_instruction(self, instruction, label=None):
        self._instructions.append((label, instruction))

    def _access_memory(self, node, instruction, label=None):
        if isinstance(node, ast.Constant):
            # Extract the value as an immediate if we encounter an ast.Constant instance
            instruction = self._identify_ldst(node.value, instruction)
            self._record_instruction(f'{instruction} {node.value},i', label)
        else:
            # instructions could be LDWA/LDWX, STWA/STWX, etc.
            instruction = self._identify_ldst(node.id, instruction)
            # identify the addressing mode based on current variable and current visitor state
            addressing_mode = self._identify_addressing_mode(node.id)
            self._record_instruction(
                f'{instruction} {self.st.get_name(node.id)},{addressing_mode}', label)

    def _identify(self):
        result = self._elem_id
        self._elem_id = self._elem_id + 1
        return result

    def _identify_if(self):
        result = self._if_id
        self._if_id += 1
        return result

    def _identify_addressing_mode(self, var_name: str):
        '''
            identify the appropriate addressing mode for the given variable
        '''
        if self._in_function and TopLevelProgram._check_constant(var_name):
            return 'i'
        # current variable is for an array and it is local
        elif self._in_function and var_name in self.array_names and var_name[2] == '_':
            return 'sx'
        elif var_name in self.array_names:
            return 'x'
        elif self._in_function:
            return 's'
        else:
            return 'd'

    def _identify_ldst(self, var_name: str, instruction: str):
        if var_name in self.slicing_vars or self._modify_index:
            # Perform all operations involving an array index in the index register
            return instruction[:-1] + 'X'
        else:
            return instruction

    def _load_arr_val(self, node, id=''):
        '''
            Load the value of an array slicing operation to the accumulator
        '''
        var_name = self.st.get_name(node.value.id)
        slicing_var = self.st.get_name(node.slice.id)
        s_addressing_mode = self._identify_addressing_mode(slicing_var)
        v_addressing_mode = self._identify_addressing_mode(var_name)
        if id:
            self._record_instruction(
                f'LDWX {slicing_var},{s_addressing_mode}', id)
        else:
            self._record_instruction(
                f'LDWX {slicing_var},{s_addressing_mode}')
        # ASLX
        self.visit_Subscript(node)
        self._record_instruction(
            f'LDWA {var_name},{v_addressing_mode}')

    @staticmethod
    def _check_constant(var_name: str) -> bool:
        # Check if a variable is a constant based on its name
        if len(var_name) == 1:
            return False
        return var_name[0] == '_' and var_name[1].isupper()
