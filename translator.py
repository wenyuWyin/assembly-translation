import argparse
import ast
from translate_utils.visitors.GlobalVariables import GlobalVariableExtraction
from translate_utils.visitors.TopLevelProgram import TopLevelProgram
from translate_utils.visitors.GeneralizedProgram import GeneralizedProgram
from translate_utils.generators.StaticMemoryAllocation import StaticMemoryAllocation
from translate_utils.generators.EntryPoint import EntryPoint


def main():
    input_file, print_ast = process_cli()
    with open(input_file) as f:
        source = f.read()
    node = ast.parse(source)
    if print_ast:
        print(ast.dump(node, indent=2))
    else:
        process(input_file, node)


def process_cli():
    """"Process Command Line Interface options"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', help='filename to compile (.py)')
    parser.add_argument('--ast-only', default=False, action='store_true')
    args = vars(parser.parse_args())
    return args['f'], args['ast_only']


def process(input_file, root_node):
    print(f'; Translating {input_file}')
    general_level = GeneralizedProgram('tl_1')

    extractor = GlobalVariableExtraction()
    extractor.visit(root_node)

    general_level.slicing_vars = extractor.slicing_vars

    memory_alloc = StaticMemoryAllocation(extractor.results, general_level.st)
    print('; Branching to top level (tl) instructions')
    print('\t\tBR tl_1')
    general_level.st = memory_alloc.generate()
    general_level.visit(root_node)
    ep = EntryPoint(general_level.finalize())
    ep.generate()


if __name__ == '__main__':
    main()
