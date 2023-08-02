# PYTHON_ARGCOMPLETE_OK

from __future__ import annotations

import argparse
from typing import Any, Optional, Union, List, Protocol, Callable, Type
from gettext import gettext as _

from .util import compile_shargs

try:
    import argcomplete
except ImportError:
    pass


class _Subcommand_on_command(Protocol):
    def __call__(self, args: object, unknown_args: Optional[object] = None) -> Any:
        pass


class _InternalSubcmdArgs(Protocol):
    _func: _Subcommand_on_command
    _allow_unknown_args: bool


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


class _UsageAllAction(argparse.Action):

    def __init__(self,
                 option_strings,
                 dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS,
                 help=None):
        super(_UsageAllAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)

    # def print_help(self, parser: argparse.ArgumentParser, file=None, indent=''):
    #     # message = parser.format_help()
    #     message = parser.format_usage()
    #     if indent:
    #         lines = message.split('\n')
    #         message = '\n'.join([indent + line for line in lines])
    #     parser._print_message(message, file)

    def __call__(self, parser: SubcommandParser, namespace, values, option_string=None):
        # depth first search
        stack: list[tuple[SubcommandParser, int]] = []
        stack.append((parser, 0))
        while stack and (elm := stack.pop()):
            parser, level = elm
            # self.print_help(parser, indent='  ' * level)
            # self.print_help(parser)
            parser.print_usage()
            if parser.subcommands:
                to_push = [(subcmd.parser, level + 1) for subcmd in parser.subcommands]
                to_push.reverse()
                stack.extend(to_push)
        parser.exit()


class SubcommandParser(argparse.ArgumentParser):
    subparsers: Optional[argparse._SubParsersAction] = None
    subcommands: Optional[list[Subcommand]] = None
    parent_shared_parsers: Optional[List[argparse.ArgumentParser]] = None
    shared_parser: Optional[argparse.ArgumentParser] = None

    argcomplete: bool
    __allow_unknown_args: bool
    add_help_all: bool

    __unknown_args: Optional[list] = None

    @property
    def allow_unknown_args(self) -> bool:
        return self.__allow_unknown_args

    @allow_unknown_args.setter
    def allow_unknown_args(self, val: bool):
        self.__allow_unknown_args = val

    def __init__(self, *args, argcomplete: bool = False, add_help_all: bool = True, **kwargs):
        super().__init__(*args, **kwargs)

        self.argcomplete = argcomplete
        self.allow_unknown_args = False
        self.add_help_all = add_help_all

        # add help argument if necessary
        # (using explicit default to override global argument_default)
        default_prefix = '-' if '-' in self.prefix_chars else self.prefix_chars[0]
        if self.add_help:
            self.add_argument(
                default_prefix*2+'usage'+default_prefix+'all',
                action=_UsageAllAction, default=argparse.SUPPRESS,
                help=_('show all subcommand usages recursively'))

    def add_subcommands(self, *subcommands: Subcommand, title: Optional[str] = None, required: bool = True, help: Optional[str] = None, metavar: str = 'SUBCOMMAND'):
        if not self.subparsers:
            kwargs = {}
            if title:
                kwargs['title'] = title
            if self.allow_unknown_args:
                kwargs['action'] = TolerableSubParsersAction
            self.subparsers = self.add_subparsers(
                required=required,
                help=help,
                metavar=metavar,
                **kwargs,
            )

        if not self.subcommands:
            self.subcommands = []

        self.subcommands.extend(list(subcommands))

    def _register_subcommands(self):
        if not self.subcommands:
            return
        
        # self.subparsers must not be None after self.add_subcommands()
        assert self.subparsers

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

    def parse_args(self, *args, **kwargs) -> _InternalSubcmdArgs:
        self._register_subcommands()
        if self.argcomplete:
            self.try_argcomplete()
        parsed_args, unknown_args = super().parse_known_args(*args, **kwargs)
        if unknown_args and not parsed_args._allow_unknown_args:
            msg = _('unrecognized arguments: %s')
            self.error(msg % ' '.join(unknown_args))
        self.__unknown_args = unknown_args
        return parsed_args

    def exec_subcommands(self, parsed_args: Optional[_InternalSubcmdArgs] = None):
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

            # # for myself
            # super().add_argument(*args, **kwargs)
            # for my children
            return self.shared_parser.add_argument(*args, **kwargs)

        return super().add_argument(*args, **kwargs)

    def add_argument_group(self, *args, shared: bool = False, **kwargs) -> argparse._ArgumentGroup:
        if shared:
            if not self.shared_parser:
                self.shared_parser = argparse.ArgumentParser(add_help=False)

            # for my children
            group = self.shared_parser.add_argument_group(*args, **kwargs)
            # # for myself
            # self._action_groups.append(group)

            return group

        return super().add_argument_group(*args, **kwargs)

    def add_mutually_exclusive_group(self, *args, shared: bool = False, **kwargs) -> argparse._MutuallyExclusiveGroup:
        if shared:
            if not self.shared_parser:
                self.shared_parser = argparse.ArgumentParser(add_help=False)

            # for my children
            group = self.shared_parser.add_mutually_exclusive_group(*args, **kwargs)
            # # for myself
            # self._mutually_exclusive_groups.append(group)

            return group

        return super().add_mutually_exclusive_group(*args, **kwargs)


class Subcommand:
    parser: SubcommandParser
    name: str
    help: str

    def on_parser_init(self, parser: SubcommandParser):
        raise NotImplementedError

    def on_command(self, args, unknown_args=None):
        raise NotImplementedError

    def _register(self, subparsers: argparse._SubParsersAction, parents: Optional[List[argparse.ArgumentParser]] = None):
        kwargs: dict[str, Any] = {'help': self.help}
        if parents:
            kwargs['parents'] = parents

        self.parser = subparsers.add_parser(self.name, **kwargs)
        self.parser.__class__ = SubcommandParser
        assert isinstance(self.parser, SubcommandParser)
        self.parser.parent_shared_parsers = parents
        self.on_parser_init(self.parser)
        self.parser._register_subcommands()
        self.parser.set_defaults(
            _func=self.on_command,
            _allow_unknown_args=self.parser.allow_unknown_args,
        )

    def __init__(self, subparsers: Optional[argparse._SubParsersAction] = None, name: Optional[str] = None, help: str = '', dependency: Union[str, List[str]] = ''):
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

