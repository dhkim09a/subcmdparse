# PYTHON_ARGCOMPLETE_OK

import argparse
from typing import Union, List
from gettext import gettext as _

from .util import compile_shargs

try:
    import argcomplete
except ImportError:
    pass


class TolerableSubParsersAction(argparse._SubParsersAction):
    @property
    def choices(self):
        return None

    @choices.setter
    def choices(self, val):
        pass

    def __call__(self, parser, namespace, values, *args, **kwargs):
        try:
            super().__call__(parser, namespace, values, *args, **kwargs)
        except argparse.ArgumentError:
            vars(namespace).setdefault(argparse._UNRECOGNIZED_ARGS_ATTR, [])
            getattr(namespace, argparse._UNRECOGNIZED_ARGS_ATTR).extend(values)


class SubcommandParser(argparse.ArgumentParser):
    subparsers = None
    subcommands: list = None
    parent_shared_parsers: List[argparse.ArgumentParser] = None
    shared_parser: argparse.ArgumentParser = None

    argcomplete: bool
    __allow_unknown_args: bool

    __unknown_args: list = None

    @property
    def allow_unknown_args(self) -> bool:
        return self.__allow_unknown_args

    @allow_unknown_args.setter
    def allow_unknown_args(self, val: bool):
        self.__allow_unknown_args = val

    def __init__(self, *args, argcomplete: bool = False, **kwargs):
        super().__init__(*args, **kwargs)

        self.argcomplete = argcomplete
        self.allow_unknown_args = False

    def add_subcommands(self, *subcommands, title=None, required=True, help=None, metavar='SUBCOMMAND'):
        if not self.subparsers:
            self.subparsers = self.add_subparsers(
                **{'title': title} if title else {},
                required=required,
                help=help,
                metavar=metavar,
                **{'action': TolerableSubParsersAction} if self.allow_unknown_args else {},
            )

        if not self.subcommands:
            self.subcommands = []

        self.subcommands.extend(list(subcommands))

    def _register_subcommands(self):
        if not self.subcommands:
            return
        for subcommand in self.subcommands:
            if not isinstance(subcommand, Subcommand):
                raise TypeError(str(subcommand.__class__) + 'is not Subcommand')
            subcommand._register(self.subparsers,
                                 parents=[*(self.parent_shared_parsers if self.parent_shared_parsers else []),
                                          *([self.shared_parser] if self.shared_parser else [])],
                                 )

    def try_argcomplete(self):
        if 'argcomplete' in globals():
            argcomplete.autocomplete(self)
        else:
            print('warning: install \'argcomplete\' package to enable bash autocomplete')

    def parse_args(self, *args, **kwargs) -> any:
        self._register_subcommands()
        if self.argcomplete:
            self.try_argcomplete()
        parsed_args, unknown_args = super().parse_known_args(*args, **kwargs)
        if unknown_args and not parsed_args._allow_unknown_args:
            msg = _('unrecognized arguments: %s')
            self.error(msg % ' '.join(unknown_args))
        self.__unknown_args = unknown_args
        return parsed_args

    def exec_subcommands(self, parsed_args: object = None):
        if not parsed_args:
            parsed_args = self.parse_args()

        if parsed_args._allow_unknown_args:
            parsed_args._func(parsed_args, unknown_args=self.__unknown_args)
        else:
            parsed_args._func(parsed_args)

    def add_argument(self, *args, shared: bool = False, **kwargs):
        if shared:
            if not self.shared_parser:
                self.shared_parser = argparse.ArgumentParser(add_help=False)

            # for myself
            super().add_argument(*args, **kwargs)
            # for my children
            return self.shared_parser.add_argument(*args, **kwargs)

        return super().add_argument(*args, **kwargs)

    def add_argument_group(self, *args, shared: bool = False, **kwargs) -> argparse._ArgumentGroup:
        if shared:
            if not self.shared_parser:
                self.shared_parser = argparse.ArgumentParser(add_help=False)

            # for myself
            super().add_argument_group(*args, **kwargs)
            # for my children
            return self.shared_parser.add_argument_group(*args, **kwargs)

        return super().add_argument_group(*args, **kwargs)

    def add_mutually_exclusive_group(self, *args, shared: bool = False, **kwargs) -> argparse._MutuallyExclusiveGroup:
        if shared:
            if not self.shared_parser:
                self.shared_parser = argparse.ArgumentParser(add_help=False)

            # for myself
            super().add_mutually_exclusive_group(*args, **kwargs)
            # for my children
            return self.shared_parser.add_mutually_exclusive_group(*args, **kwargs)

        return super().add_mutually_exclusive_group(*args, **kwargs)


class Subcommand:
    parser: SubcommandParser
    name: str
    help: str

    def on_parser_init(self, parser: SubcommandParser):
        raise NotImplementedError

    def on_command(self, args, unknown_args=None):
        raise NotImplementedError

    def _register(self, subparsers, parents: List[argparse.ArgumentParser] = None):
        kwargs = {'help': self.help}
        if parents:
            kwargs['parents'] = parents

        self.parser = subparsers.add_parser(self.name, **kwargs)
        self.parser.__class__ = SubcommandParser
        self.parser.parent_shared_parsers = parents
        self.on_parser_init(self.parser)
        self.parser._register_subcommands()
        self.parser.set_defaults(
            _func=self.on_command,
            _allow_unknown_args=self.parser.allow_unknown_args,
        )

    def __init__(self, subparsers = None, name: str = None, help: str = '', dependency: Union[str, List[str]] = ''):
        self.name = name if name else type(self).__name__.lower()
        self.help = help
        if subparsers:
            self._register(subparsers)

    @classmethod
    def exec(cls, *args, **kwargs):
        cmdargs, shargs = compile_shargs(*args, **kwargs)

        parser = SubcommandParser()
        parser.add_subcommands(cls(name='subcmd'))
        parserd_args = parser.parse_args(['subcmd', *cmdargs])

        parser.exec_subcommands(parserd_args)
