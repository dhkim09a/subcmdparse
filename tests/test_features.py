import argparse
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
from unittest import TestCase

from subcmdparse import Subcommand, SubcommandParser
from subcmdparse.subcmdparse import (
    TolerableSubParsersAction,
    _UsageAllAction,
)
from subcmdparse.util import compile_shargs


class _NoopSubcmd(Subcommand):
    def on_parser_init(self, parser):
        pass

    def on_command(self, args):
        pass


class TestSubcommandConstruction(TestCase):
    def test_default_name_is_class_name_lower(self):
        class CmdFoo(Subcommand):
            def on_parser_init(self, parser):
                pass

            def on_command(self, args):
                pass

        c = CmdFoo()
        self.assertEqual(c.name, 'cmdfoo')

    def test_custom_name_overrides_default(self):
        c = _NoopSubcmd(name='alt')
        self.assertEqual(c.name, 'alt')

    def test_help_defaults_to_empty(self):
        c = _NoopSubcmd()
        self.assertEqual(c.help, '')

    def test_help_is_stored(self):
        c = _NoopSubcmd(help='hello')
        self.assertEqual(c.help, 'hello')

    def test_callbacks_stored(self):
        def init(parser):
            pass

        def cmd(args, unknown_args=None):
            return 'ok'

        def exc(e):
            return e

        c = _NoopSubcmd(cb_parser_init=init, cb_command=cmd, cb_exception=exc)
        self.assertIs(c.cb_parser_init, init)
        self.assertIs(c.cb_command, cmd)
        self.assertIs(c.cb_exception, exc)


class TestSubcommandParserAddHelp(TestCase):
    def test_add_help_defaults_true(self):
        parser = SubcommandParser()
        self.assertTrue(parser.add_help)

    def test_add_help_setter_removes_then_adds(self):
        parser = SubcommandParser()
        parser.add_help = False
        self.assertFalse(parser.add_help)
        parser.add_help = True
        self.assertTrue(parser.add_help)

    def test_add_help_setter_idempotent(self):
        parser = SubcommandParser()
        before = list(parser._actions)
        parser.add_help = True
        self.assertEqual(before, list(parser._actions))

    def test_no_add_help_at_construction(self):
        parser = SubcommandParser(add_help=False)
        self.assertFalse(parser.add_help)


class TestRemoveArgument(TestCase):
    def test_remove_by_option_string(self):
        parser = SubcommandParser(add_help=False)
        parser.add_argument('-x', action='store_true')
        parser.remove_argument('-x')
        self.assertNotIn('-x', parser._option_string_actions)

    def test_remove_by_dest(self):
        parser = SubcommandParser(add_help=False)
        parser.add_argument('-x', '--xray', dest='xray', action='store_true')
        parser.remove_argument('xray')
        # both option strings removed from map
        self.assertNotIn('-x', parser._option_string_actions)
        self.assertNotIn('--xray', parser._option_string_actions)


class TestCallbackHooks(TestCase):
    def test_cb_command_called_instead_of_on_command(self):
        captured = {}

        def cb(args, unknown_args=None):
            captured['ran'] = True
            return 'cb-ret'

        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                pass

            def on_command(self, args):
                raise AssertionError('on_command should not be called')

        parser = SubcommandParser()
        parser.add_subcommands(Cmd(cb_command=cb))
        result = parser.exec_subcommands(parser.parse_args(['cmd']))
        self.assertTrue(captured['ran'])
        self.assertEqual(result, 'cb-ret')

    def test_cb_parser_init_called_instead_of_on_parser_init(self):
        seen = {}

        def cb(parser):
            seen['parser'] = parser
            parser.add_argument('--y', type=int)

        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                raise AssertionError('on_parser_init should not be called')

            def on_command(self, args):
                return args.y

        parser = SubcommandParser()
        parser.add_subcommands(Cmd(cb_parser_init=cb))
        result = parser.exec_subcommands(parser.parse_args(['cmd', '--y', '7']))
        self.assertEqual(result, 7)
        self.assertIn('parser', seen)

    def test_cb_exception_catches_command_exception(self):
        def excp(e):
            return ('handled', type(e).__name__)

        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                pass

            def on_command(self, args):
                raise RuntimeError('boom')

        parser = SubcommandParser()
        parser.add_subcommands(Cmd(cb_exception=excp))
        result = parser.exec_subcommands(parser.parse_args(['cmd']))
        self.assertEqual(result, ('handled', 'RuntimeError'))

    def test_uncaught_exception_propagates(self):
        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                pass

            def on_command(self, args):
                raise ValueError('nope')

        parser = SubcommandParser()
        parser.add_subcommands(Cmd())
        with self.assertRaises(ValueError):
            parser.exec_subcommands(parser.parse_args(['cmd']))


class TestExecSubcommandsFromArgv(TestCase):
    def test_exec_without_parsed_args_uses_argv(self):
        captured = {}

        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                parser.add_argument('value')

            def on_command(self, args):
                captured['v'] = args.value

        parser = SubcommandParser()
        parser.add_subcommands(Cmd())

        saved = sys.argv.copy()
        try:
            sys.argv[1:] = ['cmd', 'hello']
            parser.exec_subcommands()
        finally:
            sys.argv = saved
        self.assertEqual(captured['v'], 'hello')


class TestNestedSubcommands(TestCase):
    def test_three_level_nesting(self):
        captured = {}

        class C(Subcommand):
            def on_parser_init(self, parser):
                parser.add_argument('val', type=int)

            def on_command(self, args):
                captured['val'] = args.val

        class B(Subcommand):
            def on_parser_init(self, parser):
                parser.add_subcommands(C())

            def on_command(self, args):
                pass

        class A(Subcommand):
            def on_parser_init(self, parser):
                parser.add_subcommands(B())

            def on_command(self, args):
                pass

        parser = SubcommandParser()
        parser.add_subcommands(A())
        parser.exec_subcommands(parser.parse_args(['a', 'b', 'c', '42']))
        self.assertEqual(captured['val'], 42)


class TestSharedArguments(TestCase):
    def test_shared_argument_seen_by_child(self):
        captured = {}

        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                pass

            def on_command(self, args):
                captured['x'] = args.x

        parser = SubcommandParser()
        parser.add_argument('-x', action='store_true', shared=True)
        parser.add_subcommands(Cmd())
        parser.exec_subcommands(parser.parse_args(['cmd', '-x']))
        self.assertTrue(captured['x'])

    def test_shared_argument_propagates_two_levels(self):
        captured = {}

        class Leaf(Subcommand):
            def on_parser_init(self, parser):
                pass

            def on_command(self, args):
                captured['x'] = args.x

        class Mid(Subcommand):
            def on_parser_init(self, parser):
                parser.add_subcommands(Leaf())

            def on_command(self, args):
                pass

        parser = SubcommandParser()
        parser.add_argument('-x', type=str, shared=True)
        parser.add_subcommands(Mid())
        parser.exec_subcommands(parser.parse_args(['mid', 'leaf', '-x', 'val']))
        self.assertEqual(captured['x'], 'val')

    def test_shared_group_required_argument(self):
        captured = {}

        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                pass

            def on_command(self, args):
                captured['v'] = args.v

        parser = SubcommandParser()
        group = parser.add_argument_group(shared=True)
        group.add_argument('--v', type=int, required=True)
        parser.add_subcommands(Cmd())
        parser.exec_subcommands(parser.parse_args(['cmd', '--v', '99']))
        self.assertEqual(captured['v'], 99)

    def test_shared_mutually_exclusive_enforced(self):
        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                pass

            def on_command(self, args):
                pass

        parser = SubcommandParser()
        group = parser.add_mutually_exclusive_group(shared=True)
        group.add_argument('-a', action='store_true')
        group.add_argument('-b', action='store_true')
        parser.add_subcommands(Cmd())
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()):
                parser.parse_args(['cmd', '-a', '-b'])


class TestUnknownArgs(TestCase):
    def test_unknown_args_passed_to_callback(self):
        captured = {}

        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                parser.allow_unknown_args = True
                parser.add_argument('foo')

            def on_command(self, args, unknown_args=None):
                captured['foo'] = args.foo
                captured['unknown'] = unknown_args

        parser = SubcommandParser()
        parser.add_subcommands(Cmd())
        parser.exec_subcommands(parser.parse_args(
            ['cmd', 'foo1', '--extra', 'thing']
        ))
        self.assertEqual(captured['foo'], 'foo1')
        self.assertEqual(captured['unknown'], ['--extra', 'thing'])

    def test_unknown_args_disabled_errors(self):
        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                parser.add_argument('foo')

            def on_command(self, args):
                pass

        parser = SubcommandParser()
        parser.add_subcommands(Cmd())
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()):
                parser.parse_args(['cmd', 'foo1', 'oops'])


class TestUsageAllAction(TestCase):
    def test_usage_all_walks_tree_and_exits(self):
        class Inner(Subcommand):
            def on_parser_init(self, parser):
                parser.add_argument('z')

            def on_command(self, args):
                pass

        class Outer(Subcommand):
            def on_parser_init(self, parser):
                parser.add_subcommands(Inner())

            def on_command(self, args):
                pass

        parser = SubcommandParser(prog='myprog')
        parser.add_subcommands(Outer())

        buf = io.StringIO()
        with self.assertRaises(SystemExit):
            with redirect_stdout(buf):
                parser.parse_args(['--usage-all'])
        output = buf.getvalue()
        # should mention prog usage for root and inner level
        self.assertIn('myprog', output)

    def test_no_usage_all_when_disabled(self):
        parser = SubcommandParser(add_help_all=False)
        self.assertNotIn('--usage-all', parser._option_string_actions)


class TestTolerableSubParsersAction(TestCase):
    def test_choices_property_returns_none(self):
        parser = SubcommandParser()
        parser.allow_unknown_args = True
        parser.add_subcommands(_NoopSubcmd(name='real'))
        parser._register_subcommands()
        for action in parser._actions:
            if isinstance(action, TolerableSubParsersAction):
                self.assertIsNone(action.choices)
                action.choices = ['ignored']
                self.assertIsNone(action.choices)
                return
        self.fail('TolerableSubParsersAction not found')


class TestSubcommandExecClassmethod(TestCase):
    def test_exec_passes_args(self):
        captured = {}

        class Cmd(Subcommand):
            def on_parser_init(self, parser):
                parser.add_argument('name')

            def on_command(self, args):
                captured['n'] = args.name
                return 'rv'

        # Subcommand.exec uses compile_shargs which produces positional/flag args
        result = Cmd.exec('hello')
        self.assertEqual(captured['n'], 'hello')
        self.assertEqual(result, 'rv')


class TestCompileShargs(TestCase):
    def test_positional_args_passthrough(self):
        cmdargs, shargs = compile_shargs('foo', 'bar')
        self.assertIn('foo', cmdargs)
        self.assertIn('bar', cmdargs)
        self.assertEqual(shargs, {})

    def test_kwargs_become_cli_flags(self):
        cmdargs, shargs = compile_shargs('foo', special=True)
        # boolean kwarg becomes a --flag in cmdargs, not in shargs
        self.assertIn('foo', cmdargs)
        self.assertIn('--special', cmdargs)
        self.assertEqual(shargs, {})

    def test_underscore_prefixed_kwargs_are_sh_args(self):
        cmdargs, shargs = compile_shargs('foo', _tty_out=False)
        self.assertEqual(cmdargs, ['foo'])
        self.assertIn('_tty_out', shargs)
        self.assertFalse(shargs['_tty_out'])


class TestRegisterValidation(TestCase):
    def test_non_subcommand_raises(self):
        parser = SubcommandParser()
        parser.add_subcommands(_NoopSubcmd())
        # corrupt the subcommands list
        parser.subcommands.append('not a subcommand')  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            parser._register_subcommands()
