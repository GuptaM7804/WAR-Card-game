"""
war card game client and server
"""
import asyncio
from collections import namedtuple
from enum import Enum
import logging
import random
import socket
import _thread
import sys


Game = namedtuple("Game", ["p1", "p2"])


class Command(Enum):
    """
    The byte values sent as the first byte of any message in the war protocol.
    """
    WANTGAME = 0
    GAMESTART = 1
    PLAYCARD = 2
    PLAYRESULT = 3


class Result(Enum):
    """
    The byte values sent as the payload byte of a PLAYRESULT message.
    """
    WIN = 0
    DRAW = 1
    LOSE = 2


def readexactly(sock, numbytes):
    """
    Accumulate exactly `numbytes` from `sock` and return those. If EOF is found
    before numbytes have been received, be sure to account for that here or in
    the caller.
    """
    byte = b""
    while len(byte) < numbytes:
        try:
            data = sock.recv(numbytes - len(byte))
        except socket.error:
            logging.error("Error error error")
            return None
        if not data:
            break
        byte += data
    return byte


def kill_game(game):
    """
    Done: If either client sends a bad message, immediately nuke the game.
    """
    game.p1.close()
    game.p2.close()
    game = Game(None, None)


def compare_cards(card1, card2):
    """
    Done: Given an integer card representation, return -1 for card1 < card2,
    0 for card1 = card2, and 1 for card1 > card2
    """
    value1 = card1 % 13 + 2
    value2 = card2 % 13 + 2
    return (value1 > value2) - (value1 < value2)


def deal_cards():
    """
    Done: Randomize a deck of cards (list of ints 0..51), and return two
    26 card "hands."
    """
    deck = list(range(52))
    random.shuffle(deck)
    hand1, hand2 = deck[:26], deck[26:]
    return hand1, hand2


def war_game(client1, client2):
    """
    war_game: handles the actual game of war between dos clientos
    easy to code get good
    """
    game = Game(client1[0], client2[0])
    response1 = readexactly(game.p1, 2)
    response2 = readexactly(game.p2, 2)
    if response1[0] != Command.WANTGAME.value \
            or response2[0] != Command.WANTGAME.value:
        kill_game(game)
        return

    hand1, hand2 = deal_cards()
    game.p1.sendall(bytes([Command.GAMESTART.value]))
    game.p1.sendall(bytes(hand1))
    game.p2.sendall(bytes([Command.GAMESTART.value]))
    game.p2.sendall(bytes(hand2))
    for _ in range(0, 26):
        card1 = readexactly(game.p1, 2)
        card2 = readexactly(game.p2, 2)
        if card1[0] != Command.PLAYCARD.value \
                or card2[0] != Command.PLAYCARD.value:
            kill_game(game)
            return
        if card1[1] not in hand1 or card2[1] not in hand2:
            kill_game(game)
            return

        result = compare_cards(card1[1], card2[1])
        if result == 1:
            p1_result, p2_result = 0, 2
        elif result == -1:
            p1_result, p2_result = 2, 0
        else:
            p1_result, p2_result = 1, 1
        game.p1.sendall(bytes([Command.PLAYRESULT.value, p1_result]))
        game.p2.sendall(bytes([Command.PLAYRESULT.value, p2_result]))


def serve_game(host, port):
    """
    Done: Open a socket for listening for new connections on host:port, and
    perform the war protocol to serve a game of war between each client.
    This function should run forever, continually serving clients.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen()

    try:
        while True:
            client1 = server_socket.accept()
            client2 = server_socket.accept()

            _thread.start_new_thread(war_game, (client1, client2))
    except KeyboardInterrupt:
        server_socket.close()


async def limit_client(host, port, loop, sem):
    """
    Limit the number of clients currently executing.
    You do not need to change this function.
    """
    async with sem:
        return await client(host, port, loop)


async def client(host, port, loop):
    """
    Run an individual client on a given event loop.
    You do not need to change this function.
    """
    try:
        reader, writer = await asyncio.open_connection(host, port, loop=loop)
        # send want game
        writer.write(b"\0\0")
        card_msg = await reader.readexactly(27)
        myscore = 0
        for card in card_msg[1:]:
            writer.write(bytes([Command.PLAYCARD.value, card]))
            result = await reader.readexactly(2)
            if result[1] == Result.WIN.value:
                myscore += 1
            elif result[1] == Result.LOSE.value:
                myscore -= 1
        if myscore > 0:
            result = "won"
        elif myscore < 0:
            result = "lost"
        else:
            result = "drew"
        print(result)
        logging.debug("Game complete, I %s", result)
        writer.close()
        return 1
    except ConnectionResetError:
        logging.error("ConnectionResetError")
        return 0
    except asyncio.streams.IncompleteReadError:
        logging.error("asyncio.streams.IncompleteReadError")
        return 0
    except OSError:
        logging.error("OSError")
        return 0


def main(args):
    """
    launch a client/server
    """
    host = args[1]
    port = int(args[2])
    if args[0] == "server":
        try:
            # your server should serve clients until the user presses ctrl+c
            serve_game(host, port)
        except KeyboardInterrupt:
            pass
        return
    loop = asyncio.get_event_loop()

    if args[0] == "client":
        loop.run_until_complete(client(host, port, loop))
    elif args[0] == "clients":
        sem = asyncio.Semaphore(1000)
        num_clients = int(args[3])
        clients = [limit_client(host, port, loop, sem)
                   for x in range(num_clients)]

        async def run_all_clients():
            """
            use `as_completed` to spawn all clients simultaneously
            and collect their results in arbitrary order.
            """
            completed_clients = 0
            for client_result in asyncio.as_completed(clients):
                completed_clients += await client_result
            return completed_clients
        res = loop.run_until_complete(
            asyncio.Task(run_all_clients(), loop=loop))
        logging.info("%d completed clients", res)

    loop.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1:])
