# Licensed to the Software Freedom Conservancy (SFC) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The SFC licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""Unit tests for the CDDL facade generator (py/generate_bidi.py).

The generator finds commands with a pattern that expects a named params type
(``params: session.NewParameters``), which is how the core BiDi spec is written.
Adjacent specs may declare the params inline (``params: { ... }``), as ua-client-hints
does. Before the inline block was hoisted into a named type, such a command was
silently dropped and its module class was emitted empty. These tests pin the hoisting
and guard the named-params path it must leave untouched.
"""

import logging

import pytest
from generate_bidi import CddlModule, CddlParser

NAMED_PARAMS = """\
example.DoThingCommand = (
    method: "example.doThing",
    params: example.DoThingParameters
)

example.DoThingParameters = {
    target: example.Target / null,
    ? contexts: [+text],
}

example.Target = {
    id: text,
}
"""

INLINE_PARAMS = """\
example.DoThingCommand = {
    method: "example.doThing",
    params: {
        target: example.Target / null,
        ? contexts: [+text],
    }
}

example.Target = {
    id: text,
}
"""


TWO_INLINE_COMMANDS = """\
example.Commands = (
    (method: "example.first", params: { a: text }) //
    (method: "example.second", params: { b: text })
)
"""

INLINE_COMMAND_COLLIDING_WITH_A_NAMED_TYPE = (
    TWO_INLINE_COMMANDS
    + """
example.FirstParameters = {
    unrelated: text,
}
"""
)


@pytest.fixture
def parse(tmp_path):
    """Parse a CDDL snippet the way the build parses the merged spec file."""

    def _parse(cddl):
        spec = tmp_path / "spec.cddl"
        spec.write_text(cddl, encoding="utf-8")
        return CddlParser(str(spec)).parse()

    return _parse


@pytest.mark.parametrize("cddl", [NAMED_PARAMS, INLINE_PARAMS], ids=["named", "inline"])
def test_command_is_extracted_regardless_of_params_shape(parse, cddl):
    (command,) = parse(cddl)["example"].commands

    assert command.name == "doThing"
    assert command.params == {"target": "example.Target / null", "contexts": "[+text]"}
    assert command.required_params == {"target"}


def test_inline_params_are_hoisted_into_a_named_type(parse):
    module = parse(INLINE_PARAMS)["example"]

    params_type = next(t for t in module.types if t.name == "DoThingParameters")
    assert set(params_type.fields) == {"target", "contexts"}


def test_every_inline_params_block_in_a_definition_is_hoisted(parse):
    module = parse(TWO_INLINE_COMMANDS)["example"]

    assert [command.name for command in module.commands] == ["first", "second"]
    assert {t.name for t in module.types} == {"FirstParameters", "SecondParameters"}


def test_a_block_that_cannot_be_hoisted_is_skipped_without_losing_the_rest(parse, caplog):
    with caplog.at_level(logging.WARNING, logger="generate_bidi"):
        module = parse(INLINE_COMMAND_COLLIDING_WITH_A_NAMED_TYPE)["example"]

    assert [command.name for command in module.commands] == ["second"]
    assert "example.FirstParameters" in caplog.text


def test_excluding_a_modules_only_command_leaves_no_dangling_import(parse):
    code = parse(INLINE_PARAMS)["example"].generate_code({"exclude_methods": ["do_thing"]})

    assert "def do_thing(" not in code
    assert "command_builder" not in code


def test_module_without_commands_or_events_warns_instead_of_failing_silently(caplog):
    with caplog.at_level(logging.WARNING, logger="generate_bidi"):
        code = CddlModule(name="example").generate_code({})

    assert "    pass\n" in code
    assert "example" in caplog.text
