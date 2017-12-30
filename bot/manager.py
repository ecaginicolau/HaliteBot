# Python imports
import logging
from datetime import datetime
# Bot imports
from bot.monitor import Monitor
from bot.drone import DroneRole, TargetType, Drone
from bot.settings import MIN_SHIP_ATTACKERS, MAX_RATIO_SHIP_ATTACKERS, DEFENDER_RADIUS, NB_SHIP_THRESHOLD,\
    MAX_TURN_DURATION, MINER_CAN_DEFEND, MINER_DEFENDER_RADIUS
# hlt imports
from hlt.constants import *
from hlt.entity import Ship

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

        # Store the game_map
        self.game_map = None

        # Store the start_time of the current_turn
        self.turn_start_time = None
        logging.info("New manager created for player: %s" % self.player_id)

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

    # Return the role of a single ship
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
            logging.warning("Drone already exist, changing role instead")
            self.change_drone_role(drone, role)
        except KeyError:
            self.__all_drones[ship.id] = Drone(ship=ship, role=role)
            try:
                self.__all_role_drones[role].append(ship.id)
            except KeyError:
                self.__all_role_drones[role] = [ship.id]
            logging.info("Added a new ship with the role: %s" % self.get_ship_role(ship.id))

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
                ship = self.monitor.get_ship(ship_id)
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
        logging.info("In total %s drone died" % self.__nb_dead_drone)

    def check_for_new_ship(self):
        """
        [EVERY TURN]
        Look for newly created ship, convert them to drone
            - If the ship has no drone (role == UNKNOWN), create a drone
            - At the end, no unknown drone should remain
        :return:
        """

        for ship_id in self.monitor.get_team_ships():
            # Get the ship
            ship = self.monitor.get_ship(ship_id)
            # If the current ship has no role, assign it as IDLE (new ship)
            if self.get_ship_role(ship_id) == DroneRole.UNKNOWN:
                self.add_ship(ship=ship, role=DroneRole.IDLE)

    def calculate_all_drones_distance(self):
        """
        Calculate between all drones and all ships, once and for all!
        :return:
        """
        for _, drone in self.__all_drones.items():
            if drone.role != DroneRole.MINER:
                drone.calculate_all_ships_distance(self.monitor.get_all_ships_dict())
                drone.calculate_all_planets_distance(self.monitor.get_all_planets_dict())

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
            if self.monitor.get_ship(ship_id).health != drone.max_health:
                # Miner should never move
                if drone.role != DroneRole.MINER:
                    # If it's not a defender, make it a defender
                    if drone.role != DroneRole.DEFENDER:
                        nb_damaged += 1
                        self.change_drone_role(drone, DroneRole.DEFENDER)
        logging.info("Found %s damaged ship" % nb_damaged)

    def role_status(self):
        """
        Return the number of drone for each role, for debug purpose
        :return: a dictionnay with the role as index containing the number of drone for each role
        """
        role_counter = {}
        for role in DroneRole:
            role_counter[role] = self.nb_drone_role(role)
            logging.info("Role: %s, count: %s" % (role, role_counter[role]))
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

    def nb_offense(self):
        return self.nb_drone_role(DroneRole.ATTACKER) + self.nb_drone_role(DroneRole.ASSASSIN)

    def ratio_offense(self):

        """
        OLD METHOD
        current_ratio = (self.nb_drone_role(DroneRole.ATTACKER) + self.nb_drone_role(
            DroneRole.ASSASSIN)) / float(
            self.nb_drone_role(DroneRole.ATTACKER) + self.nb_drone_role(DroneRole.ASSASSIN) + self.nb_drone_role(
                DroneRole.CONQUEROR) + self.nb_drone_role(DroneRole.IDLE))
        """
        current_ratio = self.nb_offense() / float(len(self.__all_drones))

        return current_ratio

    def give_role_idle_drone(self):
        """
        [EVERY TURN]
        Loop through all idle drone to give them a role
            - Always try to have some attackers : between MIN_SHIP_ATTACKERS & MAX_RATIO_SHIP_ATTACKERS
            - All remaining drone are defaulted to CONQUEROR
            - At the end no idle drone should remains
        :return:
        """
        self.role_status()
        # If there are Idle drones
        if self.nb_drone_role(DroneRole.IDLE) > 0:
            # First:  There are still empty planets:
            if self.monitor.nb_empty_planets() > 0:
                """
                #Give the Attacker/Assassin role
                """
                # Calculate the ratio of attacker / total drone
                logging.debug("current_ratio: %s" % self.ratio_offense())
                # First make sure there are enough attacker
                while ((self.nb_offense() < MIN_SHIP_ATTACKERS) or (self.ratio_offense() < MAX_RATIO_SHIP_ATTACKERS)) \
                        and (self.nb_drone_role(DroneRole.IDLE) > 0):
                    # Change an IDLE Drone to attacker
                    # Pick a IDLE drone
                    # TODO Look for the closest ship to an enemy
                    ship_id = self.__all_role_drones[DroneRole.IDLE][0]
                    drone = self.__all_drones[ship_id]

                    # If there are no assassin, make an assassin
                    if self.nb_drone_role(DroneRole.ASSASSIN) == 0:
                        # Create an assassin
                        self.change_drone_role(drone, DroneRole.ATTACKER)
                    else:
                        # If there are more assassin than attacker
                        if self.nb_drone_role(DroneRole.ASSASSIN) >= self.nb_drone_role(DroneRole.ATTACKER):
                            # Create an assassin
                            self.change_drone_role(drone, DroneRole.ATTACKER)
                        else:
                            # Else create an attacker
                            self.change_drone_role(drone, DroneRole.ASSASSIN)
                    # Calculate the ratio of attacker / total drone
                    logging.debug("current_ratio: %s" % self.ratio_offense())

                """
                #Give the Conqueror role
                """
                # Affect all remaining idle to conqueror role
                # Copythe list of ship_id for modification
                list_ship_id = list(self.__all_role_drones[DroneRole.IDLE])
                for ship_id in list_ship_id:
                    drone = self.__all_drones[ship_id]
                    self.change_drone_role(drone, DroneRole.CONQUEROR)
            # Else: there are no empty planets : default role = ATTACKER
            else:
                """
                #Give the Attacker role
                """
                # Affect all remaining idle to conqueror role
                # Copythe list of ship_id for modification
                list_ship_id = list(self.__all_role_drones[DroneRole.IDLE])
                for ship_id in list_ship_id:
                    drone = self.__all_drones[ship_id]
                    self.change_drone_role(drone, DroneRole.ATTACKER)
        self.role_status()

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
                        drone.update_target(self.monitor.get_ship(drone.target_id))
                    except KeyError:
                        # The target is dead, reset the target
                        drone.reset_target()
                        # Skip to next ship
                        continue
                # If the drone is currently targeting a planet
                if drone.target_type == TargetType.PLANET:
                    # Check if the planet is still free
                    try:
                        target = self.monitor.get_planet(drone.target_id)
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

    def __navigate_target(self, ship, target):
        """
        Simple method to create a command to attack the closest ship
        :param ship:
        :return: the navigate command
        """
        logging.debug("Going to generate a navigate command between ship %s and target %s" % (ship.id, target.id))

        closest = ship.closest_point_to(target)
        logging.debug("Closest point to target: %s" % closest)
        navigate_command = None
        if target is not None:
            navigate_command = ship.navigate(
                closest,
                self.game_map,
                speed=int(MAX_SPEED),
                angular_step=1,
                ignore_planets=False,
                ignore_ships=False,
                ignore_ghosts=False,
            )
            logging.info("Navigation command: %s" % navigate_command)

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

    def check_drone_defense(self, drone):
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
        if distance <= MINER_DEFENDER_RADIUS:
            # Change drone role to DEFENDER
            self.change_drone_role(drone, DroneRole.DEFENDER)
            return True
        return False

    def order_assassin(self):
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
        nemesis = self.monitor.find_nemesis()

        # Loop through all drone
        for ship_id in self.__all_role_drones[DroneRole.ASSASSIN]:
            # Get the drone
            drone = self.__all_drones[ship_id]

            # Look for the closest ship of our nemesis
            distance, enemy_ship = drone.get_closest_ship(player_id=nemesis, docked_only=True)
            # Assign the new target, if any
            if enemy_ship is not None:
                drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)
            # Convert to ATTACKER if no target
            else:
                self.change_drone_role(drone, DroneRole.ATTACKER)

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
            distance, enemy_ship = drone.get_closest_ship()

            # If the closest ship is closest than defender radius, chance target
            if distance < DEFENDER_RADIUS:
                drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)
                # Skip to next drone
                continue

            # If the drone has currently no target, look for one
            if drone.target is None:
                # Look for the closest ship of our nemesis
                distance, enemy_ship = drone.get_closest_ship(player_id=nemesis)
                # Assign the new target, if any
                drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)

    def order_miner(self):
        """
        [EVERY TURN]
        Main IA function for all drone with MINER role
            - Loop through all Miner
            - Check if an enemy ship is close, switch to defender mode if it's the case
            - Drone get no target with this IA
        :return:
        """
        # By default miner can't defend
        if MINER_CAN_DEFEND:
            # Loop through all drone to look for an enemy
            for ship_id in list(self.__all_role_drones[DroneRole.MINER]):
                # Get the drone
                drone = self.__all_drones[ship_id]
                # Check if the drone needs to become a defender
                self.check_drone_defense(drone)

    # Give an order to every conquerors
    def order_conquerors(self):
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

        list_free_planet = self.monitor.get_free_planets()
        logging.info("Found %s free planets" % len(list_free_planet))

        # Keep the number of docking spot available by free planet
        dic_nb_available_spot = {}
        for planet in list_free_planet:
            dic_nb_available_spot[planet.id] = planet.nb_available_docking_spots()

        # Fast/Easy code : there are no free planets convert all drone to Attackers
        # Could be handled by folling code but much slower
        if len(list_free_planet) == 0:
            """
            #Give the Attackers role
            """
            # Affect all remaining idle to conqueror role
            logging.debug("[Transfert all attackers] OLD nb ATTACKER: %s" % self.nb_drone_role(DroneRole.ATTACKER))
            # Copy the list of ship_id for modification
            list_ship_id = list(self.__all_role_drones[DroneRole.CONQUEROR])
            for ship_id in list_ship_id:
                drone = self.__all_drones[ship_id]
                self.change_drone_role(drone, DroneRole.ATTACKER)
            logging.debug("[Transfert all attackers]NEW nb ATTACKER: %s" % self.nb_drone_role(DroneRole.ATTACKER))
            return

        list_drone_no_target = []
        # Loop once through all conqueror drone to handle drone with target
        for ship_id in list(self.__all_role_drones[DroneRole.CONQUEROR]):
            logging.debug("first conqueror loop: handling ship: %s" % ship_id)
            # Get the drone
            drone = self.__all_drones[ship_id]

            # Check if enemies are in the radius of defense
            became_defender = self.check_drone_defense(drone)
            if became_defender:
                # This conqueror became a defender, so don't continue for this drone
                logging.info("A conqueror became a defender")
                # Skip to next drone
                continue

            # Check if the drone has a valid target, skip it if so
            if drone.target is not None:
                logging.debug("Ship: %s has a target" % drone.ship.id)
                # Now make sure its target is still a free planet
                if drone.target.is_free(drone.ship.owner):
                    logging.debug("ship %s target is not free anymore" % drone.ship.id)
                    # Reset target
                    drone.reset_target()
                    # Add the drone to no_target list
                    list_drone_no_target.append(drone)
                    # Skip to next drone
                    continue

                # Reduce the number of available spot for the target by 1
                dic_nb_available_spot[drone.target.id] -= 1
                # First, make sure that if the ship can dock to its target!
                logging.info("Check if a drone can dock: ship.id: %s, planet.id: %s" % (drone.ship.id, drone.target.id))
                if drone.can_dock(drone.target):
                    # Store old target
                    target = drone.target
                    # Change role to miner
                    self.change_drone_role(drone, DroneRole.MINER)
                    # Ask for the drone to dock
                    drone.docking(target)
                    # Skip to next drone
                    continue

            else:
                # ADd the drone to no_target list
                # Skip to next ship, if it has no target
                list_drone_no_target.append(drone)
                continue

        # Find a target for drone without target
        for drone in list_drone_no_target:
            # Now, look for a suitable empty planet
            for distance, target_planet in drone.get_free_planet_by_score():
                # Check if we can still find an available docking spot on this planet
                if dic_nb_available_spot[target_planet.id] > 0:
                    drone.assign_target(target_planet, distance, target_type=TargetType.PLANET)
                    dic_nb_available_spot[target_planet.id] -= 1

                    # Check if by chance the drone can dock to its new target, to avoid loosing a turn
                    if drone.can_dock(drone.target):
                        # Store old target
                        target = drone.target
                        # Change role to miner
                        self.change_drone_role(drone, DroneRole.MINER)
                        # Ask for the drone to dock
                        drone.docking(target)

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
                distance, enemy_ship = drone.get_closest_ship()
                if enemy_ship is not None:
                    drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)

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
                logging.info("Go attack ship : %s" % drone.target.id)
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

        logging.info("Sent command to attack %s ship and navigate to %s planet" % (nb_target_ship, nb_target_planet))
        return command_queue
