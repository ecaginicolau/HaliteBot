import logging
from datetime import datetime

import hlt
from bot.manager import Manager
from bot.monitor import Monitor
from bot.influence import Influence


from bot.settings import config
import os
dir_path = os.path.dirname(os.path.realpath(__file__))


# This needs to be before the logger
game = hlt.Game("Rampa")

logging.info("Starting Rampa Bot")
logger = logging.getLogger("bot")
# Load configuration


# Will catch any exception easily
try:

    first_turn = True
    while True:
        START_TIME = datetime.utcnow()
        logger.debug("START NEW TURN")
        try:
            game_map = game.update_map()
        except ValueError:
            # ValueError means game is over
            break

        # Reset the list of command
        command_queue = []


        # Create the drone manager only once
        if first_turn:
            Manager.init(game_map.get_me().id)
            Monitor.init(game_map.get_me().id)
            Influence.init(game_map.get_me().id)
            Manager.update_game_map(game_map, START_TIME)
            Monitor.initial_turn()
            first_turn = False
            """
            if len(game_map.all_players()) == 2:
                config.load_configuration(filename=os.path.join(dir_path, "configuration.pickle"))
            else:
                config.load_configuration(filename=os.path.join(dir_path, "configuration4.pickle"))
            """
        else:
            # Update the game_map in the manager
            Manager.update_game_map(game_map, START_TIME)

        # Calculate the distance between all ships once and for all
        Manager.calculate_all_drones_distance()
        # Check damaged ship
        Manager.check_damaged_drone()
        # Check defenders timer
        # Manager.check_defender_timer()
        # Give role to IDLE drone
        Manager.give_role_idle_drone()

        # Order conqueror to conquer
        Manager.order_conquerors()
        # Order attackers to attack
        Manager.order_assassin()
        # Order attackers to attack
        Manager.order_attacker()
        # Order squads
        Manager.order_squad()
        # Order defender to defend
        Manager.order_defender()
        # Order miner to mine
        Manager.order_miner()

        # Create all commands
        command_queue = Manager.create_command_queue()
        # Send the command
        game.send_command_queue(command_queue)

        # Trace turn duration
        END_TIME = datetime.utcnow()
        duration = (END_TIME - START_TIME).total_seconds()
        logger.info("Turn duration : %.2f" % duration)
        # TURN END
        # GAME END
        #if Monitor.turn == 100:
        #    raise Exception("blah")
except:
    logging.exception("BIG CRASH")

