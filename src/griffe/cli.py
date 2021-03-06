# Why does this file exist, and why not put this in `__main__`?
#
# You might be tempted to import things from `__main__` later,
# but that will cause problems: the code will get executed twice:
#
# - When you run `python -m griffe` python will execute
#   `__main__.py` as a script. That means there won't be any
#   `griffe.__main__` in `sys.modules`.
# - When you import `__main__` it will get executed again (as a module) because
#   there's no `griffe.__main__` in `sys.modules`.

"""Module that contains the command line application."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from griffe.encoders import Encoder
from griffe.extended_ast import extend_ast
from griffe.extensions import Extensions
from griffe.loader import AsyncGriffeLoader, GriffeLoader
from griffe.logger import get_logger

logger = get_logger(__name__)


def _print_data(data, output_file):
    if output_file is sys.stdout:
        print(data)
    else:
        with open(output_file, "w") as fd:
            print(data, file=fd)


async def _load_packages_async(packages, extensions, search_paths):
    loader = AsyncGriffeLoader(extensions=extensions)
    loaded = {}
    for package in packages:
        logger.info(f"Loading package {package}")
        try:
            module = await loader.load_module(package, search_paths=search_paths)
        except ModuleNotFoundError:
            logger.error(f"Could not find package {package}")
        else:
            loaded[module.name] = module
    return loaded


def _load_packages(packages, extensions, search_paths):
    loader = GriffeLoader(extensions=extensions)
    loaded = {}
    for package in packages:
        logger.info(f"Loading package {package}")
        try:
            module = loader.load_module(package, search_paths=search_paths)
        except ModuleNotFoundError:
            logger.error(f"Could not find package {package}")
        else:
            loaded[module.name] = module
    return loaded


def get_parser() -> argparse.ArgumentParser:
    """
    Return the program argument parser.

    Returns:
        The argument parser for the program.
    """
    parser = argparse.ArgumentParser(prog="griffe", add_help=False)
    parser.add_argument(
        "-A",
        "--async-loader",
        action="store_true",
        help="Whether to read files on disk asynchronously. "
        "Very large projects with many files will be processed faster. "
        "Small projects with a few files will not see any speed up.",
    )
    parser.add_argument(
        "-a",
        "--append-sys-path",
        action="store_true",
        help="Whether to append sys.path to search paths specified with -s.",
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=sys.stdout,
        help="Output file. Supports templating to output each package in its own file, with {{package}}.",
    )
    parser.add_argument(
        "-s",
        "--search",
        action="append",
        type=Path,
        help="Paths to search packages into.",
    )
    parser.add_argument("packages", metavar="PACKAGE", nargs="+", help="Packages to find and parse.")
    return parser


def main(args: list[str] | None = None) -> int:  # noqa: WPS231
    """
    Run the main program.

    This function is executed when you type `griffe` or `python -m griffe`.

    Arguments:
        args: Arguments passed from the command line.

    Returns:
        An exit code.
    """
    parser = get_parser()
    opts: argparse.Namespace = parser.parse_args(args)  # type: ignore

    logging.basicConfig(format="%(levelname)-10s %(message)s", level=logging.WARNING)  # noqa: WPS323

    output = opts.output

    per_package_output = False
    if isinstance(output, str) and output.format(package="package") != output:
        per_package_output = True

    search = opts.search
    if opts.append_sys_path:
        search.extend(sys.path)

    extend_ast()
    extensions = Extensions()

    if opts.async_loader:
        loop = asyncio.get_event_loop()
        coroutine = _load_packages_async(opts.packages, extensions=extensions, search_paths=search)
        packages = loop.run_until_complete(coroutine)
    else:
        packages = _load_packages(opts.packages, extensions=extensions, search_paths=search)

    if per_package_output:
        for package_name, data in packages.items():
            serialized = json.dumps(data, cls=Encoder, indent=2, full=True)
            _print_data(serialized, output.format(package=package_name))
    else:
        serialized = json.dumps(packages, cls=Encoder, indent=2, full=True)
        _print_data(serialized, output)

    return 0 if len(packages) == len(opts.packages) else 1
