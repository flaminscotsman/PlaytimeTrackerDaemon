import logging

from twisted.internet import defer
from twisted.internet.task import LoopingCall
from twistedlilypad.Requests import RequestGetPlayers
from twistedlilypad.Results import ResultGetPlayers

from playtimetracker import LilypadFactory, PlayerNetworkActivityTracker


class OnlinePlayerPoller(PlayerNetworkActivityTracker):
    def __init__(self, username, password, mongo_uri, mongo_database, mongo_collection):
        super(OnlinePlayerPoller, self).__init__(username, password, mongo_uri, mongo_database, mongo_collection)

        self.poller = LoopingCall(self.poll_players)
        self.last_uuids = None

        original_pass_auth = self._passAuth

        def _passAuthShim(evt):
            self.poller.start(5)
            original_pass_auth(evt)

        self._passAuth = _passAuthShim

    @defer.inlineCallbacks
    def poll_players(self):
        try:
            # Nice little gotcha here - you can't inline the request or it can somethimes get garbage collected before
            #   being called!
            request = self.writeRequest(RequestGetPlayers(True, True))
            current_players = yield request
        except Exception:
            self.logger.exception("An error occurred when retrieving current players")
            return

        assert isinstance(current_players, ResultGetPlayers)

        # noinspection PyBroadException
        try:
            if self.last_uuids is None:
                # First run, no need to do anything
                return

            left_players = self.last_uuids.difference(current_players.uuids)
            for uuid in left_players:
                # Connect to MongoDB and get the collection
                mongo = yield self.connection_pool
                database = mongo[self.mongo_database]
                collection = database[self.mongo_collection]

                # Find the unclosed player session. Note, there should only ever be one of these!
                current = yield collection.find({
                    'player_id': self.pack_uuid(uuid),
                    'active': True
                })

                if current:
                    yield self.player_leave_logger(uuid)
        except:
            self.logger.exception("An error occurred when sealing left players")
            raise
        finally:
            self.last_uuids = frozenset(current_players.uuids)


def main():
    from twisted.internet import reactor
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-c', '--connect', default="localhost:5091", help="Location of the lilypad connect instance")
    parser.add_argument('-u', '--username', default="example-999", help="Username to use when authenticating to lilypad")
    parser.add_argument('-p', '--password', default="example", help="Password to use when authenticating to lilypad")
    parser.add_argument('-d', '--uri', default="mongodb://localhost/", help="Location of the MongoDB instance")
    parser.add_argument('--database', default="PlaytimeTracking", help="MongoDB database to use")
    parser.add_argument('--collection', default="Activity", help="Mongodb collection to use")

    args = parser.parse_args()

    # Logging configuration
    logger = logging.getLogger()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    logger.addHandler(handler)

    # Run application
    factory = LilypadFactory(
        OnlinePlayerPoller,
        args.username,
        args.password,
        args.uri,
        args.database,
        args.collection
    )

    # noinspection PyUnresolvedReferences
    reactor.connectTCP(
        args.connect.rsplit(':', 1)[0],
        int(args.connect.rsplit(':', 1)[1], 10) if ':' in args.connect else 5091,
        factory
    )

    # noinspection PyUnresolvedReferences
    reactor.run()

if __name__ == '__main__':
    main()
