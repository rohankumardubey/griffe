"""Tests for the [Google-style parser][griffe.docstrings.google]."""

from __future__ import annotations

import inspect

from griffe.dataclasses import Argument, Arguments, Class, Data, Docstring, Function, Module
from griffe.docstrings import google as parser
from griffe.docstrings.dataclasses import DocstringSectionKind


# =============================================================================================
# Helpers
def parse(docstring: str, parent: Module | Class | Function | Data | None = None, **parser_opts):
    """Parse a doctring.

    Arguments:
        docstring: The docstring to parse.
        parent: The docstring's parent object.
        **parser_opts: Additional options accepted by the parser.

    Returns:
        The parsed sections, and warnings.
    """
    docstring_object = Docstring(docstring, lineno=1, endlineno=None)
    docstring_object.endlineno = len(docstring_object.lines) + 1
    if parent:
        docstring_object.parent = parent
        parent.docstring = docstring_object
    warnings = []
    parser.warn = lambda _docstring, _offset, message: warnings.append(message)
    sections = parser.parse(docstring_object, **parser_opts)
    return sections, warnings


# =============================================================================================
# Markup flow (multilines, indentation, etc.)
def test_simple_docstring():
    """Parse a simple docstring."""
    sections, warnings = parse("A simple docstring.")
    assert len(sections) == 1
    assert not warnings


def test_multiline_docstring():
    """Parse a multi-line docstring."""
    sections, warnings = parse(
        """
        A somewhat longer docstring.

        Blablablabla.
        """
    )
    assert len(sections) == 1
    assert not warnings


def test_multiple_lines_in_sections_items():
    """Parse multi-line item description."""
    docstring = """
        Arguments:
            p (int): This argument
               has a description
              spawning on multiple lines.

               It even has blank lines in it.
                       Some of these lines
                   are indented for no reason.
            q (int):
              What if the first line is blank?
    """

    sections, warnings = parse(docstring)
    assert len(sections) == 1
    assert len(sections[0].value) == 2
    assert warnings
    for warning in warnings:
        assert "should be 4 * 2 = 8 spaces, not" in warning


def test_code_blocks():
    """Parse code blocks."""
    docstring = """
        This docstring contains a docstring in a code block o_O!

        ```python
        \"\"\"
        This docstring is contained in another docstring O_o!

        Parameters:
            s: A string.
        \"\"\"
        ```
    """

    sections, warnings = parse(docstring)
    assert len(sections) == 1
    assert not warnings


def test_indented_code_block():
    """Parse indented code blocks."""
    docstring = """
        This docstring contains a docstring in a code block o_O!

            \"\"\"
            This docstring is contained in another docstring O_o!

            Parameters:
                s: A string.
            \"\"\"
    """

    sections, warnings = parse(docstring)
    assert len(sections) == 1
    assert not warnings


def test_different_indentation():
    """Parse different indentations, warn on confusing indentation."""
    docstring = """
        Raises:
             StartAt5: this section's items starts with 5 spaces of indentation.
                  Well indented continuation line.
              Badly indented continuation line (will trigger a warning).

                      Empty lines are preserved, as well as extra-indentation (this line is a code block).
             AnyOtherLine: ...starting with exactly 5 spaces is a new item.
            AnyLine: ...indented with less than 5 spaces signifies the end of the section.
        """

    sections, warnings = parse(docstring)
    assert len(sections) == 2
    assert len(sections[0].value) == 2
    assert sections[0].value[0].description == (
        "this section's items starts with 5 spaces of indentation.\n"
        "Well indented continuation line.\n"
        "Badly indented continuation line (will trigger a warning).\n"
        "\n"
        "    Empty lines are preserved, as well as extra-indentation (this line is a code block)."
    )
    assert sections[1].value == "    AnyLine: ...indented with less than 5 spaces signifies the end of the section."
    assert len(warnings) == 1
    assert "should be 5 * 2 = 10 spaces, not 6" in warnings[0]


# =============================================================================================
# Annotations (general)
def test_parse_without_parent():
    """Parse a docstring without a parent function."""
    sections, warnings = parse(
        """
        Parameters:
            void: SEGFAULT.
            niet: SEGFAULT.
            nada: SEGFAULT.
            rien: SEGFAULT.

        Keyword Args:
            keywd: SEGFAULT.

        Exceptions:
            GlobalError: when nothing works as expected.

        Returns:
            Itself.
        """
    )

    assert len(sections) == 4
    assert len(warnings) == 6  # missing annotations for arguments and return
    for warning in warnings[:-1]:
        assert "argument" in warning
    assert "return" in warnings[-1]


def test_parse_without_annotations():
    """Parse a function docstring without signature annotations."""
    docstring = """
        Parameters:
            x: X value.

        Keyword Args:
            y: Y value.

        Returns:
            Sum X + Y + Z.
    """
    arguments = Arguments()
    arguments.add(Argument(name="x", annotation=None, kind=inspect.Parameter.POSITIONAL_ONLY, default=None))
    arguments.add(Argument(name="y", annotation=None, kind=inspect.Parameter.POSITIONAL_ONLY, default=None))
    function = Function("func", arguments=arguments)

    sections, warnings = parse(docstring, function)
    assert len(sections) == 3
    assert len(warnings) == 3
    for warning in warnings[:-1]:
        assert "argument" in warning
    assert "return" in warnings[-1]


def test_parse_with_annotations():
    """Parse a function docstring with signature annotations."""
    docstring = """
        Parameters:
            x: X value.

        Keyword Arguments:
            y: Y value.

        Returns:
            Sum X + Y.
    """

    arguments = Arguments()
    arguments.add(Argument(name="x", annotation="int", kind=inspect.Parameter.POSITIONAL_ONLY, default=None))
    arguments.add(Argument(name="y", annotation="int", kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, default=None))
    function = Function("func", arguments=arguments, returns="int")

    sections, warnings = parse(docstring, function)
    assert len(sections) == 3
    assert not warnings


# =============================================================================================
# Sections (general)
def test_parse_attributes_section():
    """Parse Attributes sections."""
    docstring = """
        Attributes:
            hey: Hey.
            ho: Ho.
    """

    sections, warnings = parse(docstring)
    assert len(sections) == 1
    assert not warnings


def test_parse_examples_sections():
    """Parse a function docstring with examples."""
    docstring = """
        Examples:
            Some examples that will create a unified code block:

            >>> 2 + 2 == 5
            False
            >>> print("examples")
            "examples"

            This is just a random comment in the examples section.

            These examples will generate two different code blocks. Note the blank line.

            >>> print("I'm in the first code block!")
            "I'm in the first code block!"

            >>> print("I'm in other code block!")
            "I'm in other code block!"

            We also can write multiline examples:

            >>> x = 3 + 2
            >>> y = x + 10
            >>> y
            15

            This is just a typical Python code block:

            ```python
            print("examples")
            return 2 + 2
            ```

            Even if it contains doctests, the following block is still considered a normal code-block.

            ```python
            >>> print("examples")
            "examples"
            >>> 2 + 2
            4
            ```

            The blank line before an example is optional.
            >>> x = 3
            >>> y = "apple"
            >>> z = False
            >>> l = [x, y, z]
            >>> my_print_list_function(l)
            3
            "apple"
            False
        """

    arguments = Arguments()
    arguments.add(Argument(name="x", annotation="int", kind=inspect.Parameter.POSITIONAL_ONLY, default=None))
    arguments.add(Argument(name="y", annotation="int", kind=inspect.Parameter.POSITIONAL_ONLY, default=None))
    function = Function("func", arguments=arguments, returns="int")

    sections, warnings = parse(docstring, function)
    assert len(sections) == 1
    assert len(sections[0].value) == 9
    assert not warnings


def test_parse_yields_section():
    """Parse Yields section."""
    docstring = """
        Yields:
            int: Integers.
    """

    sections, warnings = parse(docstring)
    assert len(sections) == 1
    annotated = sections[0].value
    assert annotated.annotation == "int"
    assert annotated.description == "Integers."
    assert not warnings


def test_invalid_sections():
    """Warn on invalid (empty) sections."""
    docstring = """
        Parameters:
        Exceptions:
        Exceptions:

        Returns:
        Note:

        Important:
    """

    sections, warnings = parse(docstring)
    assert len(sections) == 1
    for warning in warnings[:3]:
        assert "Empty" in warning
    assert "Empty return section at line" in warnings[3]
    assert "Empty" in warnings[-1]


def test_close_sections():
    """Parse sections without blank lines in between."""
    docstring = """
        Parameters:
            x: X.
        Parameters:
            y: Y.

        Parameters:
            z: Z.
        Exceptions:
            Error2: error.
        Exceptions:
            Error1: error.
        Returns:
            1.
        Returns:
            2.
    """

    sections, warnings = parse(docstring)
    assert len(sections) == 7
    assert len(warnings) == 5  # no type or annotations


# =============================================================================================
# Arguments sections
def test_parse_args_and_kwargs():
    """Parse args and kwargs."""
    docstring = """
        Arguments:
            a (str): an argument.
            *args (str): args arguments.
            **kwargs (str): kwargs arguments.
    """

    sections, warnings = parse(docstring)
    assert len(sections) == 1
    expected_arguments = {"a": "an argument.", "*args": "args arguments.", "**kwargs": "kwargs arguments."}
    for argument in sections[0].value:
        assert argument.name in expected_arguments
        assert expected_arguments[argument.name] == argument.description
    assert not warnings


def test_parse_args_kwargs_keyword_only():
    """Parse args and kwargs."""
    docstring = """
        Arguments:
            a (str): an argument.
            *args (str): args arguments.

        Keyword Args:
            **kwargs (str): kwargs arguments.
    """

    sections, warnings = parse(docstring)
    assert len(sections) == 2
    expected_arguments = {"a": "an argument.", "*args": "args arguments."}
    for argument in sections[0].value:
        assert argument.name in expected_arguments
        assert expected_arguments[argument.name] == argument.description

    expected_arguments = {"**kwargs": "kwargs arguments."}
    for kwargument in sections[1].value:
        assert kwargument.name in expected_arguments
        assert expected_arguments[kwargument.name] == kwargument.description

    assert not warnings


def test_parse_types_in_docstring():
    """Parse types in docstring."""
    docstring = """
        Parameters:
            x (int): X value.

        Keyword Args:
            y (int): Y value.

        Returns:
            int: Sum X + Y + Z.
    """

    arguments = Arguments()
    arguments.add(Argument(name="x", annotation=None, kind=inspect.Parameter.POSITIONAL_ONLY, default=None))
    arguments.add(Argument(name="y", annotation=None, kind=inspect.Parameter.POSITIONAL_ONLY, default=None))
    function = Function("func", arguments=arguments, returns=None)

    sections, warnings = parse(docstring, function)
    assert len(sections) == 3
    assert not warnings

    assert sections[0].kind is DocstringSectionKind.arguments
    assert sections[1].kind is DocstringSectionKind.keyword_arguments
    assert sections[2].kind is DocstringSectionKind.returns

    (argx,) = sections[0].value  # noqa: WPS460
    (argy,) = sections[1].value  # noqa: WPS460
    returns = sections[2].value

    assert argx.name == "x"
    assert argx.annotation == "int"
    assert argx.description == "X value."
    assert argx.value is None

    assert argy.name == "y"
    assert argy.annotation == "int"
    assert argy.description == "Y value."
    assert argy.value is None

    assert returns.annotation == "int"
    assert returns.description == "Sum X + Y + Z."


def test_parse_optional_type_in_docstring():
    """Parse optional types in docstring."""
    docstring = """
        Parameters:
            x (int): X value.
            y (int, optional): Y value.

        Keyword Args:
            z (int, optional): Z value.
    """

    arguments = Arguments()
    arguments.add(Argument(name="x", annotation=None, kind=inspect.Parameter.POSITIONAL_ONLY, default="1"))
    arguments.add(Argument(name="y", annotation=None, kind=inspect.Parameter.POSITIONAL_ONLY, default="None"))
    arguments.add(Argument(name="z", annotation=None, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, default="None"))
    function = Function("func", arguments=arguments, returns=None)

    sections, warnings = parse(docstring, function)
    assert len(sections) == 2
    assert not warnings

    assert sections[0].kind is DocstringSectionKind.arguments
    assert sections[1].kind is DocstringSectionKind.keyword_arguments

    argx, argy = sections[0].value
    (argz,) = sections[1].value  # noqa: WPS460

    assert argx.name == "x"
    assert argx.annotation == "int"
    assert argx.description == "X value."
    assert argx.value == "1"

    assert argy.name == "y"
    assert argy.annotation == "int"
    assert argy.description == "Y value."
    assert argy.value == "None"

    assert argz.name == "z"
    assert argz.annotation == "int"
    assert argz.description == "Z value."
    assert argz.value == "None"


def test_prefer_docstring_types_over_annotations():
    """Prefer the docstring type over the annotation."""
    docstring = """
        Parameters:
            x (str): X value.

        Keyword Args:
            y (str): Y value.

        Returns:
            str: Sum X + Y + Z.
    """

    arguments = Arguments()
    arguments.add(Argument(name="x", annotation="int", kind=inspect.Parameter.POSITIONAL_ONLY, default=None))
    arguments.add(Argument(name="y", annotation="int", kind=inspect.Parameter.POSITIONAL_ONLY, default=None))
    function = Function("func", arguments=arguments, returns="int")

    sections, warnings = parse(docstring, function)
    assert len(sections) == 3
    assert not warnings

    assert sections[0].kind is DocstringSectionKind.arguments
    assert sections[1].kind is DocstringSectionKind.keyword_arguments
    assert sections[2].kind is DocstringSectionKind.returns

    (argx,) = sections[0].value  # noqa: WPS460
    (argy,) = sections[1].value  # noqa: WPS460
    returns = sections[2].value

    assert argx.name == "x"
    assert argx.annotation == "str"
    assert argx.description == "X value."

    assert argy.name == "y"
    assert argy.annotation == "str"
    assert argy.description == "Y value."

    assert returns.annotation == "str"
    assert returns.description == "Sum X + Y + Z."


def test_argument_line_without_colon():
    """Warn when missing colon."""
    docstring = """
        Parameters:
            x is an integer.
    """

    sections, warnings = parse(docstring)
    assert not sections  # getting x fails, so the section is empty and discarded
    assert len(warnings) == 2
    assert "pair" in warnings[0]
    assert "Empty" in warnings[1]


def test_argument_line_without_colon_keyword_only():
    """Warn when missing colon."""
    docstring = """
        Keyword Args:
            x is an integer.
    """

    sections, warnings = parse(docstring)
    assert not sections  # getting x fails, so the section is empty and discarded
    assert len(warnings) == 2
    assert "pair" in warnings[0]
    assert "Empty" in warnings[1]


# TODO: possible feature
# def test_extra_argument():
#     """Warn on extra argument in docstring."""
#     docstring = """
#         Parameters:
#             x: Integer.
#             y: Integer.
#     """

#     sections, warnings = parse(docstring)
#     assert len(sections) == 1
#     assert len(warnings) == 2


# TODO: possible feature
# def test_missing_argument():
#     """Warn on missing argument in docstring."""
#     docstring = """
#         Parameters:
#             x: Integer.
#     """

#     sections, warnings = parse(docstring)
#     assert len(sections) == 1
#     assert not warnings


# =============================================================================================
# Yields sections
def test_parse_yields_section_with_return_annotation():
    """Parse Yields section with a return annotation in the parent function."""
    docstring = """
        Yields:
            Integers.
    """

    function = Function(name="func", returns="Iterator[int]")
    sections, warnings = parse(docstring, function)
    assert len(sections) == 1
    annotated = sections[0].value
    assert annotated.annotation == "Iterator[int]"
    assert annotated.description == "Integers."
    assert not warnings


# =============================================================================================
# Parser special features
def test_replace_unknown_with_admonitions():
    """Replace unknown section with their Markdown admonition equivalent."""
    docstring = """
        Note:
            Hello.

        Note: With title.
            Hello again.

        Something:
            Something.
    """

    sections, warnings = parse(docstring)
    assert len(sections) == 1
    assert not warnings
    assert "!!! note" in sections[0].value
    assert '!!! note "' in sections[0].value
    assert "!!! something" in sections[0].value


# TODO: allow titles in section!
def test_replace_titled_unknown_with_admonitions():
    """Replace unknown section with their Markdown admonition equivalent, keeping their title."""
