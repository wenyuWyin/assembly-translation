from ..utils.symbol_table import SymbolTable as st


class StaticMemoryAllocation():

    def __init__(self, global_vars: dict(), st: st) -> None:
        self.__global_vars = global_vars
        self.st = st

    def generate(self):
        print('; Allocating Global (static) memory')
        for var_name, attrs in self.__global_vars.items():
            # reserving memory for variables in different groups (const, val, other)
            if attrs[0] == 'const':
                name = self.st.convert(var_name)
                self.st.add_special_var(name)
                print(f'{str(name+":"):<9}\t.EQUATE {attrs[1]}')
            elif attrs[0] == 'val':
                name = self.st.convert(var_name)
                self.st.add_special_var(name)
                print(f'{str(name+":"):<9}\t.WORD {attrs[1]}')
            elif attrs[0] == 'arr':
                name = self.st.convert(var_name)
                self.st.add_special_var(name)
                print(f'{str(name+":"):<9}\t.BLOCK {attrs[1]}')
            else:
                name = self.st.convert(var_name)
                print(f'{str(name+":"):<9}\t.BLOCK 2')
        return self.st
