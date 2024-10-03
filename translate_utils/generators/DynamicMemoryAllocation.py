from ..utils.symbol_table import SymbolTable as st


class DynamicMemoryAllocation():

    def __init__(self, func_vars: dict(), st: st, func_name: str) -> None:
        self.__func_vars = func_vars
        self.st = st
        self.f_name = func_name

    def generate(self):
        count = 0
        print(f'; Allocating memory for local variables')
        for var in self.__func_vars['local_var']:
            name = self.st.func_convert(var[0], self.f_name)
            # check if it is an array
            if var[0][-1] == '_':
                self.st.add_special_var(name)
            print(f'{str(name+":"):<9}\t.EQUATE {count}')
            # Increment the stack pointer value
            count += var[1]

        # Push two bytes to the stack for function's return address
        count += 2
        print(f'; Allocating memory for parameters and return value')
        for var in self.__func_vars['params'] + self.__func_vars['return']:
            name = self.st.func_convert(var, self.f_name)
            print(f'{str(name+":"):<9}\t.EQUATE {count}')
            count += 2
