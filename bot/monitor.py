import logging

from navigation import Circle, calculate_distance_between

from .hyperparameters import SHIP_WEIGHT, PLANET_WEIGHT, PROXIMITY_WEIGHT

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
        # Store the list of planet for each enemy, indexed by player_id
        self.__enemy_planets = {}
        # Store the list planet for the current player, for comparison purpose
        self.__team_planets = []
        # Store the list of empty_planet, for comparison purpose
        self.__empty_planets = []
        # Store the list of enemy ship indexed by player_id
        self.__enemy_ship = {}
        # Store the list of current player's ship, for comparison purpose
        self.__team_ship = []
        # Store the current nemesis, must be reset every turn
        self.__nemesis = None

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
        self.__enemy_planets = {}
        self.__team_planets = []
        self.__empty_planets = []
        # Loop through all planet, look for empty, enemy or team planets
        for planet in self.game_map.all_planets():
            if not planet.is_owned():
                self.__empty_planets.append(planet)
            else:
                if planet.owner.id == self.player_id:
                    self.__team_planets.append(planet)
                else:
                    try:
                        self.__enemy_planets[planet.owner.id].append(planet)
                    except KeyError:
                        self.__enemy_planets[planet.owner.id] = [planet]

        # ship list & dictionary
        self.__enemy_ship = {}
        self.__team_ship = []
        for ship in self.game_map._all_ships():
            if ship.owner.id == self.player_id:
                self.__team_ship.append(ship)
            else:
                try:
                    self.__enemy_ship[ship.owner.id].append(ship)
                except KeyError:
                    self.__enemy_ship[ship.owner.id] = [ship]

    def player_with_max_planet(self):
        """
        Helper function to find the player_id that has the max number of planets
        :return: return both the player_id and the number of planets
        """

        max_nb = 0
        max_player_id = None
        # Loop through all player to find which has the most planet
        for player_id, list_planets in self.__enemy_planets.items():
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
        for player_id, list_ships in self.__enemy_ship.items():
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
        if player_id == self.player_id:
            # If it's the current player, get the list of ship from __team_ship
            list_ship = self.__team_ship
        else:
            # if it's an enemy, get the list from the __enemy_ship[player_id] dictionary
            list_ship = self.__enemy_ship[player_id]

        sum_x = 0
        sum_y = 0
        for ship in list_ship:
            sum_x += ship.pos.x
            sum_y += ship.pos.y

        center_x = sum_x / len(list_ship)
        center_y = sum_y / len(list_ship)

        logger.debug("Calculated the gravititinal center of player_id %s: %s,%s" % (player_id, center_x, center_y))

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

        #If we have already calculated the nemesis this turn
        if self.__nemesis is not None:
            return self.__nemesis

        #If there is only one enemy, no need to calculate anything
        if len(self.__enemy_ship) == 1:
            self.__nemesis = list(self.__enemy_ship.keys())[0]
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
        for enemy_id in self.__enemy_planets.keys():
            # Calculate the gravitational_center
            enemy_g_center = self.gravitational_center(enemy_id)
            # Calculate the distance
            distance = calculate_distance_between(team_g_center, enemy_g_center)
            # Get the number of ships
            try:
                nb_ship = len(self.__enemy_ship[enemy_id])
            except KeyError:
                nb_ship = 0
            # Get the number of planets
            try:
                nb_planet = len(self.__enemy_planets[enemy_id])
            except KeyError:
                nb_planet = 0
            #Calculate the score
            score = SHIP_WEIGHT * nb_ship + PLANET_WEIGHT * nb_planet + PROXIMITY_WEIGHT * distance
            enemy_score[enemy_id] = score
            logger.info("Score of the player_id %s is %s" % (enemy_id, score))

        # Find the nemesis : the enemy with the biggest score
        max_score = -9999
        nemesis = None
        for enemy_id, score  in enemy_score.items():
            if score > max_score:
                max_score = score
                nemesis = enemy_id

        self.__nemesis = nemesis
        return self.__nemesis