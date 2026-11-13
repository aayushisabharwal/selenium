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

Two failure modes are pinned here. A command whose CDDL declares its params inline
(``params: { ... }``) used to match nothing and was dropped without a diagnostic,
emitting an empty module class; it is now hoisted into a named type first. And a
dataclass method body spanning more than one line used to have only its first line
indented, which is a SyntaxError in the shipped module rather than a style nit.

The named-params path these must leave untouched is covered alongside them.
"""

import ast
import logging

import pytest
from generate_bidi import CddlModule, CddlParser, CddlTypeDefinition

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


MULTILINE_DATACLASS_METHOD = """\
fields = {"brand": self.brand}
return {key: value for key, value in fields.items() if value is not None}"""


def test_a_multiline_dataclass_method_body_is_indented_into_the_method():
    """A body emitted at column 0 is a SyntaxError in the shipped module, not a style nit."""
    definition = CddlTypeDefinition(module="example", name="BrandVersion", fields={"brand": "text"})

    code = definition.to_python_dataclass(
        {"dataclass_methods": {"BrandVersion": {"to_bidi_dict": MULTILINE_DATACLASS_METHOD}}}
    )

    ast.parse(code)
    assert "\n        return {key: value" in code
