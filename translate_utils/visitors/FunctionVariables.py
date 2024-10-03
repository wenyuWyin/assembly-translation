import ast


class FunctionVariableExtraction(ast.NodeVisitor):
    """
        We extract all the left hand side of the 
        local (function-level) assignments
    """

    def __init__(self) -> None:
        super().__init__()
        self.results = {'local_var': [], 'params': [], 'return': []}
        self.slicing_vars = set()

    def visit_Assign(self, node):
        if len(node.targets) != 1:
            raise ValueError("Only unary assignments are supported")

        # Add the slicing variable to slicing_vars sety if we encounter
        # a Subscript
        if isinstance(node.targets[0], ast.Subscript):
            self.slicing_vars.add(node.targets[0].slice.id)
            return

        var_name = node.targets[0].id

        # Ensure we don't add duplicate variable names
        all_var_name = [t[0] for t in self.results['local_var']]
        if (var_name in all_var_name or
                var_name in self.results['params']):
            return

        # If we encounter an assignment statement that initialized an array
        if var_name[-1] == '_':
            # If the array is initialized with a fixed length, give it
            # a size of length * 2
            if isinstance(node.value.right, ast.Constant):
                length = node.value.right.value * 2
            else:
                # Defaultly set the size of the array to 200, if it is of
                # variable length
                length = 200
        else:
            # Normal variables have a size of 2 bytes
            length = 2
        self.results['local_var'].append((node.targets[0].id, length))

    def visit_arg(self, node):
        self.results['params'].append(node.arg)

    def visit_Return(self, node):
        if not self.results['return']:
            self.results['return'].append('retVal')
