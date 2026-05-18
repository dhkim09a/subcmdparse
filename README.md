# subcmdparse

`argparse` extension for declarative subcommands. Each subcommand is a class with `on_parser_init(parser)` and `on_command(args)` hooks; a `SubcommandParser` ties them together and runs the right one based on `sys.argv`.

Adds nice-to-haves on top of stock `argparse`: a `--help-all` action that prints help for the whole tree, optional [`argcomplete`](https://pypi.org/project/argcomplete/) integration, tolerant subparser dispatch, and `allow_unknown_args` passthrough.

Python ≥ 3.7. Optional: `argcomplete`.

## Install

```bash
pip install -e .
```

## Quick start

```python
from subcmdparse import Subcommand, SubcommandParser


class Greet(Subcommand):
    def on_parser_init(self, parser):
        parser.add_argument("name")
        parser.add_argument("--shout", action="store_true")

    def on_command(self, args):
        msg = f"hello, {args.name}"
        print(msg.upper() if args.shout else msg)


class Echo(Subcommand):
    def on_parser_init(self, parser):
        parser.add_argument("text", nargs="+")

    def on_command(self, args):
        print(" ".join(args.text))


if __name__ == "__main__":
    p = SubcommandParser(prog="demo")
    p.add_subcommands(Greet(), Echo())
    p.exec_subcommands()
```

```
$ python demo.py greet Alice --shout
HELLO, ALICE
```

## API

```python
from subcmdparse import Subcommand, SubcommandParser
```

### `Subcommand`

Base class for a single subcommand. Override:

| Hook                                        | Purpose                                                                |
| ------------------------------------------- | ---------------------------------------------------------------------- |
| `on_parser_init(self, parser)`              | Add this subcommand's arguments to its own `ArgumentParser`.           |
| `on_command(self, args, unknown_args=None)` | Run when this subcommand is selected. `unknown_args` is populated when `allow_unknown_args=True`. |
| `on_exception(self, exc)` (optional)        | Custom error handler for exceptions raised inside `on_command`.        |

Class attributes you can set instead of constructor args: `name` (CLI name, defaults to class name lowercased), `help`, `description`, `allow_unknown_args`.

Subcommands can themselves contain nested `Subcommand`s — pass them to `SubcommandParser.add_subcommands` inside a parent's `on_parser_init`, or expose them via the class's nested-subcommands attribute.

### `SubcommandParser(*args, argcomplete=False, add_help_all=True, **kwargs)`

Subclass of `argparse.ArgumentParser`.

| Method / property                                                                         | Description                                                                |
| ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `add_subcommands(*subcommands, title=None, required=True, help=None, metavar='SUBCOMMAND')` | Register one or more `Subcommand` instances.                              |
| `parse_args(...)`                                                                         | As in `argparse`; also registers pending subcommands and runs `argcomplete`. |
| `exec_subcommands(parsed_args=None)`                                                      | Parse args (if not given) and dispatch to the selected subcommand's `on_command`. |
| `add_help` (read/write)                                                                   | Enable/disable the standard `-h/--help` after construction.                |
| `allow_unknown_args` (read/write)                                                         | When `True`, unrecognised args are passed to `on_command` instead of erroring. |
| `argcomplete`                                                                             | When `True`, calls `argcomplete.autocomplete(self)` during `parse_args`.   |
| `add_help_all`                                                                            | When `True` (default), exposes `--help-all` which prints help for every subcommand recursively. |
