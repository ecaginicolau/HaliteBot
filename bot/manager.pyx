# Python imports
import logging
from datetime import datetime
# Bot imports
from bot.monitor import Monitor
from bot.drone import DroneRole, TargetType, Drone
from bot.navigation import calculate_distance_between
from bot.influence import Influence
from bot.settings import MIN_SHIP_ATTACKERS, MAX_RATIO_SHIP_ATTACKERS, NB_SHIP_THRESHOLD, \
    MAX_TURN_DURATION, MINER_CAN_DEFEND, SAFE_ZONE_RADIUS, MIN_SCORE_DEFENSE, FOLLOW_DISTANCE, EARLY_RATIO_ASSASSIN, EARLY_RATIO_ATTACKER, \
    EARLY_RATIO_DEFENDER, LATE_RATIO_DEFENDER, LATE_RATIO_ATTACKER, LATE_RATIO_ASSASSIN, DEFENDER_RADIUS, NB_TURN_INFLUENCE, NB_IN_INFLUENCE_RATIO
# hlt imports
from hlt.constants import *
from hlt.entity import Ship, Position

"""
# Manager's job:
    - Check for new ship every turn
    - Check for dead drone every turn
    - Check for damaged drone every turn
"""


class Manager(object):
    """
    The role of this class is to manage every drone
    """

    # Store the player id, will be used to distinguish ships
    player_id = None
    # Internal counters
    __nb_dead_drone = 0
    # Store every  drone, indexed by ship_id
    __all_drones = {}
    # Store every drone indexed by role for easy lookup
    __all_role_drones = {}
    # Store the game_map
    game_map = None
    # Store the start_time of the current_turn
    turn_start_time = None

    @staticmethod
    def init(player_id):
        # Store the player id, will be used to distinguish ships
        Manager.player_id = player_id
        # Initialise the dictionnay of role
        for role in DroneRole:
            Manager.__all_role_drones[role] = []

    @staticmethod
    def update_game_map(game_map, start_time):
        """
        [EVERY TURN]
        # Update the game map for the manager
        :param game_map: the game_map for the current_turn
        :param start_time: the start time (datetime utc) for the current turn
        :return:
        """
        # Update the turn start_time
        Manager.turn_start_time = start_time
        # update the game map itself
        Manager.game_map = game_map
        # Send the game_map to the monitor
        Monitor.update_game(game_map)
        # Check for dead drone
        Manager.check_for_dead_drones()
        # Check/Update drone's targets
        Manager.check_drone_target()
        # Check for newly created ship, convert them to drone
        Manager.check_for_new_ship()
        # Check miners
        Monitor.check_planets_miners()
        # Update influence of the game map
        Influence.update_game_map(game_map)
        # Check for new threat
        Monitor.calculate_threat_level()
        # Calculate the number of ship in the influence zone everyturn
        Monitor.nb_ship_in_influence()

    # Return the role of a single ship
    @staticmethod
    def get_ship_role(ship_id):
        try:
            return Manager.__all_drones[ship_id].role
        except KeyError:
            return DroneRole.UNKNOWN

    # Change the role of a single drone
    @staticmethod
    def change_drone_role(drone, role):
        # Reset drone target, invalid if changing role
        drone.reset_target()
        # Store the old role
        old_role = drone.role
        # Remove from the old list
        Manager.__all_role_drones[old_role].remove(drone.ship_id)
        # Add to the new list
        try:
            Manager.__all_role_drones[role].append(drone.ship_id)
        except KeyError:
            Manager.__all_role_drones[role] = [drone.ship_id]
        # Change internal drone role
        drone.role = role

    # Add a new ship to the fleet
    @staticmethod
    def add_ship(ship, role=DroneRole.IDLE):
        # First check if the drone exist
        try:
            drone = Manager.__all_drones[ship.id]
            # Remove the drone from the old list
            logging.warning("Drone already exist, changing role instead")
            Manager.change_drone_role(drone, role)
        except KeyError:
            Manager.__all_drones[ship.id] = Drone(ship=ship, role=role)
            try:
                Manager.__all_role_drones[role].append(ship.id)
            except KeyError:
                Manager.__all_role_drones[role] = [ship.id]
            logging.info("Added a new ship with the role: %s" % Manager.get_ship_role(ship.id))

    @staticmethod
    def add_possible_threat(ship_id, distance, threat_id):
        Manager.__all_drones[ship_id].add_possible_threat(distance, threat_id)

    @staticmethod
    def get_drone(ship_id):
        try:
            return Manager.__all_drones[ship_id]
        except KeyError:
            return None

    @staticmethod
    def check_for_dead_drones():
        """
        [EVERY TURN]
        Loop through all drone to remove dead drone from the list
            - If the drone's ship can't be found in the current list of ship it means it's dead
        :return:
        """
        for ship_id in list(Manager.__all_drones.keys()):
            drone = Manager.__all_drones[ship_id]
            try:
                # If we can find the ship
                ship = Monitor.get_ship(ship_id)
                # Update it in the drone
                drone.update_ship(ship)
            except KeyError:
                # Ship can't be found, so drone is dead
                Manager.__nb_dead_drone += 1
                # Get the old role
                old_role = drone.role
                # Remove from the list of current role
                Manager.__all_role_drones[old_role].remove(ship_id)
                # Remove from the list of all drone
                del Manager.__all_drones[ship_id]
        logging.info("In total %s drone died" % Manager.__nb_dead_drone)

    @staticmethod
    def check_for_new_ship():
        """
        [EVERY TURN]
        Look for newly created ship, convert them to drone
            - If the ship has no drone (role == UNKNOWN), create a drone
            - At the end, no unknown drone should remain
        :return:
        """

        for ship_id in Monitor.get_team_ships():
            # Get the ship
            ship = Monitor.get_ship(ship_id)
            # If the current ship has no role, assign it as IDLE (new ship)
            if Manager.get_ship_role(ship_id) == DroneRole.UNKNOWN:
                Manager.add_ship(ship=ship, role=DroneRole.IDLE)

    @staticmethod
    def calculate_all_drones_distance():
        """
        Calculate between all drones and all ships, once and for all!
        :return:
        """
        for _, drone in Manager.__all_drones.items():
            if drone.role != DroneRole.MINER:
                drone.calculate_all_ships_distance(Monitor.get_all_ships_dict())
                drone.calculate_all_planets_distance(Monitor.get_all_planets_dict())

    @staticmethod
    def check_defender_timer():
        """
        [EVERY TURN]
        Decrease the timer for every defenders
            - Return the drone to idle if no time left
        :return:
        """
        # Loop through all defenders
        for ship_id in list(Manager.__all_role_drones[DroneRole.DEFENDER]):
            # Get the drone
            drone = Manager.__all_drones[ship_id]
            # If there is no defense time left
            if drone.defender_timer <= 0:
                # Change the drone back to it's previous role
                # Get previous role
                previous_role = drone.get_previous_role()
                # Drone can't return to Miner, so switch it to IDLE it was a miner
                if previous_role != DroneRole.MINER:
                    Manager.change_drone_role(drone, DroneRole.IDLE)
                else:
                    # Change if back to its previous role
                    Manager.change_drone_role(drone, previous_role)

    @staticmethod
    def check_damaged_drone():
        """
        [EVERY TURN]
        Loop through all drone to check if they are damaged
            - Convert them to defender if they are damaged
        :return:
        """
        nb_damaged = 0
        for ship_id, drone in Manager.__all_drones.items():
            drone = Manager.__all_drones[ship_id]
            if Monitor.get_ship(ship_id).health < drone.max_health / 2:
                nb_damaged += 1
                logging.debug("ship: %s damaged: %s" % (ship_id, Monitor.get_ship(ship_id).health))
                drone.is_damaged = True
        logging.info("Found %s damaged ship" % nb_damaged)

    @staticmethod
    def role_status():
        """
        Return the number of drone for each role, for debug purpose
        :return: a dictionnay with the role as index containing the number of drone for each role
        """
        role_counter = {}
        for role in DroneRole:
            role_counter[role] = Manager.nb_drone_role(role)
            logging.info("Role: %s, count: %s" % (role, role_counter[role]))
        return role_counter

    @staticmethod
    def nb_drone_role(role):
        """
        Count the number of drone of specific role
        :param role:
        :return: the number of drone of the role
        """
        try:
            return len(Manager.__all_role_drones[role])
        except KeyError:
            return 0

    @staticmethod
    def nb_offense():
        return Manager.nb_drone_role(DroneRole.ATTACKER) + Manager.nb_drone_role(DroneRole.ASSASSIN) + Manager.nb_drone_role(DroneRole.DEFENDER)

    @staticmethod
    def ratio_offense():
        """
        Calcul the ratio between offensive drone vs all drones
        :return: a float between 0 and 1
        """
        ratio = Manager.nb_offense() / float(len(Manager.__all_drones))
        logging.debug("ratio_offense: %s" % ratio)
        return ratio

    @staticmethod
    def future_ratio_offense():
        """
        Calcul the ratio between offensive drone vs all drones, AFTER the drone would be assigned
        :return: a float between 0 and 1
        """
        ratio = (Manager.nb_offense() + 1) / float(len(Manager.__all_drones))
        logging.debug("future_ratio_offense: %s" % ratio)
        return ratio

    @staticmethod
    def get_next_offensive_role():
        """
        This function will return the next offensive DroneRole
        :return:
        """
        if Monitor.map_has_available_spots():
            """
            # By default our first offensive drone is an assassin
            if Manager.nb_drone_role(DroneRole.ASSASSIN) == 0:
                return DroneRole.ASSASSIN
            """
            # Make sure there are enough attackers
            ratio_attacker = Manager.nb_drone_role(DroneRole.ATTACKER) / float(Manager.nb_offense() + 1)
            if ratio_attacker < EARLY_RATIO_ATTACKER:
                return DroneRole.ATTACKER

            # Make sure there are enough assassins
            ratio_assassin = Manager.nb_drone_role(DroneRole.ASSASSIN) / float(Manager.nb_offense() + 1)
            if ratio_assassin < EARLY_RATIO_ASSASSIN:
                return DroneRole.ASSASSIN

            # Make sure there are enough defenders
            ratio_defender = Manager.nb_drone_role(DroneRole.DEFENDER) / float(Manager.nb_offense() + 1)
            if ratio_defender < EARLY_RATIO_DEFENDER:
                return DroneRole.DEFENDER

            # Should not happen, but in doubt create an attacker
            return DroneRole.ATTACKER
        else:
            """
            # By default our first offensive drone is an assassin
            if Manager.nb_drone_role(DroneRole.ASSASSIN) == 0:
                return DroneRole.ASSASSIN
            """
            # Make sure there are enough attackers
            ratio_attacker = Manager.nb_drone_role(DroneRole.ATTACKER) / float(Manager.nb_offense() + 1)
            if ratio_attacker < LATE_RATIO_ATTACKER:
                return DroneRole.ATTACKER

            # Make sure there are enough assassins
            ratio_assassin = Manager.nb_drone_role(DroneRole.ASSASSIN) / float(Manager.nb_offense() + 1)
            if ratio_assassin < LATE_RATIO_ASSASSIN:
                return DroneRole.ASSASSIN

            # Make sure there are enough defenders
            ratio_defender = Manager.nb_drone_role(DroneRole.DEFENDER) / float(Manager.nb_offense() + 1)
            if ratio_defender < LATE_RATIO_DEFENDER:
                return DroneRole.DEFENDER

            # Should not happen, but in doubt create an attacker
            return DroneRole.ATTACKER

    @staticmethod
    def give_role_idle_drone():
        """
        [EVERY TURN]
        Loop through all idle drone to give them a role
            - Always try to have some attackers : between MIN_SHIP_ATTACKERS & MAX_RATIO_SHIP_ATTACKERS
            - All remaining drone are defaulted to CONQUEROR
            - At the end no idle drone should remains
        :return:
        """
        Manager.role_status()
        """
        # 1st: There are still planets to conquer
        """
        if Monitor.map_has_available_spots():
            # While there are still some idle drone, and we have less attackers than ships attacking us
            while Manager.nb_drone_role(DroneRole.IDLE) > 0 and Manager.nb_offense() < Monitor.nb_ship_in_influence_last_x(NB_TURN_INFLUENCE) * NB_IN_INFLUENCE_RATIO:
                # Change an IDLE Drone to attacker
                # Look for the idle drone that is the closest to an enemy
                min_distance = 999
                selected_drone = None
                for ship_id in Manager.__all_role_drones[DroneRole.IDLE]:
                    drone = Manager.__all_drones[ship_id]
                    distance, target = drone.get_closest_ship()
                    if distance < min_distance:
                        selected_drone = drone
                        min_distance = distance
                # Now work with the drone that is the closest to an enemy
                # Get the next offensive role to assign
                role = Manager.get_next_offensive_role()
                # Assign the role to the drone
                Manager.change_drone_role(selected_drone, role)

            # If there are Idle drones
            if Manager.nb_drone_role(DroneRole.IDLE) > 0:
                # Affect all remaining idle to conqueror role
                # Copy the list of ship_id for modification
                list_ship_id = list(Manager.__all_role_drones[DroneRole.IDLE])
                for ship_id in list_ship_id:
                    drone = Manager.__all_drones[ship_id]
                    # Assign the role
                    Manager.change_drone_role(drone, DroneRole.CONQUEROR)

        else:
            """
            # 2nd:  There are no planets to conquer anymore
            """
            list_ship_id = list(Manager.__all_role_drones[DroneRole.IDLE])
            for ship_id in list_ship_id:
                drone = Manager.__all_drones[ship_id]
                # Get the next offensive role
                role = Manager.get_next_offensive_role()
                # Assign the role
                Manager.change_drone_role(drone, role)


        Manager.role_status()

    @staticmethod
    def give_role_idle_drone2():
        """
        [EVERY TURN]
        Loop through all idle drone to give them a role
            - Always try to have some attackers : between MIN_SHIP_ATTACKERS & MAX_RATIO_SHIP_ATTACKERS
            - All remaining drone are defaulted to CONQUEROR
            - At the end no idle drone should remains
        :return:
        """
        Manager.role_status()
        # If there are Idle drones
        if Manager.nb_drone_role(DroneRole.IDLE) > 0:
            # First:  Make sure there are still some available spots to dock
            if Monitor.map_has_available_spots():
                """
                # Not all drone should be attackers if there are still planets to conquer/mine
                # Assign offensive drone based on different ratio
                """
                # First make sure there are enough attacker
                while Manager.nb_drone_role(DroneRole.IDLE) > 0 and\
                        (Manager.nb_offense() < MIN_SHIP_ATTACKERS or Manager.future_ratio_offense() < MAX_RATIO_SHIP_ATTACKERS):
                    # Change an IDLE Drone to attacker
                    # Look for the idle drone that is the closest to an enemy
                    min_distance = 999
                    selected_drone = None
                    for ship_id in Manager.__all_role_drones[DroneRole.IDLE]:
                        drone = Manager.__all_drones[ship_id]
                        distance, target = drone.get_closest_ship()
                        if distance < min_distance:
                            selected_drone = drone
                            min_distance = distance
                    # Now work with the drone that is the closest to an enemy
                    # Get the next offensive role to assign
                    role = Manager.get_next_offensive_role()
                    # Assign the role to the drone
                    Manager.change_drone_role(selected_drone, role)

                """
                #Give the Conqueror role
                """
                # Affect all remaining idle to conqueror role
                # Copy the list of ship_id for modification
                list_ship_id = list(Manager.__all_role_drones[DroneRole.IDLE])
                for ship_id in list_ship_id:
                    drone = Manager.__all_drones[ship_id]
                    Manager.change_drone_role(drone, DroneRole.CONQUEROR)
            # Else: there are no empty planets : default role = ATTACKER
            else:
                """
                # since there are no available spot to dock, we don't need to conquer/mine anymore
                # Create only offensive drone
                """
                # Affect all remaining idle to conqueror role
                # Copythe list of ship_id for modification
                list_ship_id = list(Manager.__all_role_drones[DroneRole.IDLE])
                for ship_id in list_ship_id:
                    drone = Manager.__all_drones[ship_id]
                    # Get the next offensive role to assign
                    role = Manager.get_next_offensive_role()
                    # Assign the role
                    Manager.change_drone_role(drone, role)
        Manager.role_status()

    @staticmethod
    def check_drone_target():
        """
        [EVERY TURN]
        Check if the drones's target are still valid and update them
            - Loop through all drone
            - If the drone has a target
                - If the target is a ship, make sure it's still alive. Update the target it if so, otherwise reset it
                - If the target is a planet, make sure it's still empty. Update the target it if so, otherwise reset it
        :return:
        """
        for ship_id, drone in Manager.__all_drones.items():
            # If the drone had a target already
            if drone.target_id is not None:
                # If the drone is currently targeting a ship
                if drone.target_type == TargetType.SHIP:
                    # Make sure the enemy ship is still alive, update the target if so
                    try:
                        drone.update_target(Monitor.get_ship(drone.target_id))
                    except KeyError:
                        # The target is dead, reset the target
                        drone.reset_target()
                        # Skip to next ship
                        continue
                # If the drone is currently targeting a planet
                if drone.target_type == TargetType.PLANET:
                    # Check if the planet is still free
                    try:
                        target = Monitor.get_planet(drone.target_id)
                        # Check if the planet is still free
                        if not target.is_free(drone.ship.owner):
                            # The target is not free anymore
                            drone.reset_target()
                            # Skip to next ship
                            continue
                        else:
                            # Update the target
                            drone.update_target(target)

                    except KeyError:
                        # The planet is destroyed?
                        drone.reset_target()
                        # Skip to next ship
                        continue

    @staticmethod
    def __navigate_target(ship, target, assassin=False, closest=True):
        """
        Simple method to create a command to attack the closest ship
        :param ship:
        :return: the navigate command
        """
        # logging.debug("Going to generate a navigate command between ship %s and target %s" % (ship.id, target.id))

        navigate_command = None
        if target is not None:
            navigate_command = ship.navigate(
                target,
                Manager.game_map,
                speed=int(MAX_SPEED),
                angular_step=1,
                ignore_planets=False,
                ignore_ships=False,
                ignore_ghosts=False,
                assassin=assassin,
                closest=closest,
            )
            # logging.info("Navigation command: %s" % navigate_command)

        return navigate_command

    @staticmethod
    def __intercept_ship(ship, target, distance):
        if distance > FOLLOW_DISTANCE:
            new_target = target.pos + (target.velocity * (FOLLOW_DISTANCE / MAX_SPEED))
            new_target = Position(new_target.x, new_target.y)
            return Manager.__navigate_target(ship, new_target, closest=False)
        return Manager.__navigate_target(ship, target)

    @staticmethod
    def __suicide_ship_command(ship, target, assassin=False):
        """
        Simple method to create a command to collide to a target
        :param ship:
        :return: the navigate command
        """
        return Manager.__navigate_target(ship, target, assassin=assassin, closest=False)

    @staticmethod
    def __attack_ship_command(ship, target, assassin=False):
        """
        Simple method to create a command to attack a target ship
        :param ship:
        :return: the navigate command
        """
        return Manager.__navigate_target(ship, target, assassin=assassin)

    @staticmethod
    def __conquer_ship_command(ship, target):
        """
        Simple method to create a command to conquer a target planet
        :param ship:
        :return: the navigate command
        """
        return Manager.__navigate_target(ship, target)

    @staticmethod
    def check_drone_surrounding(drone):
        # Check if enemies are in the radius of defense
        # Get the distance of the closest enemy ship
        distance, ship = drone.get_closest_ship()
        if distance <= DEFENDER_RADIUS:
            # Change drone role to DEFENDER
            Manager.change_drone_role(drone, DroneRole.ATTACKER)
            return True
        return False

    @staticmethod
    def check_drone_defense(drone):
        """
        Check if there is an enemy inside the defender radius of a drone, make it a defender if so
        :param drone:
        :return: true if a drone has become a defender
        """

        # First make sure that the drone has still some defender_timer left
        if drone.defender_timer <= 0:
            return False

        # Check if enemies are in the radius of defense
        # Get the distance of the closest enemy ship
        distance, ship = drone.get_closest_ship()
        if distance <= DEFENDER_RADIUS:
            # Change drone role to DEFENDER
            Manager.change_drone_role(drone, DroneRole.DEFENDER)
            return True
        return False

    @staticmethod
    def order_assassin():
        """
        [EVERY TURN]
        Main IA function for all drone with ASSASSIN role
            - Loop through all ASSASSIN
            - Don't change drone with valid target
            - Look for a target for drone without one: closest ship docked to a planet
            - If there are no docked ship, change to attacker
            - At the end every assassin should have a target
        :return:
        """

        # Get the current nemesis
        nemesis = Monitor.find_nemesis()

        # Loop through all drone
        for ship_id in Manager.__all_role_drones[DroneRole.ASSASSIN]:
            # Get the drone
            drone = Manager.__all_drones[ship_id]
            if drone.target is None:
                # Look for the closest ship of our nemesis that is docked
                distance, enemy_ship = drone.get_furthest_ship(player_id=nemesis, docked_only=True)
                #If we've found a docked ship
                if enemy_ship is not None:
                    drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)
                # If there are no docked ship
                else:
                    # move to the gravitational center of our nemesis
                    center = Monitor.gravitational_center(nemesis)
                    position = Position(center.x, center.y, center.radius)
                    distance = calculate_distance_between(drone.ship.pos, position.pos)
                    # Assign the target
                    drone.assign_target(position, distance, target_type=TargetType.POSITION)

    @staticmethod
    def order_attacker():
        """
        [EVERY TURN]
        Main IA function for all drone with ATTACKER role
            - Loop through all Attacker
            - Don't change drone with valid target
            - Look for a target for drone without one: closest enemy ship
            - At the end every attacker should have a target
        :return:
        """

        # Get the current nemesis
        nemesis = Monitor.find_nemesis()

        # Loop through all drone
        for ship_id in list(Manager.__all_role_drones[DroneRole.ATTACKER]):
            # Get the drone
            drone = Manager.__all_drones[ship_id]
            # If the drone has currently no target, look for one
            # if drone.target is None:
            # Look for the closest ship of our nemesis
            #distance, enemy_ship = drone.get_closest_ship(player_id=nemesis)
            distance, enemy_ship = drone.get_closest_ship()
            # Check if there is an enemy around the ship
            if distance <= SAFE_ZONE_RADIUS:
                # Attack this ship
                drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)
            else:
                # Check that the drone can't become a conqueror for "free"
                if Influence.is_in_planet_zone(drone.ship.pos):
                    # Get the planet_id
                    planet_id = Influence.get_planet_influence(drone.ship.pos)
                    # Make sure the planet is still free
                    if Monitor.get_nb_spots_for_miners(planet_id) > 0:
                        # Change role to CONQUEROR
                        Manager.change_drone_role(drone, DroneRole.CONQUEROR)
                        # Get the planet
                        planet = Monitor.get_planet(planet_id)
                        # Calculate the distance
                        distance = calculate_distance_between(planet.pos, drone.ship.pos)
                        # Add the target to the drone
                        drone.assign_target(planet, distance, target_type=TargetType.PLANET)
                        #Add the drone to the list of miner
                        Monitor.add_planets_miner(planet.id, drone.ship.id)
                        # Skip to next drone
                        continue

                # If there are no enemy and no free planet close, look for an enemy inside the influence zone
                influence_distance, influence_enemy_ship = drone.get_closest_ship_in_influence()
                if influence_enemy_ship is not None:
                    # Assign the new target, if any available
                    drone.assign_target(influence_enemy_ship, influence_distance, target_type=TargetType.SHIP)
                else:
                    # Attack the closest ship
                    drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)



    @staticmethod
    def order_miner():
        """
        [EVERY TURN]
        Main IA function for all drone with MINER role
            - Loop through all Miner
            - Check if an enemy ship is close, switch to defender mode if it's the case
            - Drone get no target with this IA
        :return:
        """
        # Loop through all drone to look for an enemy
        for ship_id in list(Manager.__all_role_drones[DroneRole.MINER]):
            # Get the drone
            drone = Manager.__all_drones[ship_id]
            # By default miner can't defend
            if MINER_CAN_DEFEND:
                # Check if the drone needs to become a defender
                Manager.check_drone_defense(drone)
            # Check if a miner is not stuck at mining an impossible spot
            if drone.ship.DockingStatus == Ship.DockingStatus.UNDOCKED and not drone.can_dock(drone.target):
                # Reset this drone back to conqueror
                Manager.change_drone_role(drone, DroneRole.CONQUEROR)

    # Give an order to every conquerors
    @staticmethod
    def order_conquerors():
        """
        [EVERY TURN]
        Main IA function for all drone with CONQUEROR role
        The main objective for a CONQUEROR is to become a MINER
            - Loop through all Conquerors
            - Check if an enemy ship is close, switch to defender mode if it's the case
            - Don't change drone with valid target
            - Look for a target for drone without one: closest free planet that is not full
            - If no Free planet left: convert the drone to an attacker
            - At the end every conquerors should have a target + some of them can be converted to attackers
        :return:
        """


        list_drone_no_target = []
        # Loop once through all conqueror drone to handle drone with target
        for ship_id in list(Manager.__all_role_drones[DroneRole.CONQUEROR]):
            # Get the drone
            drone = Manager.__all_drones[ship_id]

            # Defend itself if needed
            became_attacker = Manager.check_drone_surrounding(drone)
            if became_attacker:
                continue

            # Check if the drone has a valid target, skip it if so
            if drone.target is not None:
                # Now make sure its target is still a free planet
                if not drone.target.is_free(drone.ship.owner):
                    # Reset target
                    drone.reset_target()
                    # Add the drone to no_target list
                    list_drone_no_target.append(drone)
                    # Skip to next drone
                    continue

                # First, make sure that if the ship can dock to its target!
                if drone.can_dock(drone.target):
                    # Store old target
                    target = drone.target
                    # Change role to miner
                    Manager.change_drone_role(drone, DroneRole.MINER)
                    # Ask for the drone to dock
                    drone.docking(target)
                    # Skip to next drone
                    continue

            else:
                # Add the drone to no_target list
                # Skip to next ship, if it has no target
                list_drone_no_target.append(drone)
                continue

        # Find a target for drone without target
        for drone in list_drone_no_target:
            # Check if there are still some spots for miners to go
            if Monitor.map_has_available_spots_for_miners():
                # Now, look for a suitable empty planet
                for distance, target_planet in drone.get_free_planet_by_score():
                    # Check if we can still find an available docking spot on this planet
                    if Monitor.get_nb_spots_for_miners(target_planet.id) > 0:
                        drone.assign_target(target_planet, distance, target_type=TargetType.PLANET)
                        # Add the drone to the list of miners of the planet
                        Monitor.add_planets_miner(target_planet.id, drone.ship.id)

                        # Check if by chance the drone can dock to its new target, to avoid loosing a turn
                        if drone.can_dock(drone.target):
                            # Store old target
                            target = drone.target
                            # Change role to miner
                            Manager.change_drone_role(drone, DroneRole.MINER)
                            # Ask for the drone to dock
                            drone.docking(target)

                        break
            else:
                # If there are no spot available, make it an attacker
                # Change role to attacker
                Manager.change_drone_role(drone, DroneRole.ATTACKER)

    @staticmethod
    def order_defender():
        """
        [EVERY TURN]
        Main IA function for all drone with DEFENDER role
            - Loop through all Defenders
            - Make sure to undock the ship if needed
            - Don't change drone with valid target
            - Look for a target for drone without one: closest enemy ship
            - At the end every defenders should have a target or be undocking
        :return:
        """
        # Loop through all drone
        for ship_id in Manager.__all_role_drones[DroneRole.DEFENDER]:
            # Get the drone
            drone = Manager.__all_drones[ship_id]
            # Get Ship
            ship = drone.ship
            # If the ship is not undocked, undock it
            if ship.docking_status != Ship.DockingStatus.UNDOCKED:
                # Set target to undocking
                drone.undocking()
            # If the ship is undocked, send it to attack
            else:
                # Decrease defender time by one
                drone.defender_timer -= 1
                # Look for the closest ship, defender don't look for nemesis, just attack the closest
                distance, score, enemy_ship = drone.get_dangerous_ship()
                if (enemy_ship is not None) and (score < MIN_SCORE_DEFENSE):
                    drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)
                # If there are no dangerous ship in range
                else:
                    # Move toward the defense point
                    defense_point = Monitor.defense_point()
                    # Calculate position because there are no cache for this distance
                    distance = calculate_distance_between(drone.ship.pos, defense_point.pos)
                    # Make it the new target (ship type?)
                    drone.assign_target(defense_point, distance, target_type=TargetType.POSITION)

    @staticmethod
    def order_free_planet():
        # Loop through all free planet
        for planet in Monitor.get_free_planets():
            # Look for free planet that still need some conqueror
            if planet.nb_available_docking_spots() > len(Monitor.get_planets_miners()):
                # Look for drone around the planet to assign one
                # TODO: continue here
                pass


    @staticmethod
    def create_command_queue():
        """
        Loop through all the drone and their target to generate a list of command
        If there are more than NB_SHIP_THRESHOLD ships:
            - Sort the drone by target_distance to prioritise ship
        Exit the loop if we have spent more than MAX_TURN_DURATION sec in this turn
        :return: command_queue for the game to process
        """

        command_queue = []
        # Get the list of drone and their target's distance
        # Split the list in 2
        # Target with distance
        list_drone_distance = []
        # Target without distance
        list_drone_no_distance = []
        for ship_id, drone in Manager.__all_drones.items():
            # if it's already docking, do nothing
            if (drone.ship.docking_status == Ship.DockingStatus.DOCKING) or (
                        drone.ship.docking_status == Ship.DockingStatus.UNDOCKING):
                # Skip to next drone
                continue
            # If the drone has a target (and so a distance)
            if (drone.target is not None) and (drone.target_type != TargetType.DOCKING):
                list_drone_distance.append([drone.target_distance, drone])
            # Otherwise it's docking/undocking
            else:
                list_drone_no_distance.append(drone)

        # Easy part, handle all docking/undocking drone
        for drone in list_drone_no_distance:
            if drone.target_type == TargetType.DOCKING:
                command = drone.ship.dock(drone.target)
                if command:
                    command_queue.append(command)
            else:
                command = drone.ship.undock()
                if command:
                    command_queue.append(command)

        # Now ships with target
        # If there are more ship than NB_SHIP_THRESHOLD
        if len(Monitor.get_all_ships_dict()) > NB_SHIP_THRESHOLD:
            # order the list by target distance
            list_drone_distance = sorted(list_drone_distance, key=lambda l: l[0])

        # Try to send the commands if we are getting close to MAX_TURN_DURATION sec
        # Check time every 10 ships or so
        nb = 0
        nb_target_ship = 0
        nb_target_planet = 0
        # Loop through all drone order by distance ASC
        for distance, drone in list_drone_distance:
            nb += 1
            # if the target is a ship
            if drone.target_type == TargetType.SHIP:
                nb_target_ship += 1
                if drone.role == DroneRole.ASSASSIN:
                    if drone.is_damaged:
                        logging.info("Go suicide assassin ship : %s" % drone.target.id)
                        command = Manager.__suicide_ship_command(drone.ship, drone.target, assassin=True)
                    else:
                        logging.info("Go assassin ship : %s" % drone.target.id)
                        command = Manager.__attack_ship_command(drone.ship, drone.target, assassin=True)
                    if command:
                        command_queue.append(command)
                elif drone.role == DroneRole.DEFENDER:
                    if drone.target_type == TargetType.SHIP:
                        logging.info("Go intercept ship : %s" % drone.target.id)
                        command = Manager.__intercept_ship(drone.ship, drone.target, distance)
                    else:
                        logging.info("Go to defense position: %s" % drone.target.pos)
                        command = Manager.__navigate_target(drone.ship, drone.target, closest = False)
                    if command:
                        command_queue.append(command)
                else:
                    logging.info("Go attack ship : %s" % drone.target.id)
                    command = Manager.__attack_ship_command(drone.ship, drone.target)
                    if command:
                        command_queue.append(command)

            # If the target is a planet
            else:
                nb_target_planet += 1
                command = Manager.__conquer_ship_command(drone.ship, drone.target)
                if command:
                    command_queue.append(command)
            # Check time every 5 ships
            if nb % 5 == 0:
                end_time = datetime.utcnow()
                duration = (end_time - Manager.turn_start_time).total_seconds()
                # if the duration is more than MAX_TURN_DURATION break the loop
                if duration > MAX_TURN_DURATION:
                    # Leave the loop
                    break

        logging.info("Sent command to attack %s ship and navigate to %s planet" % (nb_target_ship, nb_target_planet))
        return command_queue
