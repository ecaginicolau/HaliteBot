import logging

from bot.drone import DroneRole
from bot.navigation import Circle, calculate_distance_between

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
        self.__members=new_members

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

    def nb_members(self):
        """
        Return the number of members on this squad
        leader + members
        :return:
        """
        nb = 0
        if self.is_leader_alive():
            n = 1
        nb += len(self.__members)
        return nb

    def gravitational_center(self):
        """
        Return the gravitational center of the squad
        :return:
        """
        center = Circle(0,0,0)
        if self.is_leader_alive():
            center.x += self.__leader.ship.pos.x
            center.y += self.__leader.ship.pos.y
        for member in self.__members:
            center.x += member.ship.pos.x
            center.y += member.ship.pos.y
        # Now divide by the number of members
        center.x /= float(self.nb_members())
        center.y /= float(self.nb_members())
        return center

    def promote_new_leader(self):
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
        # Remove from the list of members
        self.__members.remove(new_leader)

    def add_member(self, drone):
        """
        Add a drone to the squad
        :param drone:
        :return:
        """
        self.__members.append(drone)