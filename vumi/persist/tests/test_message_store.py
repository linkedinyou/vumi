# -*- coding: utf-8 -*-

"""Tests for vumi.persist.message_store."""

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportEvent
from vumi.tests.utils import FakeRedis
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.persist.message_store import MessageStore
from vumi.persist.txriak_manager import TxRiakManager


class TestMessageStore(ApplicationTestCase):
    # inherits from ApplicationTestCase for .mkmsg_in and .mkmsg_out

    @inlineCallbacks
    def setUp(self):
        self.r_server = FakeRedis()
        self.manager = TxRiakManager.from_config({'bucket_prefix': 'test.'})
        yield self.manager.purge_all()
        self.store = MessageStore(self.manager, self.r_server, 'teststore')

    @inlineCallbacks
    def tearDown(self):
        yield self.manager.purge_all()
        self.r_server.teardown()

    @inlineCallbacks
    def test_batch_start(self):
        tag1 = ("poolA", "tag1")
        batch_id = yield self.store.batch_start([tag1])
        batch = yield self.store.get_batch(batch_id)
        tag_info = yield self.store.get_tag_info(tag1)
        batch_messages = yield self.store.batch_messages(batch_id)
        self.assertEqual(batch_messages, [])
        self.assertEqual(list(batch.tags), [tag1])
        self.assertEqual(tag_info.current_batch.key, batch_id)
        self.assertEqual(self.store.batch_status(batch_id), {
            'ack': 0, 'delivery_report': 0, 'message': 0, 'sent': 0,
            })

    @inlineCallbacks
    def test_batch_done(self):
        tag1 = ("poolA", "tag1")
        batch_id = yield self.store.batch_start([tag1])
        yield self.store.batch_done(batch_id)
        batch = yield self.store.get_batch(batch_id)
        tag_info = yield self.store.get_tag_info(tag1)
        self.assertEqual(list(batch.tags), [tag1])
        self.assertEqual(tag_info.current_batch.key, None)

    @inlineCallbacks
    def test_add_outbound_message(self):
        msg = self.mkmsg_out(content="outfoo")
        msg_id = msg['message_id']
        yield self.store.add_outbound_message(msg)

        stored_msg = yield self.store.get_outbound_message(msg_id)
        self.assertEqual(stored_msg, msg)
        events = yield self.store.message_events(msg_id)
        self.assertEqual(events, [])

    def test_add_outbound_message_with_batch_id(self):
        batch_id = self.store.batch_start([("pool", "tag")])
        msg = self.mkmsg_out(content="outfoo")
        msg_id = msg['message_id']
        self.store.add_outbound_message(msg, batch_id=batch_id)

        self.assertEqual(self.store.get_outbound_message(msg_id), msg)
        self.assertEqual(self.store.message_batches(msg_id), [batch_id])
        self.assertEqual(self.store.batch_messages(batch_id), [msg_id])
        self.assertEqual(self.store.message_events(msg_id), [])
        self.assertEqual(self.store.batch_status(batch_id), {
            'ack': 0, 'delivery_report': 0, 'message': 1, 'sent': 1,
            })

    def test_add_outbound_message_with_tag(self):
        batch_id = self.store.batch_start([("pool", "tag")])
        msg = self.mkmsg_out(content="outfoo")
        msg_id = msg['message_id']
        self.store.add_outbound_message(msg, tag=("pool", "tag"))

        self.assertEqual(self.store.get_outbound_message(msg_id), msg)
        self.assertEqual(self.store.message_batches(msg_id), [batch_id])
        self.assertEqual(self.store.batch_messages(batch_id), [msg_id])
        self.assertEqual(self.store.message_events(msg_id), [])
        self.assertEqual(self.store.batch_status(batch_id), {
            'ack': 0, 'delivery_report': 0, 'message': 1, 'sent': 1,
            })

    def test_add_ack_event(self):
        batch_id = self.store.batch_start([("pool", "tag")])
        msg = self.mkmsg_out(content="outfoo")
        msg_id = msg['message_id']
        ack = TransportEvent(user_message_id=msg_id, event_type='ack',
                             sent_message_id='xyz')
        ack_id = ack['event_id']
        self.store.add_outbound_message(msg, batch_id=batch_id)
        self.store.add_event(ack)

        self.assertEqual(self.store.get_event(ack_id), ack)
        self.assertEqual(self.store.message_events(msg_id), [ack_id])

    def test_add_inbound_message(self):
        msg = self.mkmsg_in(content="infoo")
        msg_id = msg['message_id']
        self.store.add_inbound_message(msg)

        self.assertEqual(self.store.get_inbound_message(msg_id), msg)

    def test_add_inbound_message_with_batch_id(self):
        batch_id = self.store.batch_start([("pool1", "default10001")])
        msg = self.mkmsg_in(content="infoo", to_addr="+1234567810001",
                            transport_type="sms")
        msg_id = msg['message_id']
        self.store.add_inbound_message(msg, batch_id=batch_id)

        self.assertEqual(self.store.get_inbound_message(msg_id), msg)
        self.assertEqual(self.store.batch_replies(batch_id), [msg_id])

    def test_add_inbound_message_with_tag(self):
        batch_id = self.store.batch_start([("pool1", "default10001")])
        msg = self.mkmsg_in(content="infoo", to_addr="+1234567810001",
                            transport_type="sms")
        msg_id = msg['message_id']
        self.store.add_inbound_message(msg, tag=("pool1", "default10001"))

        self.assertEqual(self.store.get_inbound_message(msg_id), msg)
        self.assertEqual(self.store.batch_replies(batch_id), [msg_id])
