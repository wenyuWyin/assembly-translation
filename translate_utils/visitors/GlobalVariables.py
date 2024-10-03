import ast


class GlobalVariableExtraction(ast.NodeVisitor):
    """ 
        We extract all the left hand side of the global (top-level) assignments
    """

    slicing_vars = set()

    def __init__(self) -> None:
        super().__init__()
        # Example: {var_name1: ('const', 42), var_name2: ('val', 10), var_name3: ('other')}
        self.results = {}

    def visit_Assign(self, node):
        if len(node.targets) != 1:
            raise ValueError("Only unary assignments are supported")

        # Call visit_Subscript() if assigning a value to an array element
        if isinstance(node.targets[0], ast.Subscript):
            GlobalVariableExtraction.slicing_vars.add(node.targets[0].slice.id)
            return
        var_name = node.targets[0].id

        if var_name in self.results.keys():
            return
        if var_name[0] == '_' and var_name[1:].isupper():
            self.results[var_name] = ('const', node.value.value)
        elif isinstance(node.value, ast.Constant):
            self.results[var_name] = ('val', node.value.value)
        elif var_name[-1] == '_':
            self.results[var_name] = ('arr', node.value.right.value * 2)
        else:
            self.results[var_name] = ('other')

    def visit_FunctionDef(self, node):
        """We do not visit function definitions, they are not global by definition"""
        pass
