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
import pathlib
import sys

sys.path.append(os.path.join(os.path.dirname(pathlib.Path(__file__)), '..', '..', '..'))

from ha.core.event_manager.event_manager import EventManager
from ha.core.event_manager.subscribe_event import SubscribeEvent
from ha.core.system_health.model.health_event import HealthEvent
from ha.util.message_bus import MessageBus
from ha.core.action_handler.action_factory import ActionFactory

if __name__ == '__main__':
    try:
        print("********Event Action Handler********")
        event_manager = EventManager.get_instance()
        component = "csm"
        resource_type = "node"
        state = "offline"
        actions = ["publish"]
        message_type = event_manager.subscribe('csm', [SubscribeEvent(resource_type, [state])])
        print(f"Subscribed {component}, message type is {message_type}")
        health_event = HealthEvent("event_1", "offline", "fault", "site_1", "rack_1", "cluster_1", "storageset_1",
                                   "node_1", "abcd.com", "node", "16215009572", "disk_1", None)
        action_handler_obj = ActionFactory.get_action_handler(action=actions, event=health_event)
        action_handler_obj.act(event=health_event, action=actions)
        print("Consuming the action event")
        message_consumer = MessageBus.get_consumer(consumer_id="1",
                                                   consumer_group='test_publisher',
                                                   message_types=[message_type])
        message = message_consumer.receive()
        print(message)
        message_consumer.ack()
        unsubscribe = event_manager.unsubscribe('csm', [SubscribeEvent(resource_type, [state])])
        print(f"Unsubscribed {component}")
        print("Event action handler test completed successfully")
    except Exception as e:
        print(f"Failed to run event action handler test, Error: {e}")