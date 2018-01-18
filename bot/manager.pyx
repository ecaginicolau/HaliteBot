# Python imports
import logging
from datetime import datetime
# Bot imports

from bot.monitor import Monitor
from bot.drone import DroneRole, TargetType, Drone
from bot.navigation import calculate_distance_between, calculate_length
from bot.influence import Influence
from bot.settings import  NB_SHIP_THRESHOLD, MAX_TURN_DURATION, MINER_CAN_DEFEND, MIN_SCORE_DEFENSE, FOLLOW_DISTANCE, EARLY_RATIO_ASSASSIN, EARLY_RATIO_ATTACKER, \
    EARLY_RATIO_DEFENDER, LATE_RATIO_DEFENDER, LATE_RATIO_ATTACKER, LATE_RATIO_ASSASSIN, config
# hlt imports
from bot.squad import Squad
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
        # Check for squad life
        Manager.check_squads()
        # Check/Update drone's targets
        Manager.check_drone_target()
        # Check for newly created ship, convert them to drone
        Manager.check_for_new_ship()
        # Check miners
        Monitor.check_planets_miners()
        # Update influence of the game map
        Influence.update_game_map(game_map)
        # Calculate the number of ship in the influence zone everyturn
        Monitor.nb_ship_in_influence()
        # add the center of the map as a ghost, to avoid it
        if config.CENTER_GHOST:
            Manager.add_ghost_center()

    @staticmethod
    def add_ghost_center():
        center = Monitor.get_map_center()
        center.radius = 10
        Manager.game_map.add_ghost((center, center))

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
    def check_squads():
        squad_done = {}
        for ship_id in list(Manager.__all_drones.keys()):
            drone = Manager.__all_drones[ship_id]
            # If the drone is not in a squad, skip it
            if drone.squad is None:
                # Skip to next drone
                continue
            # If the squad has already be done, skip it
            try:
                _ = squad_done[drone.squad]
                # We found it, skip the drone
                continue
            except KeyError:
                # Add it to the dictionnary to avoid doing it twice
                squad_done[drone.squad] = 1
            # We need to check the squad
            drone.squad.check_squad_life()



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
    def go_all_in():
        # Get the list of enemy ship
        enemy_player_id = 0 if Manager.player_id == 1 else 1
        min_distance = 999
        dic_closest_planet = {}
        for ship in Manager.game_map.get_player(enemy_player_id).all_ships():
            logging.debug("enemy ship id: %s" % ship.id)
            # Find the closest planet of this ship
            min_distance = 999
            for planet_id in Monitor.get_empty_planets():
                planet = Monitor.get_planet(planet_id)
                distance = calculate_distance_between(ship.pos, planet.pos)
                if distance < min_distance:
                    min_distance = distance
                    dic_closest_planet[ship.id] = planet

        # 1st make sure it's the same planet for all 3 ships
        set_planet = set(dic_closest_planet.values())
        if len(set_planet) != 1:
            return False
        # Get the only planet
        planet = set_planet.pop()
        # If the distance between the planet and our gravitational center is less than INITIAL_SAFE_DISTANCE => all in !
        if calculate_distance_between(planet.pos, Monitor.gravitational_center(Manager.player_id)) < config.INITIAL_SAFE_DISTANCE:
            return True

        # No all in
        return False


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
        # Special case, if 2 players and turn 0
        """
        if Manager.game_map.turn == 0 and len(Manager.game_map.all_players()) == 2:
            logging.debug("Initial turn with only 2 players")
            if Manager.go_all_in():
                logging.debug("The 2 players are too close, sending all in attack")
                for drone_id in list(Manager.__all_role_drones[DroneRole.IDLE]):
                    drone = Manager.get_drone(drone_id)
                    Manager.change_drone_role(drone, DroneRole.ATTACKER)
                return None

        """
        # 1st: There are still planets to conquer
        """
        if Monitor.map_has_available_spots():
            # While there are still some idle drone, and we have less attackers than ships attacking us
            while Manager.nb_drone_role(DroneRole.IDLE) > 0 and Manager.nb_offense() < Monitor.nb_ship_in_influence_last_x(config.NB_TURN_INFLUENCE) * config.NB_IN_INFLUENCE_RATIO:
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
            # Reset speed ratioto the target
            drone.speed_ratio = None
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
    def __navigate_target(drone, target, assassin=False, closest=True):
        """
        Simple method to create a command to attack the closest ship
        :param drone:
        :return: the navigate command
        """
        # logging.debug("Going to generate a navigate command between ship %s and target %s" % (ship.id, target.id))
        # modify speed if speed_ratio is not None
        speed = int(MAX_SPEED)

        if config.SLOW_TO_TARGET:
            if drone.speed_ratio is not None and drone.target_type == TargetType.SHIP:
                speed = speed * (1 - config.SLOW_SPEED_RATIO) + speed * config.SLOW_SPEED_RATIO * drone.speed_ratio
                speed = int(round(speed))
                logging.debug("Slowing drone to speed: %s" % speed)
        navigate_command = None
        if target is not None:
            navigate_command = drone.ship.navigate(
                target,
                Manager.game_map,
                speed=speed,
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
    def __intercept_ship(drone, target, distance):
        new_target = target.pos + (target.velocity * (FOLLOW_DISTANCE / MAX_SPEED))
        new_target = Position(new_target.x, new_target.y)
        drone.assign_target(target = new_target, target_type=TargetType.POSITION)
        return Manager.__navigate_target(drone, new_target, closest=False)

    @staticmethod
    def __suicide_ship_command(drone, target, assassin=False):
        """
        Simple method to create a command to collide to a target
        :param drone:
        :return: the navigate command
        """
        return Manager.__navigate_target(drone, target, assassin=assassin, closest=False)

    @staticmethod
    def __attack_ship_command(drone, target, assassin=False):
        """
        Simple method to create a command to attack a target ship
        :param drone:
        :return: the navigate command
        """
        if config.INTERCEPT:
            if drone.target_type == TargetType.SHIP:
                if drone.target_distance > FOLLOW_DISTANCE:
                    return Manager.__intercept_ship(drone, target, drone.target_distance)
        return Manager.__navigate_target(drone, target, assassin=assassin)

    @staticmethod
    def __conquer_ship_command(drone, target):
        """
        Simple method to create a command to conquer a target planet
        :param drone:
        :return: the navigate command
        """
        return Manager.__navigate_target(drone, target)

    @staticmethod
    def check_drone_surrounding(drone):
        # Check if enemies are in the radius of defense
        # Get the distance of the closest enemy ship
        distance, ship = drone.get_closest_ship()
        if distance <= config.DEFENDER_RADIUS:
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
        if distance <= config.DEFENDER_RADIUS:
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

        # Loop through all drone
        for ship_id in Manager.__all_role_drones[DroneRole.ASSASSIN]:
            # Get the drone
            drone = Manager.__all_drones[ship_id]
            if drone.target is None:
                # Look for the furthest ship that is docked
                distance, enemy_ship = drone.get_furthest_ship(docked_only=True)
                #If we've found a docked ship
                if enemy_ship is not None:
                    drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)
                # If there are no docked ship
                else:
                    # Look for the furthest ship
                    distance, enemy_ship = drone.get_furthest_ship()
                    drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)

    @staticmethod
    def get_nb_enemy_behind(drone, enemy_ship, distance):
        # Locate the center of the enemy squad we will look
        # 1: get the direction between the leader and its starget
        direction = enemy_ship.pos - drone.ship.pos
        # 2: normalize
        direction /= calculate_length(direction)
        # 3: set the direction size to ENEMY_SQUAD_RADIUS / 2.0
        direction *= config.ENEMY_SQUAD_RADIUS / 2.0
        # 4: get the center point
        center =  enemy_ship.pos + direction
        # Look for the number of ship in the neighborhood
        nb = 0
        for other_distance, other_ship in drone.get_enemy_by_distance():
            # Don't need to calculate the distance with the default enemy ship
            if other_ship == enemy_ship:
                nb += 1
                continue
            # Don't count docked ship
            if other_ship.docking_status != Ship.DockingStatus.UNDOCKED:
                continue
            # Don't look for ship that are too far away
            if other_distance > distance + config.ENEMY_SQUAD_RADIUS * 2.0:
                break
            if calculate_distance_between(center, other_ship.pos) <= config.ENEMY_SQUAD_RADIUS:
                nb += 1
        logging.debug("[SQUAD] There are %s enemies in the enemy squad" % nb)
        return nb

    @staticmethod
    def merge_squad():
        squad_done = {}
        squad_done = {}
        for ship_id in list(Manager.__all_role_drones[DroneRole.ATTACKER]):
            drone = Manager.__all_drones[ship_id]

            # If the drone has no squad, skip
            if drone.squad is None:
                # Skip to next drone
                continue

            # Only check leaders
            if drone.squad.get_leader !=  drone:
                continue

            # Make sure we haven't given order to this squad yet
            try:
                _ = squad_done[drone.squad]
                # They key is present, so skip to next drone
                continue
            except KeyError:
                # Insert this squad as "done"
                squad_done[drone.squad] = 1
                pass

            for other_ship_id in Manager.__all_role_drones[DroneRole.ATTACKER]:
                other_drone = Manager.__all_drones[ship_id]
                # Don't check itself
                if drone == other_drone:
                    continue
                # If the other_drone has no squad, skip
                if other_drone.squad is None:
                    # Skip to next drone
                    continue
                # Only check leaders
                if other_drone.squad.get_leader !=  other_drone:
                    continue

                if calculate_distance_between(other_drone.ship.pos, drone.ship.pos) < config.SQUAD_DISTANCE_CREATION:
                    drone.squad.merge_squad(other_drone.squad)


    @staticmethod
    def order_squad():
        squad_done = {}
        for ship_id in list(Manager.__all_role_drones[DroneRole.ATTACKER]):
            drone = Manager.__all_drones[ship_id]

            # If the drone has no squad, skip
            if drone.squad is None:
                # Skip to next drone
                continue

            # Make sure we haven't given order to this squad yet
            try:
                _ = squad_done[drone.squad]
                # They key is present, so skip to next drone
                continue
            except KeyError:
                # Insert this squad as "done"
                squad_done[drone.squad] = 1
                pass

            # If the squad is too scattered, regroup it
            if drone.squad.squad_radius() > drone.squad.nb_members() * config.SQUAD_SCATTERED_THRESHOLD * 2.0:
                logging.debug("Squad is scattered, need to regroup")
                drone.squad.regroup()
            else:
                # The squad is not too scattered, we can attack
                logging.debug("Squad is close, they can attack")
                # Get the leader
                leader = drone.squad.get_leader()
                # Look for the closest ship
                distance, enemy_ship = leader.get_closest_ship()
                # Check if there is an enemy around the ship
                if distance <= config.CONTACT_ZONE_RADIUS:
                    if config.SQUAD_RUN_AWAY:
                        nb = Manager.get_nb_enemy_behind(leader, enemy_ship, distance)
                        # If there are too many enemies, run away!
                        if nb > drone.squad.nb_members() * config.SQUAD_BRAVERY:
                            if config.SQUAD_REGROUP:
                                logging.debug("[SQUAD] squad leader %s is running away from closest ship %s => regroup" % (leader.ship.id, enemy_ship.id))
                                drone.squad.regroup()
                            else:
                                logging.debug("[SQUAD] squad leader %s is running away from closest ship %s" % (leader.ship.id, enemy_ship.id))
                                direction =  (enemy_ship.pos - leader.ship.pos) * -1
                                dir_len = calculate_length(direction)
                                if dir_len < MAX_SPEED:
                                    direction = (direction / dir_len) * MAX_SPEED
                                target_pos = leader.ship.pos + direction
                                position = Position(target_pos.x, target_pos.y)
                                drone.squad.assign_target(position, target_type=TargetType.POSITION)
                        else:
                            # Attack this ship
                            logging.debug("[SQUAD] squad leader %s attacking closest ship (SAFE_ZONE_RADIUS) %s" % (leader.ship.id, enemy_ship.id))
                            drone.squad.assign_target(enemy_ship, target_type=TargetType.SHIP)
                    else:
                        # Attack this ship
                        logging.debug("[SQUAD] squad leader %s attacking closest ship (SAFE_ZONE_RADIUS) %s" % (leader.ship.id, enemy_ship.id))
                        drone.squad.assign_target(enemy_ship, target_type=TargetType.SHIP)
                else:
                    # If there are no enemy close look for an enemy inside the influence zone
                    influence_distance, influence_enemy_ship = leader.get_closest_ship_in_influence()
                    if influence_enemy_ship is not None:
                        # Assign the new target, if any available
                        logging.debug("[SQUAD] squad leader %s attacking influence ship %s" % (leader.ship.id, influence_enemy_ship.id))
                        drone.squad.assign_target(influence_enemy_ship, target_type=TargetType.SHIP)
                    else:
                        # Attack the closest ship
                        logging.debug("[SQUAD] squad leader %s attacking closest ship (default) %s" % (leader.ship.id, enemy_ship.id))
                        drone.squad.assign_target(enemy_ship, target_type=TargetType.SHIP)





    @staticmethod
    def order_attacker():
        # Loop through all drone
        for ship_id in list(Manager.__all_role_drones[DroneRole.ATTACKER]):
            # Get the drone
            drone = Manager.__all_drones[ship_id]

            if config.CREATE_SQUAD:
                # Try to create squad
                if drone.squad is None:
                    logging.debug("Drone: %s has no squad" % drone.ship.id)
                    squad_created = False
                    # Find the number of attacker drone inside the radius, join or create squad if it's the case
                    for other_ship_id in  list(Manager.__all_role_drones[DroneRole.ATTACKER]):
                        # Don't look at itself
                        if other_ship_id == ship_id:
                            # Skip next ship
                            continue
                        other_drone = Manager.__all_drones[other_ship_id]
                        if calculate_distance_between(drone.ship.pos, other_drone.ship.pos) < config.SQUAD_DISTANCE_CREATION:
                            # We have a squad here!
                            squad_created = True
                            logging.debug("Found close attacker to join in squad")
                            if other_drone.squad is not None and other_drone.squad.nb_members() < config.SQUAD_SIZE:
                                logging.debug("Squad exist and not full, joining it")
                                other_drone.squad.add_member(drone)
                            else:
                                logging.debug("Squad doesn't exist or is full, create it")
                                new_squad = Squad()
                                new_squad.add_member(drone)
                                new_squad.add_member(other_drone)
                                new_squad.promote_new_leader()
                            # Don't look for other drone
                            break
                else:
                    # logging.debug("Drone: %s has already a squad" % drone.ship.id)
                    # Skip to next drone
                    continue

            # Only handle squad less drone
            if drone.squad is None:
                # Look for the closest ship
                distance, enemy_ship = drone.get_closest_ship()
                # Check if there is an enemy around the ship
                if distance <= config.CONTACT_ZONE_RADIUS:
                    if config.SQUAD_RUN_AWAY:
                        nb = Manager.get_nb_enemy_behind(drone, enemy_ship, distance)
                        logging.debug("There are %s enemies in the enemy squad" % nb)

                        # If there are too many enemies, run away!
                        if nb > 1:
                            logging.debug("drone %s is running away from closest ship %s" % (drone.ship.id, enemy_ship.id))
                            direction =  (enemy_ship.pos - drone.ship.pos) * -1
                            dir_len = calculate_length(direction)
                            if dir_len < MAX_SPEED:
                                direction = (direction / dir_len) * MAX_SPEED
                            target_pos = drone.ship.pos + direction
                            position = Position(target_pos.x, target_pos.y)
                            drone.assign_target(position, target_type=TargetType.POSITION)
                        else:
                            # Attack this ship
                            logging.debug("drone %s attacking closest ship (SAFE_ZONE_RADIUS) %s" % (drone.ship.id, enemy_ship.id))
                            # Attack this ship
                            drone.assign_target(enemy_ship, distance, target_type=TargetType.SHIP)
                    else:
                        # Attack this ship
                        logging.debug("drone %s attacking closest ship (SAFE_ZONE_RADIUS) %s" % (drone.ship.id, enemy_ship.id))
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
    def order_attacker_no_squad():
        """
        [EVERY TURN]
        Main IA function for all drone with ATTACKER role
            - Loop through all Attacker
            - Don't change drone with valid target
            - Look for a target for drone without one: closest enemy ship
            - At the end every attacker should have a target
        :return:
        """


        # Loop through all drone
        for ship_id in list(Manager.__all_role_drones[DroneRole.ATTACKER]):
            # Get the drone
            drone = Manager.__all_drones[ship_id]
            # If the drone has currently no target, look for one
            distance, enemy_ship = drone.get_closest_ship()
            # Check if there is an enemy around the ship
            if distance <= config.SAFE_ZONE_RADIUS:
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
                # Get the closest ship
                distance, enemy_ship  = drone.get_closest_ship()
                # If the enemy ship is too close, attack
                if distance < config.SAFE_ZONE_RADIUS:
                    Manager.change_drone_role(drone, DroneRole.ATTACKER)
                    # Skip to next drone
                    continue

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
                        # logging.debug("[COMMAND] Ship: %s go suicide ship: %s" % (drone.ship.id, drone.target.id))
                        command = Manager.__suicide_ship_command(drone, drone.target, assassin=True)
                    else:
                        # logging.debug("[COMMAND] Ship: %s go assassin ship: %s" % (drone.ship.id, drone.target.id))
                        command = Manager.__attack_ship_command(drone, drone.target, assassin=True)
                    if command:
                        command_queue.append(command)
                elif drone.role == DroneRole.DEFENDER:
                    if drone.target_type == TargetType.SHIP:
                        # logging.debug("[COMMAND] Ship: %s go intercept ship: %s" % (drone.ship.id, drone.target.id))
                        command = Manager.__intercept_ship(drone, drone.target, distance)
                    else:
                        # logging.debug("[COMMAND] Ship: %s go defense position: %s" % (drone.ship.id, drone.target.pos))
                        command = Manager.__navigate_target(drone, drone.target, closest = False)
                    if command:
                        command_queue.append(command)
                else:
                    # logging.debug("[COMMAND] Ship: %s attack ship: %s" % (drone.ship.id, drone.target.id))
                    command = Manager.__attack_ship_command(drone, drone.target)
                    if command:
                        command_queue.append(command)

            # If the target is a planet
            elif drone.target_type == TargetType.PLANET:
                nb_target_planet += 1
                command = Manager.__conquer_ship_command(drone, drone.target)
                if command:
                    command_queue.append(command)
            elif drone.target_type == TargetType.POSITION:
                # logging.debug("[COMMAND] Ship: %s navigate position: %s" % (drone.ship.id, drone.target.pos))
                command = Manager.__navigate_target(drone, drone.target, closest=False)
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
