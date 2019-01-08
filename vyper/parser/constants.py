import ast
import copy

from vyper.parser.expr import Expr
from vyper.parser.context import Context
from vyper.exceptions import (
    StructureException,
    TypeMismatchException
)
from vyper.types.types import (
    BaseType,
    ByteArrayType,
    parse_type
)
from vyper.utils import (
    is_instances,
    SizeLimits
)


class Constants(object):

    def __init__(self):
        self._constants = dict()

    def __contains__(self, key):
        return key in self._constants

    def unroll_constant(self, const, global_ctx):
        # const = self._constants[self.expr.id]

        ann_expr = None
        expr = Expr.parse_value_expr(const.value, Context(vars=None, global_ctx=global_ctx, origcode=const.source_code))
        annotation_type = parse_type(const.annotation.args[0], None, custom_units=global_ctx._custom_units, custom_structs=global_ctx._structs)

        fail = False

        if is_instances([expr.typ, annotation_type], ByteArrayType):
            if expr.typ.maxlen < annotation_type.maxlen:
                return const
            fail = True

        elif expr.typ != annotation_type:
            fail = True
            # special case for literals, which can be uint256 types as well.
            if is_instances([expr.typ, annotation_type], BaseType) and \
               [annotation_type.typ, expr.typ.typ] == ['uint256', 'int128'] and \
               SizeLimits.in_bounds('uint256', expr.value):
                fail = False

            elif is_instances([expr.typ, annotation_type], BaseType) and \
               [annotation_type.typ, expr.typ.typ] == ['int128', 'int128'] and \
               SizeLimits.in_bounds('int128', expr.value):
                fail = False

        if fail:
            raise TypeMismatchException('Invalid value for constant type, expected %r' % annotation_type, const.value)

        ann_expr = copy.deepcopy(expr)
        ann_expr.typ = annotation_type
        ann_expr.typ.is_literal = expr.typ.is_literal  # Annotation type doesn't have literal set.

        return ann_expr

    def add_constant(self, item, global_ctx):
        args = item.annotation.args
        if not item.value:
            raise StructureException('Constants must express a value!', item)
        if len(args) == 1 and isinstance(args[0], (ast.Subscript, ast.Name, ast.Call)) and item.target:
            c_name = item.target.id
            if global_ctx.is_valid_varname(c_name, item):
                self._constants[c_name] = self.unroll_constant(item, global_ctx)
        else:
            raise StructureException('Incorrectly formatted struct', item)

    def ast_is_constant(self, ast_node):
        return isinstance(ast_node, ast.Name) and ast_node.id in self._constants

    def is_constant_of_base_type(self, ast_node, base_types):
        base_types = (base_types) if not isinstance(base_types, tuple) else base_types
        valid = self.ast_is_constant(ast_node)
        if not valid:
            return False

        const = self._constants[ast_node.id]
        if isinstance(const.typ, BaseType) and const.typ.typ in base_types:
            return True

        return False

    def get_constant(self, const_name, context):
        """ Return unrolled const """

        # check if value is compatible with
        const = self._constants[const_name]

        if isinstance(const, ast.AnnAssign):  # Handle ByteArrays.
            expr = Expr(const.value, context).lll_node
            return expr

        # Other types are already unwrapped, no need
        return self._constants[const_name]
