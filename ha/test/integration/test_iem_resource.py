#!/usr/bin/env python3

# Copyright (c) 2020 Seagate Technology LLC and/or its Affiliates
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


"""
 ****************************************************************************
 Description:       resource_agent resource agent
 ****************************************************************************
"""

import os
import time
import json
import consul
import unittest
from unittest.mock import patch
from datetime import datetime

from cortx.utils.ha.dm.decision_monitor import DecisionMonitor
from cortx.utils.log import Log
from cortx.utils.ha.dm.actions import Action

from ha.resource.resource_agent import IEMResourceAgent
from ha import const

class TestIEMResourceAgent(unittest.TestCase):
    """
    Unit test for hardware resource agent
    """

    def setUp(self):
        Log.init(service_name='resource_agent', log_path=const.RA_LOG_DIR, level="DEBUG")
        self.ts = int(time.time())
        self.td = datetime.fromtimestamp(self.ts).strftime('%Y-%m-%dT%H:%M:%S.000000+0000')
        with open(const.RESOURCE_SCHEMA, 'r') as f:
            self.schema = json.load(f)
        self.iem_agent = IEMResourceAgent(DecisionMonitor(), self.schema)
        self.key = "cortx/base/ha/obj"
        self.filename = 'node_iem_s3'
        self.path = 'node_iem_s3'
        self.local = self.schema['nodes']['local']
        self.consul = consul.Consul()

    def tearDown(self):
        self._remove_data(self.local, True,self.key)
        if os.path.exists(const.HA_INIT_DIR + self.filename):
            os.remove(const.HA_INIT_DIR + self.filename)

    def _get_key(self, node):
        """
        Get ID and key for alert
        """
        alert_id = ''
        hw_resource  = self.schema["resources"][self.filename +'_'+ node]
        for val in hw_resource.values():
            alert_id = alert_id + val + '/'
        alert_id = alert_id + str(self.ts)
        return self.key +'/'+ alert_id, alert_id

    def _get_data(self, node):
        key, alert_id = self._get_key(node)
        index, data = self.consul.kv.get(key)
        return data

    def _put_data(self, state, node):
        """
        Put data to consul
        Msg:
                cortx/base/ha/obj/node/srvnode-1/nw/mgmt/1589609895
                '{"decision_id": "node/srvnode-1/nw/mgmt/1589609895",
                    "action": "failed",
                    "alert_time": "2020-05-16T06:18:15.000000+0000"
                }'
        """
        key, alert_id = self._get_key(node)
        self.consul.kv.put(key, '{"decision_id": "'+alert_id+ \
            '", "action": "'+state+'", "alert_time": "'+self.td+'"}')

    def _remove_data(self, node, recurse=False, key=None):
        """
        Remove data from consul
        consul kv delete -recurse cortx/base/ha/obj/enclosure
        """
        if key == None:
            key, alert_id = self._get_key(node)
        self.consul.kv.delete(key, recurse)

    @patch('ha.resource.resource_agent.IEMResourceAgent.get_env')
    def test_start(self, patched_get_env):
        """
        Test start for hw resource agent

        Arguments:
            patched_get_env {[resource_agent method]} -- Method for resource agent to get
                pacemaker env data.
        """
        patched_get_env.return_value = {
            'OCF_RESKEY_filename': self.filename,
            'OCF_RESKEY_path': self.path,
            'OCF_RESKEY_service': '-',
            'OCF_RESKEY_node': self.local
        }
        # No data in consul
        self._remove_data(self.local)
        status = self.iem_agent.start()
        self.assertEqual(status, const.OCF_SUCCESS)
        # failed state in consul
        self._put_data(Action.FAILED, self.local)
        status = self.iem_agent.start()
        self.assertEqual(status, const.OCF_ERR_GENERIC)
        self._remove_data(self.local)
        # resolved state in consul
        time.sleep(1)
        self._put_data(Action.RESOLVED, self.local)
        status = self.iem_agent.start()
        self.assertEqual(status, const.OCF_SUCCESS)

    @patch('ha.resource.resource_agent.IEMResourceAgent.get_env')
    def test_stop(self, patched_get_env):
        """
        Test stop for hw resource agent

        Arguments:
            patched_get_env {[resource_agent method]} -- Method for resource agent to get
                pacemaker env data.
        """
        patched_get_env.return_value = {
            'OCF_RESKEY_filename': self.filename,
            'OCF_RESKEY_path': self.path,
            'OCF_RESKEY_service': 'ldap',
            'OCF_RESKEY_node': self.local
        }
        # No data to consul
        self._remove_data(self.local)
        status = self.iem_agent.stop()
        self.assertEqual(status, const.OCF_SUCCESS)
        # failed state in consul
        self._put_data(Action.FAILED, self.local)
        status = self.iem_agent.stop()
        self.assertEqual(status, const.OCF_SUCCESS)
        self._remove_data(self.local)
        # resolved state in consul
        time.sleep(1)
        self._put_data(Action.RESOLVED, self.local)
        status = self.iem_agent.stop()
        self.assertEqual(status, const.OCF_SUCCESS)

    @patch('ha.resource.resource_agent.IEMResourceAgent.get_env')
    def test_monitor(self, patched_get_env):
        """
        Test monitor for hw resource agent

        Arguments:
            patched_get_env {[resource_agent method]} -- Method for resource agent to get
                pacemaker env data.
        """
        patched_get_env.return_value = {
            'OCF_RESKEY_filename': self.filename,
            'OCF_RESKEY_path': self.path,
            'OCF_RESKEY_service': '-',
            'OCF_RESKEY_node': self.local
        }
        os.makedirs(const.HA_INIT_DIR, exist_ok=True)
        if os.path.exists(const.HA_INIT_DIR + self.filename):
            os.remove(const.HA_INIT_DIR + self.filename)
        status = self.iem_agent.monitor()
        self.assertEqual(status, const.OCF_NOT_RUNNING)
        if not os.path.exists(const.HA_INIT_DIR + self.filename):
            with open(const.HA_INIT_DIR + self.filename, 'w'): pass
        # No data in consul
        self._remove_data(self.local)
        status = self.iem_agent.monitor()
        self.assertEqual(status, const.OCF_SUCCESS)
        # failed state in consul
        self._put_data(Action.FAILED, self.local)
        status = self.iem_agent.monitor()
        self.assertEqual(status, const.OCF_ERR_GENERIC)
        self._remove_data(self.local)
        # resolved state in consul
        time.sleep(1)
        self._put_data(Action.RESOLVED, self.local)
        status = self.iem_agent.monitor()
        self.assertEqual(status, const.OCF_SUCCESS)

if __name__ == "__main__":
    unittest.main()