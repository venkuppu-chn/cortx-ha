#!/usr/bin/env python3

# Copyright (c) 2021 Seagate Technology LLC and/or its Affiliates
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>. For any questions
# about this software or licensing, please email opensource@seagate.com or
# cortx-questions@seagate.com.

import os
import sys
import pathlib
import unittest
sys.path.append(os.path.join(os.path.dirname(pathlib.Path(__file__)), '..', '..', '..', '..'))
from cortx.utils.log import Log
from ha.core.event_manager.event_manager import EventManager
from ha.core.event_manager.const import SUBSCRIPTION_LIST
from ha.core.event_manager.subscribe_event import SubscribeEvent
from ha.core.system_health.const import HEALTH_STATUSES

class TestEventManager(unittest.TestCase):
    """
    Unit test for event manager
    """

    def setUp(self):
        Log.init(service_name='event_manager', log_path="/tmp", level="DEBUG")
        self.event_manager = EventManager.get_instance()
        self.component = SUBSCRIPTION_LIST.TEST.value
        self.event = SubscribeEvent("enclosure:hw:controller",
            [HEALTH_STATUSES.FAILED.value, HEALTH_STATUSES.ONLINE.value])

    def tearDown(self):
        pass

    def test_subscriber(self):
        self.event_manager.subscribe(self.component, [self.event])
        self.event_manager.unsubscribe(self.component, [self.event])

if __name__ == "__main__":
    unittest.main()