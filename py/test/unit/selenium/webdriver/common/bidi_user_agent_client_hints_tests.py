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

"""Unit tests for the generated userAgentClientHints facade.

``clientHints`` is nullable-required: sending ``null`` clears a previous override, so
``None`` must reach the wire rather than be dropped. The dataclass fields are
snake_case and must serialize to the spec's camelCase keys.
"""

from selenium.webdriver.common.bidi.user_agent_client_hints import (
    BrandVersion,
    ClientHintsMetadata,
    UserAgentClientHints,
)


class FakeConnection:
    def __init__(self):
        self.commands = []

    def execute(self, cmd):
        payload = next(cmd)
        self.commands.append(payload)
        try:
            cmd.send({})
        except StopIteration as exc:
            return exc.value


def _send(**kwargs):
    conn = FakeConnection()
    UserAgentClientHints(conn).set_client_hints_override(**kwargs)
    (command,) = conn.commands
    assert command["method"] == "userAgentClientHints.setClientHintsOverride"
    return command["params"]


def test_metadata_serializes_to_camel_case_and_omits_unset_fields():
    hints = ClientHintsMetadata(
        brands=[BrandVersion(brand="SeleniumBrowser", version="1")],
        platform="SeleniumOS",
        platform_version="1.0",
        mobile=False,
        form_factors=["Mobile"],
    )

    assert _send(client_hints=hints, contexts=["ctx-1"]) == {
        "clientHints": {
            "brands": [{"brand": "SeleniumBrowser", "version": "1"}],
            "platform": "SeleniumOS",
            "platformVersion": "1.0",
            "mobile": False,
            "formFactors": ["Mobile"],
        },
        "contexts": ["ctx-1"],
    }


def test_none_clears_the_override_with_an_explicit_null():
    assert _send(client_hints=None, user_contexts=["uc-1"]) == {"clientHints": None, "userContexts": ["uc-1"]}


def test_global_override_sends_no_scoping_keys():
    assert _send(client_hints={"platform": "SeleniumOS"}) == {"clientHints": {"platform": "SeleniumOS"}}


def test_brand_version_omits_unset_fields_instead_of_sending_null():
    assert BrandVersion(brand="SeleniumBrowser").to_bidi_dict() == {"brand": "SeleniumBrowser"}
