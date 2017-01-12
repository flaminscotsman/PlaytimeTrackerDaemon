import logging

from twisted.internet import defer
from twistedlilypad.Packets import PacketPlayerEvent

from playtimetracker import LilypadFactory
from playtimetracker.playtimetracker import PlayerNetworkActivityTracker


class PlayerNetworkActivityListener(PlayerNetworkActivityTracker):
    @defer.inlineCallbacks
    def onPlayerEventPacket(self, event):
        assert isinstance(event, PacketPlayerEvent)
        if event.joining:
            # We don't care about join events; continue
            return

        yield self.player_leave_event(event.player_uuid)


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
        PlayerNetworkActivityListener,
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
