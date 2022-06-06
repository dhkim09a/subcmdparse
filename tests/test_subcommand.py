import argparse
import sys
from unittest import TestCase

from subcmdparse.subcmdparse import Subcommand, SubcommandParser


class TestSubcommand(TestCase):

    def test_basic(self):
        cmd = ''

        class CmdA(Subcommand):
            def on_parser_init(self, parser: argparse.ArgumentParser):
                pass

            def on_command(self, args):
                assert cmd == 'cmda'

        parser = SubcommandParser()

        parser.add_subcommands(CmdA())

        cmd = 'cmda'
        args = parser.parse_args([cmd])
        parser.exec_subcommands(args)

    def test_subcommand_naming(self):
        cmd = ''

        class CmdA(Subcommand):
            def on_parser_init(self, parser: argparse.ArgumentParser):
                pass

            def on_command(self, args):
                assert cmd == 'X'

        parser = SubcommandParser()

        parser.add_subcommands(CmdA(name='X'))

        cmd = 'X'
        args = parser.parse_args([cmd])
        parser.exec_subcommands(args)

    def test_multiple_subcommand_regs(self):
        cmd = ''

        class CmdA(Subcommand):
            def on_parser_init(self, parser: argparse.ArgumentParser):
                pass

            def on_command(self, args):
                assert cmd == 'cmda'

        class CmdB(Subcommand):
            def on_parser_init(self, parser: argparse.ArgumentParser):
                pass

            def on_command(self, args):
                assert cmd == 'cmdb'

        class CmdC(Subcommand):
            def on_parser_init(self, parser: argparse.ArgumentParser):
                pass

            def on_command(self, args):
                assert cmd == 'cmdc'

        parser = SubcommandParser()

        parser.add_subcommands(CmdA())
        parser.add_subcommands(CmdB(), CmdC())

        cmd = 'cmda'
        argsA = parser.parse_args([cmd])
        parser.exec_subcommands(argsA)

        cmd = 'cmdb'
        argsB = parser.parse_args([cmd])
        parser.exec_subcommands(argsB)

        cmd = 'cmdc'
        argsC = parser.parse_args([cmd])
        parser.exec_subcommands(argsC)

        cmd = 'cmda'
        parser.exec_subcommands(argsA)

    def test_argcomplete(self):
        cmd = ''

        class CmdA(Subcommand):
            def on_parser_init(self, parser: argparse.ArgumentParser):
                pass

            def on_command(self, args):
                assert cmd == 'cmda'

        parser = SubcommandParser(argcomplete=True)

        parser.add_subcommands(CmdA())

        cmd = 'cmda'
        args = parser.parse_args([cmd])
        parser.exec_subcommands(args)

    def test_help(self):
        cmd = ''

        class CmdA(Subcommand):
            def on_parser_init(self, parser: argparse.ArgumentParser):
                pass

            def on_command(self, args):
                pass

        parser = SubcommandParser()

        parser.add_subcommands(CmdA())

        cmd = '--help'

        try:
            args = parser.parse_args([cmd])
        except:
            pass

    def test_shared_argument(self):
        cmd = ''

        class CmdA(Subcommand):
            def on_parser_init(self, parser: argparse.ArgumentParser):
                pass

            def on_command(self, args):
                assert cmd == 'cmda'

                assert args.x

        parser = SubcommandParser()

        parser.add_argument('-x', action='store_true', shared=True)

        parser.add_subcommands(CmdA())

        # parser.add_argument('-y', action='store_true', shared=True)

        cmd = 'cmda'
        # args = parser.parse_args([cmd, '-x', '-y'])
        args = parser.parse_args([cmd, '-x'])
        parser.exec_subcommands(args)

    def test_subsubcommand(self):
        cmd = ''

        class SubSubCmd(Subcommand):
            def on_parser_init(self, parser: SubcommandParser):
                parser.add_argument('x', type=str)

            def on_command(self, args):
                assert args.x == 'arg'

        class SubCmd(Subcommand):
            def on_parser_init(self, parser: SubcommandParser):
                parser.add_subcommands(SubSubCmd())

            def on_command(self, args):
                pass

        parser = SubcommandParser()

        parser.add_subcommands(SubCmd())

        cmd = 'subcmd subsubcmd arg'.split()
        args = parser.parse_args(*[cmd])
        parser.exec_subcommands(args)

    def test_unknown_args(self):
        class SubCmdA(Subcommand):
            def on_parser_init(self, parser: SubcommandParser):
                parser.add_argument('foo')

            def on_command(self, args):
                assert args.foo == 'foo1'

        class SubCmdB(Subcommand):
            def on_parser_init(self, parser: SubcommandParser):
                parser.allow_unknown_args = True
                parser.add_argument('foo')

            def on_command(self, args, unknown_args=None):
                assert args.foo == 'foo1'
                assert isinstance(unknown_args, list)
                assert len(unknown_args) == 2
                assert unknown_args[0] == 'unknown'
                assert unknown_args[1] == 'args'

        parser = SubcommandParser()
        # parser.allow_unknown_args = True

        parser.add_subcommands(SubCmdA())
        parser.add_subcommands(SubCmdB())

        argv = sys.argv.copy()

        sys.argv[1:] = ['subcmda', 'foo1']

        parser.exec_subcommands()

        sys.argv[1:] = ['subcmda', 'foo1', 'unknown', 'args']

        try:
            parser.exec_subcommands()
        except:
            pass
        else:
            raise Exception('did not raise exception for unknown args')

        sys.argv[1:] = ['subcmdb', 'foo1', 'unknown', 'args']

        parser.exec_subcommands()

        sys.argv = argv
