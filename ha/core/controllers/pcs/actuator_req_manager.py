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

import time
import json
import ast

from cortx.utils.conf_store import Conf
from ha.core.system_health.const import NODE_MAP_ATTRIBUTES
from ha.execute import SimpleCommand
from ha.const import ACTUATOR_SCHEMA, ACTUATOR_ATTRIBUTES, ACTUATOR_RESP_RETRY_COUNT, ACTUATOR_RESP_WAIT_TIME
from ha.const import _DELIM
from ha import const
from cortx.utils.log import Log
from ha.const import PVTFQDN_TO_NODEID_KEY

from ha.core.system_health.system_health import SystemHealth, SystemHealthManager
from ha.core.error import ClusterManagerError
from ha.util.message_bus import MessageBus
from ha.core.config.config_manager import ConfigManager


class ActuatorManager:

    def __init__(self):

        # ARCH TEMP configure log file only for testing
        ConfigManager.init("actuator_manager")

        self._conf_store = ConfigManager.get_confstore()
        self._execute = SimpleCommand()
        self._machine_id = self._get_machine_id()
        self._uuid = None
        self._is_resp_received = False
        self._encl_shutdown_successful = False

    def _generate_uuid(self):
        """
        Generate as uuid a random number.
        This will be populated in uuid field in actuator request
        same uuid is expected in actuatore response
        """
        self._uuid = str(int(time.time()))

    def _get_machine_id(self):
        command = "cat /etc/machine-id"
        machine_id, err, rc = self._execute.run_cmd(command, check_error=True)
        Log.info(f"Read machine-id. Output: {machine_id}, Err: {err}, RC: {rc}")
        print(f"Read machine-id. Output: {machine_id}")
        return machine_id.strip()

    def enclosure_stop(self, node_name: str) -> bool :
        """
        Send actuator request to monitor for stopping enclosure
        """

        print(self._conf_store)

        req = self._create_req(node_name)
        self._send_req(req)
        self._wait_for_resp()
        print("waiting for response now ...")

        # Wait for 60 sec max. Expected max wait time = 40 sec + 20 sec buffer
        for _ in range(0, ACTUATOR_RESP_RETRY_COUNT):
            time.sleep(ACTUATOR_RESP_WAIT_TIME)
            if self._is_resp_received:
               break

        # Stop the thread that was created
        #self.consumer.stop()
        #ARCH TBD for now raise exception if response is not received.

        if self._is_resp_received and self._encl_shutdown_successful:
            Log.info(f"Enclosure shutdown successful on node {node_name}")
            print(f"Enclosure shutdown successful on node {node_name}")
            self._is_resp_received = self._encl_shutdown_successful = False
            return True

        if not self._is_resp_received:
            Log.warn(f"Actuator response not received; enclosure shutdown failed on node {node_name}")
            print(f"Actuator response not received; enclosure shutdown failed on node {node_name}")
        else:
            Log.warn(f"Unable to shutdown enclosure on node {node_name}")
            print(f"Unable to shutdown enclosure on node {node_name}")

        # ARCH TBD check if node shutdown does anything with thi True/False that is sent
        # Except for the already handled Logging
        self._is_resp_received = self._encl_shutdown_successful = False
        return False



    def _create_req(self, target_node_name):
        """
        Create actualtor request for enclosure stop
        """

        with open(ACTUATOR_SCHEMA, 'r') as actuator_req_schema_file:
            actuator_req = json.load(actuator_req_schema_file)

        # Get details for current node
        node_name = Conf.get(const.HA_GLOBAL_INDEX, f"CLUSTER_MANAGER{_DELIM}local_node")
        print(f"{PVTFQDN_TO_NODEID_KEY}/{node_name}")

        key_val  = self._conf_store.get(f"{PVTFQDN_TO_NODEID_KEY}/{node_name}")
        _, node_id = key_val.popitem()
        print(f"Got node is as {node_id}")

        system_health = SystemHealth(self._conf_store)
        health_manager = SystemHealthManager(self._conf_store)
        key = system_health._prepare_key(const.COMPONENTS.NODE_MAP.value, node_id=node_id)

        print(f"key is {key}")

        node_map_val = health_manager.get_key(key)
        if node_map_val is None:
            raise ClusterManagerError("Failed to fetch node_map value")

        node_map_dict = ast.literal_eval(node_map_val)
        self._generate_uuid()
        print(f"uuid is {self._uuid}")

        # Populate the actuator request schema
        actuator_req[ACTUATOR_ATTRIBUTES.TIME] = str(int(time.time()))
        actuator_req[ACTUATOR_ATTRIBUTES.MESSAGE][ACTUATOR_ATTRIBUTES.REQUEST_PATH][ACTUATOR_ATTRIBUTES.SITE_ID] = node_map_dict[NODE_MAP_ATTRIBUTES.SITE_ID.value] 
        actuator_req[ACTUATOR_ATTRIBUTES.MESSAGE][ACTUATOR_ATTRIBUTES.REQUEST_PATH][ACTUATOR_ATTRIBUTES.RACK_ID] = node_map_dict[NODE_MAP_ATTRIBUTES.RACK_ID.value]
        actuator_req[ACTUATOR_ATTRIBUTES.MESSAGE][ACTUATOR_ATTRIBUTES.REQUEST_PATH][ACTUATOR_ATTRIBUTES.NODE_ID] = node_id
        actuator_req[ACTUATOR_ATTRIBUTES.MESSAGE][ACTUATOR_ATTRIBUTES.TARGET_NODE_ID] = target_node_name
        actuator_req[ACTUATOR_ATTRIBUTES.MESSAGE][ACTUATOR_ATTRIBUTES.HEADER][ACTUATOR_ATTRIBUTES.UUID] = self._uuid

        print(actuator_req)

        actuator_req_schema_file.close()
        req = json.dumps(actuator_req)

        return req

    def _send_req(self, req):
        """
        Send the created request to "monitor" on message bus
        """

        self.req_message_type = Conf.get(const.HA_GLOBAL_INDEX, f"ACTUATOR_MANAGER{_DELIM}req_message_type")
        self.producer_id = Conf.get(const.HA_GLOBAL_INDEX, f"ACTUATOR_MANAGER{_DELIM}producer_id")
        self.producer =  MessageBus.get_producer(self.producer_id, self.req_message_type)

        print(f"Publishing on message_type {self.req_message_type}, producer_id {self.producer_id}, producer {self.producer}")
        Log.debug(f"Publishing request {req} on message_type {self.req_message_type}")
        self.producer.publish(req)

    def _wait_for_resp(self):
        """
        Wait for a response to the sent request. Timeout if req not received in specified time. i
        """
        self.consumer_group =  Conf.get(const.HA_GLOBAL_INDEX, f"ACTUATOR_MANAGER{_DELIM}consumer_group")
        self.consumer_id =  Conf.get(const.HA_GLOBAL_INDEX, f"ACTUATOR_MANAGER{_DELIM}consumer_id")
        self.resp_message_type = Conf.get(const.HA_GLOBAL_INDEX, f"ACTUATOR_MANAGER{_DELIM}resp_message_type")

        print(f"self.consumer_group {self.consumer_group} , self.resp_message_type {self.resp_message_type} ")
        self.consumer = MessageBus.get_consumer(consumer_id=str(self.consumer_id),
                                consumer_group=self.consumer_group,
                                message_type=self.resp_message_type,
                                callback=self.process_resp)
        # Start the thread to listen to response
        self.consumer.start()
        Log.debug(f"Waiting to get response on message_type {self.resp_message_type}")

    def _filter_event(self, msg: str) -> bool :

        print(f"filter_event for {msg}")
        message = json.loads(msg).get(ACTUATOR_ATTRIBUTES.MESSAGE)

        msg_type = message.get(ACTUATOR_ATTRIBUTES.ACTUATOR_RESPONSE_TYPE)
        if msg_type is not None:
            uuid = message.get(ACTUATOR_ATTRIBUTES.HEADER).get(ACTUATOR_ATTRIBUTES.UUID)
            if uuid == self._uuid:
                return True
        return False

    def _parse_response(self, msg) -> bool:
        """
        Response with following severity expected in json response
           "severity": "informational" : Successful shutdown
           "severity": "warning" :  Failure in shutdown

        Return
            True : Enclosure shutdown was successful
            False : Enclosure shutdown failed
        """
        message = json.loads(msg).get(ACTUATOR_ATTRIBUTES.MESSAGE)
        severity =  message.get(ACTUATOR_ATTRIBUTES.ACTUATOR_RESPONSE_TYPE).get(ACTUATOR_ATTRIBUTES.SEVERITY)
        if severity == "informational":
            return True
        elif severity == "warning":
            return False
        else:
            Log.warn(f"Unexpected status received in {msg}")
            print(f"Unexpected status received in {msg}")
            # ARCH TBD Raise exception or just ignore
            return False


    def process_resp(self, resp: str):
        """
        Parse the response and detect success / failure
        """
        try:
            resp = json.loads(resp.decode('utf-8'))
        except Exception as e:
            Log.error(f"Invalid resp {resp}, Error: {e}")
            print(f"Invalid resp {resp}, Error: {e}")
            return
        if resp is None:
            return

        Log.debug(f"Received message {resp}")
        if self._filter_event(json.dumps(resp)):
            Log.info(f"Filtered Event detected: {resp}")
            print(f"Filtered Event detected: {resp}")
            # Parse respnse for Enclosure shutdown Success/Failure
            if self._parse_response(json.dumps(resp)):
                self._encl_shutdown_successful = True
                print("self._encl_shutdown_successful is TRUE\n")

            # cleanup
            self._uuid = None
            self._is_resp_received = True
            MessageBus.deregister(self.resp_message_type)
        else:
            print("Event not for us")
        return