# -*- coding: utf-8 -*-
# Copyright 2020 The Matrix.org Foundation C.I.C.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from mock import Mock

from synapse.handlers.typing import RoomMember
from synapse.replication.tcp.commands import PositionCommand
from synapse.replication.tcp.streams import TypingStream

from tests.replication._base import BaseStreamTestCase

USER_ID = "@feeling:blue"
USER_ID_2 = "@da-ba-dee:blue"

ROOM_ID = "!bar:blue"
ROOM_ID_2 = "!foo:blue"


class TypingStreamTestCase(BaseStreamTestCase):
    def _build_replication_data_handler(self):
        return Mock(wraps=super()._build_replication_data_handler())

    def test_typing(self):
        typing = self.hs.get_typing_handler()

        self.reconnect()

        typing._push_update(member=RoomMember(ROOM_ID, USER_ID), typing=True)

        self.reactor.advance(0)

        # We should now see an attempt to connect to the master
        request = self.handle_http_replication_attempt()
        self.assert_request_is_get_repl_stream_updates(request, "typing")

        self.test_handler.on_rdata.assert_called_once()
        stream_name, _, token, rdata_rows = self.test_handler.on_rdata.call_args[0]
        self.assertEqual(stream_name, "typing")
        self.assertEqual(1, len(rdata_rows))
        row = rdata_rows[0]  # type: TypingStream.TypingStreamRow
        self.assertEqual(ROOM_ID, row.room_id)
        self.assertEqual([USER_ID], row.user_ids)

        # Now let's disconnect and insert some data.
        self.disconnect()

        self.test_handler.on_rdata.reset_mock()

        typing._push_update(member=RoomMember(ROOM_ID, USER_ID), typing=False)

        self.test_handler.on_rdata.assert_not_called()

        self.reconnect()
        self.pump(0.1)

        # We should now see an attempt to connect to the master
        request = self.handle_http_replication_attempt()
        self.assert_request_is_get_repl_stream_updates(request, "typing")

        # The from token should be the token from the last RDATA we got.
        self.assertEqual(int(request.args[b"from_token"][0]), token)

        self.test_handler.on_rdata.assert_called_once()
        stream_name, _, token, rdata_rows = self.test_handler.on_rdata.call_args[0]
        self.assertEqual(stream_name, "typing")
        self.assertEqual(1, len(rdata_rows))
        row = rdata_rows[0]
        self.assertEqual(ROOM_ID, row.room_id)
        self.assertEqual([], row.user_ids)

    def test_reset(self):
        """
        Test what happens when a typing stream resets.

        This is emulated by jumping the stream ahead, then reconnecting (which
        sends the proper position and RDATA).
        """
        typing = self.hs.get_typing_handler()

        self.reconnect()

        typing._push_update(member=RoomMember(ROOM_ID, USER_ID), typing=True)

        self.reactor.advance(0)

        # We should now see an attempt to connect to the master
        request = self.handle_http_replication_attempt()
        self.assert_request_is_get_repl_stream_updates(request, "typing")

        self.test_handler.on_rdata.assert_called_once()
        stream_name, _, token, rdata_rows = self.test_handler.on_rdata.call_args[0]
        self.assertEqual(stream_name, "typing")
        self.assertEqual(1, len(rdata_rows))
        row = rdata_rows[0]  # type: TypingStream.TypingStreamRow
        self.assertEqual(ROOM_ID, row.room_id)
        self.assertEqual([USER_ID], row.user_ids)

        # Jump the stream ahead manually, the state of the master is not
        # modified, however.
        self.hs.get_tcp_replication().send_command(
            PositionCommand("typing", "master", 100)
        )

        # Now let's disconnect and insert some data.
        self.disconnect()

        self.test_handler.on_rdata.reset_mock()

        typing._push_update(member=RoomMember(ROOM_ID_2, USER_ID_2), typing=False)

        self.test_handler.on_rdata.assert_not_called()

        self.reconnect()
        self.pump(0.1)

        # We should now see an attempt to connect to the master
        request = self.handle_http_replication_attempt()
        self.assert_request_is_get_repl_stream_updates(request, "typing")

        # The from token should be the token from the last RDATA we got.
        self.assertEqual(int(request.args[b"from_token"][0]), token)

        self.test_handler.on_rdata.assert_called_once()
        stream_name, _, token, rdata_rows = self.test_handler.on_rdata.call_args[0]
        self.assertEqual(stream_name, "typing")
        self.assertEqual(1, len(rdata_rows))
        row = rdata_rows[0]
        self.assertEqual(ROOM_ID_2, row.room_id)
        self.assertEqual([], row.user_ids)
