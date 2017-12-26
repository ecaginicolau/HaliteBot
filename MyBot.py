import hlt
import logging
from datetime import datetime
from manager import Manager

# This needs to be before the logger
game = hlt.Game("Rampa-Managed-Nemesis")

logging.info("Starting Rampa Bot")
logger = logging.getLogger("bot")

# Will catch any exception easily
try:

    manager = None
    monitor = None
    while True:
        START_TIME = datetime.utcnow()
        logger.debug("START NEW TURN")
        try:
            game_map = game.update_map()
        except ValueError:
            # ValueError means game is over
            break

        # Create the drone manager only once
        if manager is None:
            manager = Manager(game_map.get_me().id)

        # Reset the list of command
        command_queue = []

        # Update the game_map in the manager
        manager.update_game_map(game_map, START_TIME)
        # Add the ships to the manager
        manager.update_list_ship()
        # Check for dead drone
        manager.check_for_dead_drones()
        # Check/Update drone's targets
        manager.check_drone_target()
        # Check for newly created ship, convert them to drone
        manager.check_for_new_ship()
        # Print the role status
        manager.role_status()
        # Check damaged ship
        manager.check_damaged_drone()
        # Check defenders timer
        manager.check_defender_timer()
        # Give role to IDLE drone
        manager.give_role_idle_drone()

        # Order conqueror to conquer
        manager.order_conquerors()
        # Order attackers to attack
        manager.order_attacker()
        # Order defender to defend
        manager.order_defender()
        # Order miner to mine
        manager.order_miner()

        # Create all commands
        command_queue = manager.create_command_queue()
        # Send the command
        game.send_command_queue(command_queue)

        # Trace turn duration
        END_TIME = datetime.utcnow()
        duration = (END_TIME - START_TIME).total_seconds()
        logger.info("Turn duration : %.2f" % duration)
        # TURN END
        # GAME END
except:
    logging.exception("BIG CRASH")
