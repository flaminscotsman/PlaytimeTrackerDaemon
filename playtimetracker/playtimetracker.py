# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from struct import pack

from bson.binary import JAVA_LEGACY, Binary, OLD_UUID_SUBTYPE
from bson.codec_options import CodecOptions
from twisted.internet import defer
from twisted.internet.protocol import ReconnectingClientFactory
from twistedlilypad.LilypadProtocol import AutoAuthenticatingLilypadClientProtocol
from txmongo.collection import Collection
from txmongo.connection import ConnectionPool
from txmongo.database import Database


class PlayerNetworkActivityTracker(AutoAuthenticatingLilypadClientProtocol):
    def __init__(self, username, password, mongo_uri, mongo_database, mongo_collection):
        self.username = username
        self.password = password

        self.mongo_uri = mongo_uri
        self.mongo_database = mongo_database
        self.mongo_collection = mongo_collection
        self._connection_pool = None

        self.logger = logging.getLogger('PlaytimeTracker')

        super(AutoAuthenticatingLilypadClientProtocol, self).__init__()

    def connectionMade(self):
        """As the ReconnectingClientFactory exponentially backs off up to a default maximum delay before attempting to
        reconnect of 1 hour, reset the reconnection delay to it's initial value once connected.
        """
        if hasattr(self, 'factory') and isinstance(self.factory, ReconnectingClientFactory):
            self.factory.delay = self.factory.initialDelay
        super(PlayerNetworkActivityTracker, self).connectionMade()

    @defer.inlineCallbacks
    def player_leave_logger(self, player_uuid):
        """Seals the active playtime document(s) of a player to provide per-session play time statistics

        Args:
            player_uuid (UUID): UUID of the player
        """
        try:
            # Collect the time the player left before doing any slow database accesses
            logout_time = datetime.now()
            # player_id = UUIDLegacy(event.player_uuid)
            player_id = self.pack_uuid(player_uuid)

            # Connect to MongoDB and get the collection
            mongo = yield self.connection_pool
            database = mongo[self.mongo_database]
            assert isinstance(database, Database)
            collection = database[self.mongo_collection]
            assert isinstance(collection, Collection)

            # Find the unclosed player session(s). Note, there should only ever be one of these!
            current = yield collection.find({
                'player_id': player_id,
                'active': True
            }, projection=['start_time'])

            # Find the session id of the last processed session.
            last = yield collection.aggregate([
                {
                    '$match': {
                        'player_id': player_id,
                        'active': False,
                        'session_id': {'$exists': True}
                    }
                }, {
                    '$sort': {
                        'session_id': -1
                    }
                }, {
                    '$project': {
                        'session_id': True
                    }
                }, {
                    '$limit': 1
                }
            ])

            if len(current) > 1:
                self.logger.warning("Found {} unclosed sessions for {}! This should not be possible.".format(
                    len(current), player_uuid
                ))

            session_id = last[-1]['session_id'] if last else 0

            for offset, to_seal in enumerate(sorted(current, key=lambda x: x['start_time']), 1):
                query = collection.update({
                    'player_id': player_id,
                    'start_time': {'$lte': to_seal['start_time']},
                    'session_id': {'$exists': False}
                }, {
                    '$set': {
                        'active': False,
                        'session_id': session_id + offset,
                    }
                }, multi=True)
                yield query

                query = collection.update({
                    '_id': to_seal['_id']
                }, {
                    '$set': {
                        'active': False,
                        'end_time': logout_time
                    }
                })
                yield query

                query = collection.find({
                    'player_id': player_id,
                    'session_id': session_id + offset,
                })
                for document in (yield query):
                    # Update the end time and duration of the last element in the activity_tracker array
                    set_op = {
                        'activity_tracker.{}.duration'.format(len(document['activity_tracker']) - 1):
                            (document['end_time'] - document['activity_tracker'][-1]['start_time']).total_seconds(),
                        'activity_tracker.{}.end_time'.format(len(document['activity_tracker']) - 1): document['end_time']
                    }

                    # Update the duration of each element in the activity_tracker array using the start_time of the next
                    #   element in the sequence
                    set_op.update({
                        'activity_tracker.{}.duration'.format(idx):
                            (doc['start_time'] - document['activity_tracker'][idx]['start_time']).total_seconds()
                        for idx, doc in enumerate(document['activity_tracker'][1:])
                    })

                    # Update the end_time of each element in the activity_tracker array using the start_time of the next
                    #   element in the sequence
                    set_op.update({
                        'activity_tracker.{}.end_time'.format(idx): doc['start_time']
                        for idx, doc in enumerate(document['activity_tracker'][1:])
                    })

                    # Dispatch the update operation
                    query = collection.update({
                        '_id': document['_id']
                    }, {
                        '$set': set_op
                    })
                    yield query
        except Exception as e:
            self.logger.exception('An error occurred when closing a record!')
            raise

    @staticmethod
    def pack_uuid(uuid):
        return Binary(pack('<Q', uuid.int / 0x10000000000000000) + pack('<Q', uuid.int % 0x10000000000000000),
                      OLD_UUID_SUBTYPE)

    @property
    @defer.inlineCallbacks
    def connection_pool(self):
        if self._connection_pool is None:
            self._connection_pool = yield ConnectionPool(self.mongo_uri, pool_size=5, codec_options=CodecOptions(uuid_representation=JAVA_LEGACY))
        defer.returnValue(self._connection_pool)


class LilypadFactory(ReconnectingClientFactory):
    """Quick class to build an instance of the protocol with the correct credentials when requested."""
    def __init__(self, protocol, username, password, mongo_uri, mongo_database, mongo_collection):
        """ Keep a reference to the username/password combination used to authenticate. """
        self.protocol = protocol

        self.username = username
        self.password = password

        self.mongo_uri = mongo_uri
        self.mongo_database = mongo_database
        self.mongo_collection = mongo_collection

    def buildProtocol(self, addr):
        """Build a protocol instance, called when connecting to a network."""
        proto = self.protocol(
            self.username,
            self.password,
            self.mongo_uri,
            self.mongo_database,
            self.mongo_collection
        )
        proto.factory = self
        return proto
