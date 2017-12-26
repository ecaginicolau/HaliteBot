import hlt
import logging
from enum import Enum

logger = logging.getLogger("drone")

# Nb of turn the ship is set to defender mode
MAX_TURN_DEFENDER = 5


class DroneRole(Enum):
    """
    # List of possible role a Drone can have
    """

    # Unknow, while it's the default role it should not happen
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

    def update_ship(self, ship):
        """
        Update the ship info, needs to be done each round
        :param ship:
        :return:
        """
        self.ship = ship

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
            distance = self.ship.calculate_distance_between(target)

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
