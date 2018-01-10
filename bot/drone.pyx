import hlt
import logging
from enum import Enum

from bot.influence import Influence
from bot.monitor import Monitor
from bot.navigation import calculate_distance_between
from bot.settings import MAX_TURN_DEFENDER, THREAT_WEIGHT, DISTANCE_WEIGHT, SCORE_NB_DOCKING_SPOTS, SCORE_NB_SHIP_ONGOING, SCORE_DISTANCE_CENTER
from hlt import constants
from hlt.entity import Ship

logger = logging.getLogger("drone")


class DroneRole(Enum):
    """
    # List of possible role a Drone can have
    """

    # Unknown, while it's the default role it should not happen
    UNKNOWN = "unknown"
    # IDlE, the drone has no current order, it needs to take one
    IDLE = "idle"
    # The drone role is to attack the enemy, as much as possible
    ATTACKER = "attacker"
    # The drone role is to take new planets
    CONQUEROR = "conqueror"
    # The drone role is to mine for faster ships creations
    MINER = "miner"
    # The drone role is to attack the enemy for a short duration
    DEFENDER = "defender"
    # The drone role is to attack the enemy's miners
    ASSASSIN = "assassin"


class TargetType(Enum):
    """
    # The list of target type for the current drone action
    """

    # It can be targetting a planet (for conquest?)
    PLANET = "planet"
    # It can be targetting a ship (attack or defense)
    SHIP = "ship"
    # It can be currently docking (so no need of target?)
    DOCKING = "docking"
    # It can be currently undock (so no need of target?)
    UNDOCKING = "undocking"
    # It can be currently undock (so no need of target?)
    POSITION = "position"


class Drone(object):
    """
    Drones are extension of ship that are in my control
    """

    def __init__(self, ship, role=DroneRole.IDLE):
        # Drone's ship, need to be updated each round
        self.ship = ship
        # Drone's ship's id
        self.ship_id = ship.id
        # Current drone role
        self.__role = role
        # Previous drone role, useful if switched to defender
        self.__previous_role = DroneRole.IDLE
        # Current max health for this ship, usefull to check if the ship is attacked
        self.max_health = ship.health
        # How many turns are left for this ship as a defender
        self.defender_timer = MAX_TURN_DEFENDER
        # Store the id of the target, stay the same between rounds
        self.target_id = None
        # Store the target itself, needs to be updated each rounds
        self.target = None
        # Store the type of target
        self.target_type = None
        # Store the distance between the drone and its target
        self.target_distance = None
        # Store all enemy ships by distance
        self.__enemy_by_distance = []
        # Store all planet by distance
        self.__planet_by_distance = []
        # Store the distance of all enemy ships, indexed by ship.id
        self.__enemy_distance = {}
        # Store the distance of all planets, indexed by planet.id
        self.__planet_distance = {}
        # Store the possible threats as a list
        self.__possibles_threats = []
        # Flag if the drone is alive
        self.__is_alive = True
        # Flag if the drone has been damaged this X turn
        self.is_damaged = False

    def update_ship(self, ship):
        """
        Update the ship info, needs to be done each round
        :param ship:
        :return:
        """
        self.ship = ship
        # Reset the list of possible_threats for this drone
        self.__possibles_threats = []

    def is_alive(self):
        return self.__is_alive

    def add_possible_threat(self, distance, threat):
        self.__possibles_threats.append((distance, threat))

    def reset_target(self):
        """
        Reset the target
        :return:
        """
        self.target_id = None
        self.target = None
        self.target_type = None
        self.target_distance = None

    def docking(self, planet):
        """
        Docking a target_type that need no target
        :return:
        """
        self.reset_target()
        self.target = planet
        self.target_type = TargetType.DOCKING

    def undocking(self):
        """
        Undocking a target_type that need no target
        :return:
        """
        self.reset_target()
        self.target_type = TargetType.UNDOCKING

    def can_dock(self, planet):
        """
        Complete lookup if the shup can dock
            - planet empty or owned
            - planet not full
            - planet at correct distance
        :param planet:
        :return: bool, true if can dock
        """
        # Make sure the planet is free
        if planet.owner is not None and planet.owner != self.ship.owner:
            return False
        # Make sure the planet is not full
        if planet.is_full():
            return False
        # Make sure we are not too far
        if self.__planet_distance[planet.id] > planet.pos.radius + constants.DOCK_RADIUS + constants.SHIP_RADIUS:
            return False

        # If we've arrived up to here, it means we can dock
        return True

    def update_target(self, target):
        if target is None:
            self.reset_target()
            return
        self.target = target
        self.target_distance = calculate_distance_between(self.ship.pos, target.pos)

    def assign_target(self, target, distance=None, target_type=None):
        """
        Assign a new target to to the drone
        :param target: can be a ship or a planet
        :param distance: automatically calculated if None
        :param target_type: automatically calculated if None
        :return:
        """

        # If the new target is None, reset the target and exit
        if target is None:
            self.reset_target()
            return

        # If the distance parameter is None, calculate it here (save some computation time)
        if distance is None:
            distance = calculate_distance_between(self.ship.pos, target.pos)

        # Store the distance between the drone and its target
        self.target_distance = distance
        # Update the target_id, will be kept turn by turn
        self.target_id = target.id
        # Store the target itself, will need to be updated everyturn
        self.target = target
        # store the type of target, can be a ship or a planet
        if target_type is None:
            # If we didn't send the target type, look for it
            if isinstance(target, hlt.entity.Ship):
                self.target_type = TargetType.SHIP
            else:
                self.target_type = TargetType.PLANET
        else:
            # Otherwise just store it
            self.target_type = target_type
        logger.debug("Ship %s has a new target: %s of type %s" % (self.ship_id, target.id, self.target_type))

    def get_previous_role(self):
        """
        Previous role property (getter)
        :return: the previous role
        """
        return self.__previous_role

    def get_role(self):
        """
        Role property (getter)
        :return: the role
        """
        return self.__role

    def set_role(self, role):
        """
        Role property (setter)
            - Reset the target if the role has changed
            - Reset defender_timer if the new role is DEFENDER
            - Reset max_health if the old role was DEFENDER
        :param role:
        :return:
        """

        # If the role didn't change, exit
        if role == self.role:
            return

        # The role changed!
        # reset the target
        self.reset_target()
        # If the new role is defender
        if role == DroneRole.DEFENDER:
            # reset the defender timer
            self.defender_timer = MAX_TURN_DEFENDER
        # If the old role was DEFENDER
        if self.role == DroneRole.DEFENDER:
            # reset the max health so it can enter in defense mode again
            self.max_health = self.ship.health

        # Store the previous role
        self.__previous_role = self.role
        # In the end, update the role
        self.__role = role

    # Create the properties
    role = property(get_role, set_role)

    def get_furthest_ship(self, player_id=None, docked_only=False):
        """
        Return the closest ship, if a player_id is sent then return the closest ship of this player
        :param player_id: the player 's ship we are looking for, None for all ships
        :param docked_only: Only look for docked ships
        :return: a single ship
        """
        for distance, enemy_ship in reversed(self.__enemy_by_distance):
            # If we are looking for docked only ships
            if docked_only:
                # If the enemy ship is currently undocked, skip to next ship
                if enemy_ship.docking_status == Ship.DockingStatus.UNDOCKED:
                    # Skip to next ship
                    continue
            # If we are looking for a specific enemy's ships
            if player_id is not None:
                # Check if the ship's owner match the enemy we are looking after
                if player_id != enemy_ship.owner.id:
                    # SKip to next ship if the owners doesn't match
                    continue
            # If we've made up to here it means we have found the correct ship!
            return distance, enemy_ship
        # There are no ships matching this filter
        return None, None

    def get_closest_ship(self, player_id=None, docked_only=False):
        """
        Return the closest ship, if a player_id is sent then return the closest ship of this player
        :param player_id: the player 's ship we are looking for, None for all ships
        :param docked_only: Only look for docked ships
        :return: a single ship
        """
        for distance, enemy_ship in self.__enemy_by_distance:
            # If we are looking for docked only ships
            if docked_only:
                # If the enemy ship is currently undocked, skip to next ship
                if enemy_ship.docking_status == Ship.DockingStatus.UNDOCKED:
                    # Skip to next ship
                    continue
            # If we are looking for a specific enemy's ships
            if player_id is not None:
                # Check if the ship's owner match the enemy we are looking after
                if player_id != enemy_ship.owner.id:
                    # SKip to next ship if the owners doesn't match
                    continue
            # If we've made up to here it means we have found the correct ship!
            return distance, enemy_ship
        # There are no ships matching this filter
        return None, None

    def get_closest_ship_in_influence(self):
        """
        Return the closest ship, inside the player influence
        :return: a single ship
        """
        for distance, enemy_ship in self.__enemy_by_distance:
            # Check if the ship is in the influence zone
            if Influence.is_in_influence_zone(enemy_ship.pos):
                # If we've made up to here it means we have found the correct ship!
                return distance, enemy_ship
        # There are no ships matching this filter
        return None, None

    def get_dangerous_ship(self):
        """
        Return the most dangerous ship, calculated by distance & threat level
        :return: a single ship
        """
        target_score = 9999
        target_distance = 0
        target = None
        for distance, enemy_ship in self.__enemy_by_distance:
            # Simple calculate between the distance & the threat level
            score = distance * DISTANCE_WEIGHT + Monitor.get_threat_level(enemy_ship.id) * THREAT_WEIGHT
            if score < target_score:
                target_score = score
                target_distance = distance
                target = enemy_ship
        # There are no ships matching this filter
        return target_distance, target_score, target

    def calculate_all_ships_distance(self, all_ships):
        """
        Calculate all distance once and for all between all ships
        Will probaly have collision issue with distance if 2 target are at the same distance of this ship
        :param all_ships:
        :return:
        """
        self.__enemy_by_distance = []
        self.__enemy_distance = {}
        for _, ship in all_ships.items():
            # Don't calculate distance with ship of our team
            if ship.owner == self.ship.owner:
                # Ship to next ship
                continue
            # Calculate the distance between the drone and this ship
            distance = calculate_distance_between(self.ship.pos, ship.pos)
            # Store the enemy's distance for faster lookup
            self.__enemy_distance[ship.id] = distance
            # Append to the list of all distance
            self.__enemy_by_distance.append((distance, ship))

        # Sort by distance
        self.__enemy_by_distance = sorted(self.__enemy_by_distance, key=lambda l: l[0])

    def get_closest_empty_planet(self):
        """
        Get the closest empty planet
        :return: distance, planet
        """
        for distance, planet in self.__planet_by_distance:
            # Check if it's an empty planet
            if not planet.is_owned():
                return distance, planet
        # There are no empty planet left
        return None, None

    def get_closest_owned(self):
        """
        Return our closest planet
        :return: distance, planet
        """
        for distance, planet in self.__planet_by_distance:
            # Check if it's our planet
            if planet.owner == self.ship.owner:
                return distance, planet
        # We don't have an owned planet yet
        return None, None

    def calculate_all_planets_distance(self, all_planets):
        self.__planet_by_distance = []
        self.__planet_distance = {}
        for planet_id, planet in all_planets.items():
            # Calculate the distance between the drone and this ship
            distance = calculate_distance_between(self.ship.pos, planet.pos)
            # Store the distance for faster lookup
            self.__planet_distance[planet.id] = distance
            # Append to the list of all distance
            self.__planet_by_distance.append((distance, planet))

        # Sort by distance
        self.__planet_by_distance = sorted(self.__planet_by_distance, key=lambda l: l[0])

    def get_empty_planet_by_distance(self):
        list_distance = []
        for distance, planet in self.__planet_by_distance:
            if not planet.is_owned():
                list_distance.append((distance, planet))
        return list_distance

    def get_planet_by_distance(self):
        return self.__enemy_by_distance

    def get_free_planet_by_distance(self):
        """
        return the list of planet (empty or owned) and not full by distance
        :return: list of free planet by distance
        """
        list_distance = []
        for distance, planet in self.__planet_by_distance:
            # Make sure the planet is free
            if planet.is_free(self.ship.owner):
                list_distance.append((distance, planet))
        return list_distance

    def get_best_planet_by_score(self):
        try:
            return self.get_free_planet_by_score()[0]
        except IndexError:
            None, None

    def get_free_planet_by_score(self):
        """
        return the list of planet (empty or owned) and not full by distance
        :return: list of free planet by distance
        """
        list_score = []
        for distance, planet in self.__planet_by_distance:
            # Make sure the planet is free
            if planet.is_free(self.ship.owner):
                # Don't look for planet with no available spot anymore
                if Monitor.get_nb_spots_for_miners(planet.id) == 0:
                    continue
                # Score is relative to the distance
                score = distance
                """
                # The score decrease with he number of availbale docking spots in the planet
                score /= planet.nb_available_docking_spots() * SCORE_NB_DOCKING_SPOTS
                # the Score decrease with the number of ship already going to the planet
                score /= (planet.nb_available_docking_spots() - dic_nb_available_spot[planet.id] + 1) * SCORE_NB_SHIP_ONGOING
                """
                """
                # the score decrease with the distance of the planet to the center
                score -= calculate_distance_between(planet.pos, Monitor.get_map_center()) * SCORE_DISTANCE_CENTER
                """
                list_score.append((score, planet))
        list_score = sorted(list_score, key=lambda l: l[0])
        return list_score

    def get_closest_free_planet(self):
        """
        get the closest planet that is free (empty or owner by me)
        :return:
        """
        for distance, planet in self.__planet_by_distance:
            if not planet.is_owned() or planet.owner == self.ship.owner:
                return distance, planet
        return None, None
