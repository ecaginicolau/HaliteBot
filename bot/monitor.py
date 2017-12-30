import logging

from bot.settings import SHIP_WEIGHT, PLANET_WEIGHT, PROXIMITY_WEIGHT
from bot.navigation import Circle, calculate_distance_between
from hlt.entity import Ship

logger = logging.getLogger("monitor")

"""
# Monitor's job:
    - Check for the strongest enemy
    - Find the most suitable target to attack
    - Find the most suitable target to conquer
"""


class Monitor(object):
    """
    The role of this class is to monitor everything in the game and give indication on where to attack / conquer
    """

    def __init__(self, player_id):
        # Store the player id, will be used to distinguish ships
        self.player_id = player_id
        # Store the game_map, must be updated everturn
        self.game_map = None
        # Store the current nemesis, must be reset every turn
        self.__nemesis = None

        # Store the threat level of each ship, dictionnay indexed by ship_id
        self.__threat_level = {}

        # Store the list of planet for each enemy, indexed by player_id
        self.__planets_by_player = {}
        # Store the list of empty_planet, for comparison purpose
        self.__empty_planets = {}
        # Store all planets indexed by planet_id
        self.__all_planets_dict = {}

        # Store the list of enemy ship indexed by player_id
        self.__ship_by_player = {}
        # Will store all ships in dictionary, should be updated every turn
        self.__all_ships_dict = {}

    def update_game(self, game_map):
        """
        [EVERY TURN]
        Update the game_map & other internal variable that will help monitor the current game
        :param game_map:
        :return:
        """
        # Update the game_map
        self.game_map = game_map

        # Reset turn's variable
        # Reset the nemesis
        self.__nemesis = None
        # Planets list & dictionary
        self.__planets_by_player = {}
        self.__empty_planets = {}
        self.__all_planets_dict = {}
        # Loop through all planet, look for empty & owned planets
        for planet in self.game_map.all_planets():
            self.__all_planets_dict[planet.id] = planet
            if not planet.is_owned():
                self.__empty_planets[planet.id] = planet
            else:
                try:
                    self.__planets_by_player[planet.owner.id].append(planet.id)
                except KeyError:
                    self.__planets_by_player[planet.owner.id] = [planet.id]

        # ship list & dictionary
        self.__ship_by_player = {}
        self.__all_ships_dict = {}
        for ship in self.game_map.all_ships():
            self.__all_ships_dict[ship.id] = ship
            try:
                self.__ship_by_player[ship.owner.id].append(ship.id)
            except KeyError:
                self.__ship_by_player[ship.owner.id] = [ship.id]

        # Clean threat level of ship that died
        for ship_id in list(self.__threat_level.keys()):
            try:
                # Check if the ship can be still found in the list of enemy ship
                self.__all_ships_dict[ship_id]
            except KeyError:
                # Remove the ship if it can't be found
                del self.__threat_level[ship_id]

    def get_all_planets_dict(self):
        return self.__all_planets_dict

    def get_all_ships_dict(self):
        return self.__all_ships_dict

    def get_enemy_ships(self, player_id=None):
        """
        return the list of all enemies or a single enemy
        :param player_id: if player_id is not None return only the ships of this player, otherwise return all ships
        :return: the list of ships
        """
        if player_id is not None:
            return self.__ship_by_player[player_id]
        else:
            total_list = []
            for enemy_id, list_ship in self.__ship_by_player.keys():
                # Don't get our ships
                if enemy_id == self.player_id:
                    total_list.extend(list_ship)
            return total_list

    def get_free_planets(self):
        """
        Return the list of free (empty or owned not full) planet
        :return: list of planet that are free
        """
        list_free_planet = []
        for planet_id, planet in self.__all_planets_dict.items():
            # Skip if full
            if planet.is_full():
                continue
            # Skip if not owned by us or empty
            if planet.is_owned() and planet.owner.id != self.player_id:
                continue
            # Otherwise add the the list of free planet
            list_free_planet.append(planet)
        return list_free_planet

    def get_planet(self, planet_id):
        """
        return a single planet
        :param planet_id:
        :return:
        """
        return self.__all_planets_dict[planet_id]

    def get_empty_planet(self, planet_id):
        """
        return a single planet
        raison a KeyError exception if the planet can't be found in the list of empty planets
        :param planet_id:  the id of the planet
        :return:
        """
        return self.__empty_planets[planet_id]

    def nb_owned_planets(self):
        """
        Return the number of planet owned by ourself
        :return:
        """
        return len(self.__planets_by_player[self.player_id])

    def nb_empty_planets(self):
        """
        Return the number of empty planets
        :return:
        """
        return len(self.__empty_planets)

    def get_team_ships(self):
        """
        Return the list of ships of our team
        :return:
        """
        return self.__ship_by_player[self.player_id]

    def get_ship(self, ship_id):
        """
        return a single ship
        Raise KeyError exception if the ship_id is not found
        :param ship_id:
        :return:
        """
        return self.__all_ships_dict[ship_id]

    def player_with_max_planet(self):
        """
        Helper function to find the player_id that has the max number of planets
        :return: return both the player_id and the number of planets
        """

        max_nb = 0
        max_player_id = None
        # Loop through all player to find which has the most planet
        for player_id, list_planets in self.__planets_by_player.items():
            nb = len(list_planets)
            if nb > max_nb:
                max_nb = nb
                max_player_id = player_id

        return max_player_id, max_nb

    def player_with_max_ship(self):
        """
        Helper function to find the player_id that has the max number of ships
        :return: return both the player_id and the number of ships
        """

        max_nb = 0
        max_player_id = None
        # Loop through all player to find which has the most planet
        for player_id, list_ships in self.__ship_by_player.items():
            nb = len(list_ships)
            if nb > max_nb:
                max_nb = nb
                max_player_id = player_id

        return max_player_id, max_nb

    def gravitational_center(self, player_id):
        """
        Calculate the center of gravity for a player_id
            - Sum all X coordinates of every ships
            - Sum all Y coordinates of every ships
            - Devide by the number of ships
        :param player_id:
        :return: x  & y of the gratitional center
        """

        # Get the list of ship
        list_ship = self.__ship_by_player[player_id]

        sum_x = 0
        sum_y = 0
        for ship_id in list_ship:
            ship = self.__all_ships_dict[ship_id]
            sum_x += ship.pos.x
            sum_y += ship.pos.y

        center_x = sum_x / len(list_ship)
        center_y = sum_y / len(list_ship)

        logger.debug("Calculated the gravitational center of player_id %s: %s,%s" % (player_id, center_x, center_y))

        return Circle(center_x, center_y)

    def find_nemesis(self):
        """
        Calculate which player should be targeted next, based on number of ship, number of planets ...
        # Return the current nemesis if already calculated for this turn
        - if self.nemesis != None
        # Otherwise calculate it again
        - Depends on hyper parameters, SHIP_WEIGHT, PLANET_WEIGHT, PROXIMITY_WEIGHT
        - Could count which player has been too close of our frontier
        - The distance between the average of our planets
        - Many other criteria

        The nemesis can change over time, maybe in the same turn (avoid launching all ships to the same enemy?)

        :return: the player_id of our nemesis
        """

        # If we have already calculated the nemesis this turn
        if self.__nemesis is not None:
            return self.__nemesis

        # If there is only one enemy, no need to calculate anything
        if len(self.__ship_by_player) == 1:
            self.__nemesis = list(self.__ship_by_player.keys())[0]
            return self.__nemesis

        """
        # Score calculation
            - score increase with the number of ship, so SHIP_WEIGHT > 0
            - score increase with the number of planets, so PLANET_WEIGHT > 0
            - score decrese as the distance increase, so PROXIMITY_WEIGHT < 0

        # score = SHIP_WEIGHT * nb_ship  + PLANET_WEIGHT *  nb_planet + PROXIMITY_WEIGHT * distance
        # Bigger score =  bigger threat
        # Biggest score = nemesis
        """
        # Start with getting our own gravitational center
        team_g_center = self.gravitational_center(self.player_id)

        # Store the score for each enemy
        enemy_score = {}

        # Loop through all enemies
        for enemy_id in self.__planets_by_player.keys():
            # This is not an enemy, it's ourself
            if enemy_id == self.player_id:
                # Skip to next player
                continue
            # Calculate the gravitational_center
            enemy_g_center = self.gravitational_center(enemy_id)
            # Calculate the distance
            distance = calculate_distance_between(team_g_center, enemy_g_center)
            # Get the number of ships
            try:
                nb_ship = len(self.__ship_by_player[enemy_id])
            except KeyError:
                nb_ship = 0
            # Get the number of planets
            try:
                nb_planet = len(self.__planets_by_player[enemy_id])
            except KeyError:
                nb_planet = 0
            # Calculate the score
            score = SHIP_WEIGHT * nb_ship + PLANET_WEIGHT * nb_planet + PROXIMITY_WEIGHT * distance
            enemy_score[enemy_id] = score
            logger.info("Score of the player_id %s is %s" % (enemy_id, score))

        # Find the nemesis : the enemy with the biggest score
        max_score = -9999
        nemesis = None
        for enemy_id, score in enemy_score.items():
            if score > max_score:
                max_score = score
                nemesis = enemy_id

        self.__nemesis = nemesis
        return self.__nemesis

    def ship_threat_level(self):
        """
        Give a threat level for every enemy ship
        :return:
        """
        # Store the old threat level for delta calculation
        # old_threat_level = self.__threat_level

        # loop through all enemy ship
        for enemy_id, list_ship in self.__ship_by_player.items():
            for ship in list_ship:
                # Easy : docked = no threat
                if ship.docking_status != Ship.DockingStatus.UNDOCKED:
                    self.__threat_level[ship.id] = 0
                    # Skip to next ship
                    continue
