import logging

from bot.drone import DroneRole, TargetType
from bot.navigation import Circle, calculate_distance_between
from bot.settings import config
from hlt.entity import Position

logger = logging.getLogger("squad")


class Squad(object):
    """
    Contains a group of drone that share the same target and movement
    - A squad as a squad leader, everything will be calculated by him, others will just follow
    """

    def __init__(self):
        self.__leader = None
        self.__members = []
        self.__is_alive = True
        self.__target = None
        self.role = DroneRole.UNKNOWN

    def check_squad_life(self):
        # Make sure that the leader is still alive
        if self.__leader is not None:
            if not self.__leader.is_alive():
                self.__leader = None
        # Now check if any members are dead
        new_members = []
        # Loop through all current members
        for member in self.__members:
            # IF there is still a drone
            if member is not None:
                # If the drone is alive
                if member.is_alive():
                    # Add it to the new member list
                    new_members.append(member)

        # Add the new list of member
        self.__members = new_members

        # If there are no leader
        if self.__leader is None:
            # Promote a new leader
            self.promote_new_leader()

        # Check the squad is alive
        if self.nb_members() == 0:
            # Flag the squad as dead
            self.__is_alive = False

    def is_leader_alive(self):
        if self.__leader is not None:
            if self.__leader.is_alive():
                return True
        return False

    def get_members(self):
        return self.__members

    def nb_members(self):
        """
        Return the number of members on this squad
        leader + members
        :return:
        """
        return len(self.__members)

    def gravitational_center(self):
        """
        Return the gravitational center of the squad
        :return:
        """
        center = Circle(0, 0, 0)
        for member in self.__members:
            center += member.ship.pos
        # Now divide by the number of members
        center = center / float(self.nb_members())
        logging.debug("gravitational_center: %s" % center)
        return center

    def squad_radius(self):
        """
        # get the radius into which all the squad's drones are
        :return:
        """
        min_x = 999
        max_x = 0
        min_y = 999
        max_y = 0
        for drone in self.__members:
            min_x = min(min_x, drone.ship.pos.x)
            max_x = max(max_x, drone.ship.pos.x)
            min_y = min(min_y, drone.ship.pos.y)
            max_y = max(max_y, drone.ship.pos.y)
        radius = max(max_x - min_x, max_y - min_y)
        return radius

    def get_leader(self):
        return self.__leader

    def assign_target(self, target, target_type=None):
        # Try to synchronise all drone to the target
        # Avoid calculating distance twice
        dic_distance = {}
        # Get the max distance from drones
        max_distance = 0
        for drone in self.__members:
            distance = calculate_distance_between(drone.ship.pos, target.pos)
            dic_distance[drone] =  distance
            if distance > max_distance:
                max_distance = distance

        for drone in self.__members:
            if max_distance > config.SLOW_TARGET_DISTANCE:
                drone.speed_ratio = dic_distance[drone] / max_distance
            drone.assign_target(target, target_type=target_type)

    def regroup(self):
        """
        # Order all drone to move to center
        :return:
        """
        center = self.gravitational_center()
        position = Position(center.x, center.y)
        position.pos.radius = self.nb_members() * config.SQUAD_SCATTERED_THRESHOLD / 2.0
        # Assign the position as target

        self.assign_target(position, target_type=TargetType.POSITION)

    def promote_new_leader(self):
        if self.__leader == None:
            # Get the gravitational_center
            center = self.gravitational_center()

            # Look for the member closest of the gravitational center
            min_distance = 999
            new_leader = None
            # Loop through all member
            for member in self.__members:
                distance = calculate_distance_between(member.ship.pos, center)
                if distance < min_distance:
                    min_distance = distance
                    new_leader = member

            # Promote the leader
            self.__leader = new_leader

    def add_member(self, drone):
        """
        Add a drone to the squad
        :param drone:
        :return:
        """
        self.__members.append(drone)
        drone.squad = self

    def remover_member(self, drone):
        """
        Remove a drone to the squad
        :param drone:
        :return:
        """
        self.__members.remove(drone)
        if self.__leader.ship.id == drone.ship.id:
            self.__leader = None
            self.promote_new_leader()

    def merge_squad(self, other_squad):
        for member in other_squad.get_members():
            self.add_member(member)