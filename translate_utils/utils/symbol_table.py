
class SymbolTable():
    '''
        Stores the variable's name with its corresponding converted name
    '''

    def __init__(self) -> None:
        self.__symbols = dict()
        # stores all variables that are constant
        self.__specialVar = set()
        # store all functions' name (label)
        self.__labels = dict()

    def get_name(self, name: str) -> str:
        return self.__symbols[name]

    def get_label(self, name: str) -> str:
        return self.__labels[name]

    def convert(self, name: str, label_conv=False) -> str:
        # Assign a unique identifier for the given variable name
        if len(name) <= 8:
            # If the length of the name is less than 9, simply use the
            # original name
            if not label_conv:
                return self.update_and_get(name, name)
            return self.update_and_get(name, name, True)

        # Extract the first 8 characters of the original name, continuously
        # change the last variable until the new name is not taken
        if name[-1] == "_":      # special case for array's name
            return self.update_and_get(name, name[-8:])

        new_name = name[:8]
        i = 0
        while new_name in list(self.__symbols.values()) + list(self.__labels.values()):
            new_name = name[:7] + chr(97 + (ord(name[7]) + i - 97) % 26)
            i += 1
        if not label_conv:
            return self.update_and_get(name, new_name)
        return self.update_and_get(name, new_name, True)

    def func_convert(self, name: str, f_name: str) -> str:
        '''
           Special function to do variable name conversion for local variable
           This method adapted a same algorithm as the convert(name) method,
           except that it attaches the actual variable name after the first
           two characters of the function name
        '''
        if len(name) <= 5:
            self.__symbols[name] = f'{f_name[:2]}_{name}'
            return self.get_name(name)

        if name[-1] == '_':
            return self.update_and_get(name, f'{f_name[:2]}_{name[-5:]}')

        new_name = f'{f_name[:2]}_{name[:5]}'
        i = 0
        while new_name in self.__symbols.values():
            new_name = new_name[:7] + \
                chr(97 + (ord(new_name[7]) + i - 97) % 26)
            i += 1
        self.__symbols[name] = new_name
        return self.get_name(name)

    def add_special_var(self, var_name: str) -> None:
        '''
            store the constant and the variable with known value
        '''
        self.__specialVar.add(var_name)

    def remove_special_var(self, var_name: str) -> None:
        '''
            remove var_name from the set
        '''
        self.__specialVar.remove(var_name)

    def check_loaded(self, var_name: str) -> bool:
        '''
            check whether the variable needs to allocate memory location
            (if var_name in the set)
        '''
        return var_name in self.__specialVar

    def identify_const(self):
        '''
            identify all constant variable names in variables that are stored
        '''
        const = []
        for o_name, n_name in self.__symbols.items():
            if (o_name[0] == '_' and o_name[1:].isupper()) or o_name[-1] == '_':
                const.append({o_name: n_name})
        return const

    def update_const(self, const):
        '''
            adapt all constant variables from another instance of the
            symbol table
        '''
        for c in const:
            self.__symbols.update(c)

    #######
    # Helper Functions
    #######

    def update_and_get(self, name: str, new_name: str, label: bool = False):
        '''
            Update the Pep/9 variable name of a Python name, addressing it as
            either a label or a name
        '''
        if label:
            self.__labels[name] = new_name
            return self.get_label(name)
        self.__symbols[name] = new_name
        return self.get_name(name)

    def get_labels(self):
        return self.__labels

    def update_labels(self, labels: dict[str: str]):
        self.__labels = labels
