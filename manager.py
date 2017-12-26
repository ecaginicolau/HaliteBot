from drone import DroneRole, TargetType, Drone
from hlt.constants import *
from hlt.entity import Ship
import math
import logging
from datetime import datetime
from monitor import Monitor

logger = logging.getLogger("manager")

# Some global
# Max ratio of ship sent to the same planet, avoid all ship going to the same planet
MAX_RATIO_SHIP_PER_PLANET = 0.5
# Always try to have at least 1 ship attacking (if not alone?)
MIN_SHIP_ATTACKERS = 1
# Even if there are still some available planet, send a portion of the ship to attack
MAX_RATIO_SHIP_ATTACKERS = 0.25
# NB of docked ship per planet
MAX_NB_DOCKED_SHIP = 5
# Radius inside which an enemy must be for a drone to become a defender
DEFENDER_RADIUS = 10
# Special radius for miner to react faster
MINER_DEFENDER_RADIUS = 10
# If the turn takes more than this, just exit
MAX_TURN_DURATION = 1.8
# Arbitrary threshold after which we need to sort ship by distance
NB_SHIP_THRESHOLD = 130

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

    def __init__(self, player_id):
        # Create the game monitor
        self.monitor = Monitor(player_id)

        # Store the player id, will be used to distinguish ships
        self.player_id = player_id
        # Internal counters
        self.__nb_dead_drone = 0

        # Store every  drone, indexed by ship_id
        self.__all_drones = {}

        # Store every drone indexed by role for easy lookup
        self.__all_role_drones = {}
        # Initialise the dictionnay of role
        for role in DroneRole:
            self.__all_role_drones[role] = []

        # Will store all ships in dictionary, should be updated every turn
        self.__enemy_ships_dict = {}
        # Will store team ships in dictionary, should be updated every turn
        self.__team_ships_dict = {}

        # Store the game_map
        self.game_map = None

        # Store planets owner by enemies
        self.__enemy_planets = []

        # Store planet owned by the player
        self.__team_planets = []

        # Store planets empty as dictionary for fast lookup, index as planet.id
        self.__empty_planets = {}

        # Store the start_time of the current_turn
        self.turn_start_time = None
        logger.info("New manager created for player: %s" % self.player_id)

    def update_game_map(self, game_map, start_time):
        """
        [EVERY TURN]
        # Update the game map for both the manager & the monitor
        :param game_map: the game_map for the current_turn
        :param start_time: the start time (datetime utc) for the current turn
        :return:
        """
        # Send the game_map to the monitor
        self.monitor.update_game(game_map)
        # Update the turn start_time
        self.turn_start_time = start_time
        # update the game map itself
        self.game_map = game_map
        # Reset turn's variable
        self.__enemy_planets = []
        self.__team_planets = []
        self.__empty_planets = {}
        # Loop through all planet, look for empty, enemy or team planets
        for planet in self.game_map.all_planets():
            if not planet.is_owned():
                self.__empty_planets[planet.id] = planet
            else:
                if planet.owner.id == self.player_id:
                    self.__team_planets.append(planet)
                else:
                    self.__enemy_planets.append(planet)

        logger.info("Empty planets: %s, Owned planets: %s, Enemy planets: %s" % (len(self.__empty_planets),
                                                                                 len(self.__team_planets),
                                                                                 len(self.__enemy_planets)))

    # Return the role of  asingle ship
    def get_ship_role(self, ship_id):
        try:
            return self.__all_drones[ship_id].role
        except KeyError:
            return DroneRole.UNKNOWN

    # Change the role of a single drone
    def change_drone_role(self, drone, role):
        # Reset drone target, invalid if changing role
        drone.reset_target()
        # Store the old role
        old_role = drone.role
        # Remove from the old list
        self.__all_role_drones[old_role].remove(drone.ship_id)
        # Add to the new list
        try:
            self.__all_role_drones[role].append(drone.ship_id)
        except KeyError:
            self.__all_role_drones[role] = [drone.ship_id]
        # Change internal drone role
        drone.role = role

    # Add a new ship to the fleet
    def add_ship(self, ship, role=DroneRole.IDLE):
        # First check if the drone exist
        try:
            drone = self.__all_drones[ship.id]
            # Remove the drone from the old list
            logger.warning("Drone already exist, changing role instead")
            self.change_drone_role(drone, role)
        except KeyError:
            self.__all_drones[ship.id] = Drone(ship=ship, role=role)
            try:
                self.__all_role_drones[role].append(ship.id)
            except KeyError:
                self.__all_role_drones[role] = [ship.id]
            logger.info("Added a new ship with the role: %s" % self.get_ship_role(ship.id))

    def check_for_dead_drones(self):
        """
        [EVERY TURN]
        Loop through all drone to remove dead drone from the list
            - If the drone's ship can't be found in the current list of ship it means it's dead
        :return:
        """
        for ship_id in list(self.__all_drones.keys()):
            drone = self.__all_drones[ship_id]
            try:
                # If we can find the ship
                ship = self.__team_ships_dict[ship_id]
                # Update it in the drone
                drone.update_ship(ship)
            except KeyError:
                # Ship can't be found, so drone is dead
                self.__nb_dead_drone += 1
                # Get the old role
                old_role = drone.role
                # Remove from the list of current role
                self.__all_role_drones[old_role].remove(ship_id)
                # Remove from the list of all drone
                del self.__all_drones[ship_id]
        logger.info("In total %s drone died" % self.__nb_dead_drone)

    def update_list_ship(self):
        """
        [EVERY TURN]
        Get the new list of ship for this turn
            - Update both enemy & team list of ship into a dictionnay indexed by ship.id
        :return:
        """

        list_ships = self.game_map._all_ships()
        self.__enemy_ships_dict = {}
        self.__team_ships_dict = {}
        for ship in list_ships:
            if ship.owner.id == self.player_id:
                self.__team_ships_dict[ship.id] = ship
            else:
                self.__enemy_ships_dict[ship.id] = ship
        logger.info("Found %s ship in my team" % len(self.__team_ships_dict))
        logger.info("Found %s ship in enemy team" % len(self.__enemy_ships_dict))
        logger.info("Found a total  of %s ship" % (len(self.__enemy_ships_dict) + len(self.__team_ships_dict)))

    def check_for_new_ship(self):
        """
        [EVERY TURN]
        Look for newly created ship, convert them to drone
            - If the ship has no drone (role == UNKNOWN), create a drone
            - At the end, no unknown drone should remain
        :return:
        """
        for ship_id, ship in self.__team_ships_dict.items():
            # If the current ship has no role, assign it as IDLE (new ship)
            if self.get_ship_role(ship_id) == DroneRole.UNKNOWN:
                self.add_ship(ship=ship, role=DroneRole.IDLE)

    def check_defender_timer(self):
        """
        [EVERY TURN]
        Decrease the timer for every defenders
            - Return the drone to idle if no time left
        :return:
        """
        # Loop through all defenders
        for ship_id in list(self.__all_role_drones[DroneRole.DEFENDER]):
            # Get the drone
            drone = self.__all_drones[ship_id]
            # If there is no defense time left
            if drone.defender_timer <= 0:
                # Change the drone back to it's previous role
                # Get previous role
                previous_role = drone.get_previous_role()
                # Drone can't return to Miner, so switch it to IDLE it was a miner
                if previous_role != DroneRole.MINER:
                    self.change_drone_role(drone, DroneRole.IDLE)
                else:
                    # Change if back to its previous role
                    self.change_drone_role(drone, previous_role)
    def check_damaged_drone(self):
        """
        [EVERY TURN]
        Loop through all drone to check if they are damaged
            - Convert them to defender if they are damaged
        :return:
        """
        nb_damaged = 0
        for ship_id, drone in self.__all_drones.items():
            drone = self.__all_drones[ship_id]
            if self.__team_ships_dict[ship_id].health != drone.max_health:
                # If it's not a defender, make it a defender
                if drone.role != DroneRole.DEFENDER:
                    nb_damaged += 1
                    self.change_drone_role(drone, DroneRole.DEFENDER)
        logger.info("Found %s damaged ship" % nb_damaged)

    def role_status(self):
        """
        Return the number of drone for each role, for debug purpose
        :return: a dictionnay with the role as index containing the number of drone for each role
        """
        role_counter = {}
        for role in DroneRole:
            role_counter[role] = self.nb_drone_role(role)
            logger.info("Role: %s, count: %s" % (role, role_counter[role]))
        return role_counter

    def nb_drone_role(self, role):
        """
        Count the number of drone of specific role
        :param role:
        :return: the number of drone of the role
        """
        try:
            return len(self.__all_role_drones[role])
        except KeyError:
            return 0

    def give_role_idle_drone(self):
        """
        [EVERY TURN]
        Loop through all idle drone to give them a role
            - Always try to have some attackers : between MIN_SHIP_ATTACKERS & MAX_RATIO_SHIP_ATTACKERS
            - All remaining drone are defaulted to CONQUEROR
            - At the end no idle drone should remains
        :return:
        """

        # If there are Idle drones
        if self.nb_drone_role(DroneRole.IDLE) > 0:
            # First:  There are still empty planets:
            if len(self.__empty_planets) > 0:
                """
                #Give the Attacker role
                """
                # Calculate the ratio of attacker / total drone
                current_ratio = self.nb_drone_role(DroneRole.ATTACKER) / float(self.nb_drone_role(DroneRole.ATTACKER) +
                                                                               self.nb_drone_role(DroneRole.CONQUEROR) +
                                                                               self.nb_drone_role(DroneRole.IDLE))
                logger.debug(
                    "OLD nb_attackers: %s, current_ratio: %s" % (self.nb_drone_role(DroneRole.ATTACKER), current_ratio))

                # First make sure there are enough attacker
                while ((self.nb_drone_role(DroneRole.ATTACKER) < MIN_SHIP_ATTACKERS) or (
                            current_ratio < MAX_RATIO_SHIP_ATTACKERS)) \
                        and (self.nb_drone_role(DroneRole.IDLE) > 0):
                    # Change an IDLE Drone to attacker
                    # Pick a IDLE drone
                    # TODO Look for the closest ship to an enemy
                    ship_id = self.__all_role_drones[DroneRole.IDLE][0]
                    drone = self.__all_drones[ship_id]
                    self.change_drone_role(drone, DroneRole.ATTACKER)
                    current_ratio = self.nb_drone_role(DroneRole.ATTACKER) / float(
                        self.nb_drone_role(DroneRole.ATTACKER) +
                        self.nb_drone_role(DroneRole.CONQUEROR) +
                        self.nb_drone_role(DroneRole.IDLE))
                logger.debug(
                    "NEW nb_attackers: %s, current_ratio: %s" % (self.nb_drone_role(DroneRole.ATTACKER), current_ratio))

                """
                #Give the Conqueror role
                """
                # Affect all remaining idle to conqueror role
                logger.debug("OLD nb_conqueror: %s" % self.nb_drone_role(DroneRole.CONQUEROR))
                # Copythe list of ship_id for modification
                list_ship_id = list(self.__all_role_drones[DroneRole.IDLE])
                for ship_id in list_ship_id:
                    drone = self.__all_drones[ship_id]
                    self.change_drone_role(drone, DroneRole.CONQUEROR)
                logger.debug("NEW nb_conqueror: %s" % self.nb_drone_role(DroneRole.CONQUEROR))
            # Else: there are no empty planets : default role = ATTACKER
            else:
                """
                #Give the Attacker role
                """
                # Affect all remaining idle to conqueror role
                logger.debug("OLD nb attacker: %s" % self.nb_drone_role(DroneRole.ATTACKER))
                # Copythe list of ship_id for modification
                list_ship_id = list(self.__all_role_drones[DroneRole.IDLE])
                for ship_id in list_ship_id:
                    drone = self.__all_drones[ship_id]
                    self.change_drone_role(drone, DroneRole.ATTACKER)
                logger.debug("NEW nb attacker: %s" % self.nb_drone_role(DroneRole.ATTACKER))

    def check_drone_target(self):
        """
        [EVERY TURN]
        Check if the drones's target are still valid and update them
            - Loop through all drone
            - If the drone has a target
                - If the target is a ship, make sure it's still alive. Update the target it if so, otherwise reset it
                - If the target is a planet, make sure it's still empty. Update the target it if so, otherwise reset it
        :return:
        """
        for ship_id, drone in self.__all_drones.items():
            # If the drone had a target already
            if drone.target_id is not None:
                # If the drone is currently targeting a ship
                if drone.target_type == TargetType.SHIP:
                    # Make sure the enemy ship is still alive, update the target if so
                    try:
                        drone.target = self.__enemy_ships_dict[drone.target_id]
                    except KeyError:
                        # The target is dead, reset the target
                        drone.reset_target()
                        # Skip to next ship
                        continue
                # If the drone is currently targeting a planet
                if drone.target_type == TargetType.PLANET:
                    # Check if the planet is still empty Update the planet's target
                    try:
                        drone.target = self.__empty_planets[drone.target_id]
                    except KeyError:
                        # The planet is not empty anymore, reset the target
                        drone.reset_target()
                        # Skip to next ship
                        continue

    def __look_for_closest_ship(self, ship, player_id=None):
        """
        This function will loop through all enemy ship to look for the closest ship
        :param ship:
        :param player_id: if playerid is not None : look only for enemy ship of this player
        :return: both the target and the distance between the ship and the target (for computation optimization)
        """
        # set min_distance to an arbitrary huge number
        min_distance = 9999
        # Prepare the target
        target = None
        # Loop through all enemy ship
        for enemy_id, enemy_ship in self.__enemy_ships_dict.items():
            # If we don't need a specific player ship or if the ship is owned by the correct player
            if (player_id is None) or (enemy_ship.owner.id == player_id):
                # Calculate the distance
                distance = ship.calculate_distance_between(enemy_ship)
                # If the distance is smaller than the current target
                if distance < min_distance:
                    # Update the distance
                    min_distance = distance
                    # update the target
                    target = enemy_ship
        # In the end return the target
        return target, min_distance

    def __navigate_target(self, ship, target):
        """
        Simple method to create a command to attack the closest ship
        :param ship:
        :return: the navigate command
        """
        navigate_command = None
        if target is not None:
            navigate_command = ship.navigate(
                ship.closest_point_to(target),
                self.game_map,
                speed=int(MAX_SPEED),
                angular_step=5,
                ignore_ships=False)

        return navigate_command

    def __attack_ship_command(self, ship, target):
        """
        Simple method to create a command to attack a target ship
        :param ship:
        :return: the navigate command
        """
        return self.__navigate_target(ship, target)

    def __conquer_ship_command(self, ship, target):
        """
        Simple method to create a command to conquer a target planet
        :param ship:
        :return: the navigate command
        """
        return self.__navigate_target(ship, target)

    def order_attacker(self):
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
        nemesis = self.monitor.find_nemesis()

        # Loop through all drone
        for ship_id in self.__all_role_drones[DroneRole.ATTACKER]:
            # Get the drone
            drone = self.__all_drones[ship_id]

            # Look for the closest ship overall
            target, distance = self.__look_for_closest_ship(drone.ship)

            # If the drone already has a target, only react to very close ship
            if drone.target is not None:
                #If the closest ship is closest than defender radius, chance target
                if distance < DEFENDER_RADIUS :
                    drone.assign_target(target, distance, target_type=TargetType.SHIP)
                # New target or not: Skip to next drone
                continue

            # Look for the closest ship of our nemesis
            target, distance = self.__look_for_closest_ship(drone.ship, nemesis)
            # Assign the new target, if any
            if target is not None:
                drone.assign_target(target, distance, target_type=TargetType.SHIP)

    def order_miner(self):
        """
        [EVERY TURN]
        Main IA function for all drone with MINER role
            - Loop through all Miner
            - Check if an enemy ship is close, switch to defender mode if it's the case
            - Drone get no target with this IA
        :return:
        """
        # Loop through all drone to look for an enemy
        for ship_id in list(self.__all_role_drones[DroneRole.MINER]):
            # Get the drone
            drone = self.__all_drones[ship_id]

            # Check if enemies are in the radius of defense
            # If the drone has not exhausted its defender_time
            if drone.defender_timer > 0:
                became_defender = False
                for enemy_id, enemy in self.__enemy_ships_dict.items():
                    # Calculate the distance with each enemy ship
                    distance = drone.ship.calculate_distance_between(enemy)
                    # If an enemy ship is too close enter defender role
                    if distance <= MINER_DEFENDER_RADIUS:
                        # Change drone role to DEFENDER
                        self.change_drone_role(drone, DroneRole.DEFENDER)
                        became_defender = True
                        # No need to look for more ships
                        break
                # Make sure to no run conqueror orders if it became a defender
                if became_defender:
                    # Skip to next ship
                    continue

    # Give an order to every conquerors
    def order_conquerors(self):
        """
        [EVERY TURN]
        Main IA function for all drone with CONQUEROR role
            - Loop through all Conquerors
            - Check if an enemy ship is close, switch to defender mode if it's the case
            - Don't change drone with valid target
            - Look for a target for drone without one: closest empty planet that is not full
            - If no empty planet left: convert the drone to an attacker
            - At the end every conquerors should have a target + some of them can be converted to attackers
        :return:
        """

        # Store the number of ship per planet, to avoid crowded planets
        nb_ship_per_planet = {}

        # Fast/Easy code : there are no empty planets convert all drone to Attackers
        # Could be handled by folling code but much slower
        if len(self.__empty_planets) == 0:
            """
            #Give the Attackers role
            """
            # Affect all remaining idle to conqueror role
            logger.debug("[Transfert all attackers] OLD nb ATTACKER: %s" % self.nb_drone_role(DroneRole.ATTACKER))
            # Copy the list of ship_id for modification
            list_ship_id = list(self.__all_role_drones[DroneRole.CONQUEROR])
            for ship_id in list_ship_id:
                drone = self.__all_drones[ship_id]
                self.change_drone_role(drone, DroneRole.ATTACKER)
            logger.debug("[Transfert all attackers]NEW nb ATTACKER: %s" % self.nb_drone_role(DroneRole.ATTACKER))
            return

        # Loop through all conqueror drone
        for ship_id in list(self.__all_role_drones[DroneRole.CONQUEROR]):
            # Get the drone
            drone = self.__all_drones[ship_id]
            ship = drone.ship

            # Check if enemies are in the radius of defense
            # If the drone has not exhausted its defender_time
            if drone.defender_timer > 0:
                became_defender = False
                for enemy_id, enemy in self.__enemy_ships_dict.items():
                    # Calculate the distance with each enemy ship
                    distance = ship.calculate_distance_between(enemy)
                    # If an enemy ship is too close enter defender role
                    if distance <= DEFENDER_RADIUS:
                        # Change drone role to DEFENDER
                        self.change_drone_role(drone, DroneRole.DEFENDER)
                        became_defender = True
                        # No need to look for more ships
                        break
                # Make sure to no run conqueror orders if it became a defender
                if became_defender:
                    logger.debug("Created a defender")
                    # Skip to next ship
                    continue

            # Check if the drone has a valid target, skip it if so
            if drone.target is not None:
                # First, make sure that if the ship can dock to its target!
                if ship.can_dock(drone.target):
                    # Store old target
                    target = drone.target
                    # Change role to miner
                    self.change_drone_role(drone, DroneRole.MINER)
                    # Ask for the drone to dock
                    drone.docking(target)
                # Skip to next ship, if it has docked or not
                continue

            # Get the list of empty planets planets and calculate their distance
            list_empty = []
            for planet_id, planet in self.__empty_planets.items():
                distance = ship.calculate_distance_between(planet)
                list_empty.append([distance, planet])

            # Sort list by distance ASC
            list_empty = sorted(list_empty, key=lambda l: l[0])

            # Get the list owned empty planets planets and calculate their distance
            list_owned = []
            for planet in self.__team_planets:
                distance = ship.calculate_distance_between(planet)
                list_owned.append((distance, planet))

            # Sort list by distance ASC
            list_owned = sorted(list_owned, key=lambda l: l[0])
            # Only keep the planet, we don't need the distance anymore
            list_owned = [p[1] for p in list_owned]

            """
            # First, make sure that if the ship can do the closest empty planet it docks!
            if ship.can_dock(list_empty[0][1]):
                # Change role to miner
                self.change_drone_role(drone, DroneRole.MINER)
                # Ask for the drone to
                drone.docking(list_empty[0][1])
                # Skip to next drone
                continue
            """

            # Then, if it can dock to the closest owned planet, make sure that there are not too many docked ship
            if (len(list_owned) > 0) and (not list_owned[0].is_full()) and (ship.can_dock(list_owned[0])):
                if len(list_owned[0].all_docked_ships()) < min(MAX_NB_DOCKED_SHIP, len(list_owned)):
                    # Change the role of the Drone to Miner
                    drone = self.__all_drones[ship_id]
                    self.change_drone_role(drone, DroneRole.MINER)
                    drone.docking(list_owned[0])
                    # Skip to next drone
                    continue

            # Now, look for a suitable empty planet
            for distance, target_planet in list_empty:
                try:
                    nb_ship_per_planet[target_planet.id] += 1
                except KeyError:
                    nb_ship_per_planet[target_planet.id] = 1

                # Only send a ship if there is less than half of the current ship going to this destination
                if nb_ship_per_planet[target_planet.id] > math.ceil(
                                len(self.__all_role_drones[DroneRole.CONQUEROR]) * MAX_RATIO_SHIP_PER_PLANET):
                    logger.debug("Reroute the ship to another planet, too many ship already going there")
                    # This ship is not going there anymore, remove from the counter
                    nb_ship_per_planet[target_planet.id] -= 1
                    # Skip to next planet in the list
                    continue
                else:
                    # We've found a valid target, let's assign it
                    drone.assign_target(target_planet, distance, target_type=TargetType.PLANET)
                    # Exit target planet loop
                    break

    def order_defender(self):
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
        for ship_id in self.__all_role_drones[DroneRole.DEFENDER]:
            # Get the drone
            drone = self.__all_drones[ship_id]
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
                target, distance = self.__look_for_closest_ship(ship)
                if target is not None:
                    drone.assign_target(target, distance, target_type=TargetType.SHIP)

    def create_command_queue(self):
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
        for ship_id, drone in self.__all_drones.items():
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
        if len(list_drone_distance) > NB_SHIP_THRESHOLD:
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
                logger.info("Go attack ship : %s" % drone.target.id)
                command = self.__attack_ship_command(drone.ship, drone.target)
                if command:
                    command_queue.append(command)
            # If the target is a planet
            else:
                nb_target_planet += 1
                command = self.__conquer_ship_command(drone.ship, drone.target)
                if command:
                    command_queue.append(command)
            # Check time every 10 ships
            if nb % 10 == 0:
                end_time = datetime.utcnow()
                duration = (end_time - self.turn_start_time).total_seconds()
                # if the duration is more than MAX_TURN_DURATION break the loop
                if duration > MAX_TURN_DURATION:
                    # Leave the loop
                    break

        logger.info("Sent command to attack %s ship and navigate to %s planet" % (nb_target_ship, nb_target_planet))
        return command_queue
