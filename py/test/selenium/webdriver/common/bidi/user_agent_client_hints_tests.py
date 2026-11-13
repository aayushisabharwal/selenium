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

"""Browser tests for the public userAgentClientHints facade.

The facade is composed with the driver's BiDi connection rather than reached off the
driver, as the decision record on BiDi implementation boundaries prescribes. Every
assertion reads ``navigator.userAgentData`` from a real page, so a wrong wire key in
the facade's serialization fails here rather than only in a unit test of the payload.
"""

import pytest

from selenium.webdriver.common.bidi.user_agent_client_hints import (
    BrandVersion,
    ClientHintsMetadata,
    UserAgentClientHints,
)
from selenium.webdriver.common.window import WindowTypes

PAGE = "formPage.html"


def _client_hints(driver):
    driver.browsing_context  # start the BiDi session whose connection the facade uses
    return UserAgentClientHints(driver._websocket_connection)


def _fake_hints(platform):
    return ClientHintsMetadata(
        brands=[BrandVersion(brand="SeleniumBrowser", version="1")],
        platform=platform,
        mobile=True,
    )


def _user_agent_data(driver, pages, context_id):
    driver.switch_to.window(context_id)
    driver.get(pages.url(PAGE))
    return driver.execute_script(
        "const data = navigator.userAgentData;"
        "return {platform: data.platform, brand: data.brands[0].brand, mobile: data.mobile};"
    )


@pytest.mark.xfail_firefox(reason="Firefox does not implement userAgentClientHints")
def test_set_client_hints_override_with_contexts(driver, pages):
    context_id = driver.current_window_handle
    client_hints = _client_hints(driver)
    try:
        client_hints.set_client_hints_override(_fake_hints("SeleniumOS"), contexts=[context_id])
        assert _user_agent_data(driver, pages, context_id) == {
            "platform": "SeleniumOS",
            "brand": "SeleniumBrowser",
            "mobile": True,
        }
    finally:
        client_hints.set_client_hints_override(None, contexts=[context_id])


@pytest.mark.xfail_firefox(reason="Firefox does not implement userAgentClientHints")
def test_clear_client_hints_override(driver, pages):
    context_id = driver.current_window_handle
    initial_user_agent_data = _user_agent_data(driver, pages, context_id)

    client_hints = _client_hints(driver)
    try:
        client_hints.set_client_hints_override(_fake_hints("SeleniumOS"), contexts=[context_id])
        assert _user_agent_data(driver, pages, context_id)["platform"] == "SeleniumOS"
    finally:
        client_hints.set_client_hints_override(None, contexts=[context_id])

    assert _user_agent_data(driver, pages, context_id) == initial_user_agent_data


@pytest.mark.xfail_firefox(reason="Firefox does not implement userAgentClientHints")
def test_set_client_hints_override_with_user_contexts(driver, pages):
    original_window = driver.current_window_handle
    user_context = driver.browser.create_user_context()
    try:
        _client_hints(driver).set_client_hints_override(_fake_hints("UserContextOS"), user_contexts=[user_context])
        context_id = driver.browsing_context.create(type=WindowTypes.TAB, user_context=user_context)
        try:
            assert _user_agent_data(driver, pages, context_id)["platform"] == "UserContextOS"
        finally:
            driver.browsing_context.close(context_id)
    finally:
        driver.browser.remove_user_context(user_context)
        driver.switch_to.window(original_window)


# A global override outlives this test's contexts, so the driver is torn down afterwards
# rather than relying on the cleanup below surviving a mid-test failure.
@pytest.mark.needs_fresh_driver
@pytest.mark.xfail_firefox(reason="Firefox does not implement userAgentClientHints")
def test_set_client_hints_override_globally(driver, pages):
    context_id = driver.current_window_handle
    client_hints = _client_hints(driver)
    try:
        client_hints.set_client_hints_override(_fake_hints("GlobalOS"))
        assert _user_agent_data(driver, pages, context_id)["platform"] == "GlobalOS"

        later_context = driver.browsing_context.create(type=WindowTypes.TAB)
        try:
            assert _user_agent_data(driver, pages, later_context)["platform"] == "GlobalOS"
        finally:
            driver.browsing_context.close(later_context)
            driver.switch_to.window(context_id)
    finally:
        client_hints.set_client_hints_override(None)
