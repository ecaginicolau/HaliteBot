import logging
from bot.settings import DEFENSE_POINT_RADIUS, config
from bot.navigation import Circle, calculate_distance_between, calculate_length
from hlt.entity import Ship, Position
from .influence import Influence

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

    # Store the player id, will be used to distinguish ships
    player_id = None
    # Store the game_map, must be updated every turn
    game_map = None
    # Store the current nemesis, must be reset every turn
    __nemesis = None
    # Store the threat level of each ship, dictionary indexed by ship_id
    __threat_level = {}
    # Store the list of planet for each enemy, indexed by player_id
    __planets_by_player = {}
    # Store the list of empty_planet, for comparison purpose
    __empty_planets = {}
    # Store all planets indexed by planet_id
    __all_planets_dict = {}
    # Store the list of enemy ship indexed by player_id
    __ship_by_player = {}
    # Will store all ships in dictionary, should be updated every turn
    __all_ships_dict = {}
    # Store the old_position of every ship to calculate vel_x & vel_y, indexed by ship_id
    __all_ships_old_position = {}
    # Store the gravitational center of every team
    __gravitational_center = {}
    # Game turn number
    turn = 0
    # Store the number of enemy ships inside our influence zone
    __nb_in_influence = None
    # History nb ship in influence
    __history_nb_in_influence = []
    # Store the miners & futur miners of a planet,indexed by planet id
    __planets_miners = {}

    @staticmethod
    def init(player_id):
        # Store the player id, will be used to distinguish ships
        Monitor.player_id = player_id

    @staticmethod
    def update_game(game_map):
        """
        [EVERY TURN]
        Update the game_map & other internal variable that will help monitor the current game
        :param game_map:
        :return:
        """
        # Update the game_map
        Monitor.game_map = game_map
        # Update the turn number
        Monitor.turn = game_map.turn
        # Reset turn's variable
        # Reset the nemesis
        Monitor.__nemesis = None
        # Planets list & dictionary
        Monitor.__planets_by_player = {}
        Monitor.__empty_planets = {}
        Monitor.__all_planets_dict = {}
        # Loop through all planet, look for empty & owned planets
        for planet in Monitor.game_map.all_planets():
            Monitor.__all_planets_dict[planet.id] = planet
            if not planet.is_owned():
                Monitor.__empty_planets[planet.id] = planet
            else:
                try:
                    Monitor.__planets_by_player[planet.owner.id].append(planet.id)
                except KeyError:
                    Monitor.__planets_by_player[planet.owner.id] = [planet.id]

        # gravitational center
        # ship list & dictionary
        Monitor.__ship_by_player = {}
        Monitor.__all_ships_dict = {}
        Monitor.__gravitational_center = {}
        for ship in Monitor.game_map.all_ships():
            # Update the gravitational center if it exist
            try:
                Monitor.__gravitational_center[ship.owner.id] += ship.pos
            except KeyError:
                Monitor.__gravitational_center[ship.owner.id] = Circle.zero() + ship.pos
            # Update the list of all ships & ships by team
            Monitor.__all_ships_dict[ship.id] = ship
            try:
                Monitor.__ship_by_player[ship.owner.id].append(ship.id)
            except KeyError:
                Monitor.__ship_by_player[ship.owner.id] = [ship.id]

        # Average the gravitational center
        for team_id, center in Monitor.__gravitational_center.items():
            Monitor.__gravitational_center[team_id] = center / len(Monitor.__ship_by_player[team_id])
            Monitor.__gravitational_center[team_id].radius = len(Monitor.__ship_by_player[team_id])

        # Calculate velocity of all ship
        Monitor.calculate_velocity()

        # Reset the defense point
        Monitor.__defense_points = None

        # Reset influence value
        Monitor.__nb_in_influence = None

    @staticmethod
    def initial_turn():
        global MIN_SHIP_ATTACKERS
        # Get the minimum distance between us and other player
        min_distance = 999
        # Get our center of gravitiy
        our_center = Monitor.__gravitational_center[Monitor.player_id]
        # Loop through all other player
        for team_id, team_center in Monitor.__gravitational_center.items():
            # Dont look at our own ships
            if team_id == Monitor.player_id:
                distance = calculate_distance_between(our_center, team_center)
                if distance < min_distance:
                    min_distance = distance
        # Check that no team starts too close
        if min_distance < config.INITIAL_SAFE_DISTANCE:
            MIN_SHIP_ATTACKERS = 1
        else:
            MIN_SHIP_ATTACKERS = 0

    @staticmethod
    def calculate_velocity():
        # Keep the list of ship_id that needs to be deleted from old_postion
        need_to_be_deleted = []

        # Delete useless old position (not a ship anymore)
        for ship_id, old_position in Monitor.__all_ships_old_position.items():
            try:
                # Get the ship, will trigger a KeyERror exception if it doesn't exist anymore
                ship = Monitor.__all_ships_dict[ship_id]
                # Calculate the velocity based on the old positoin
                ship.velocity = Circle(ship.pos.x - old_position.x, ship.pos.y - old_position.y)
                # Store the new position for next turn
            except KeyError:
                # If the ship can't be found anymore add it to "need_to_be_deleted" list for later
                need_to_be_deleted.append(ship_id)

        # Now delete useless ship
        for ship_id in need_to_be_deleted:
            del Monitor.__all_ships_old_position[ship_id]

        # Update the position of all existing ship
        for ship_id, ship in Monitor.__all_ships_dict.items():
            Monitor.__all_ships_old_position[ship_id] = Circle(ship.pos.x, ship.pos.y)

    @staticmethod
    def get_all_planets_dict():
        return Monitor.__all_planets_dict

    @staticmethod
    def get_all_ships_dict():
        return Monitor.__all_ships_dict

    @staticmethod
    def get_enemy_ships(player_id=None):
        """
        return the list of all enemies or a single enemy
        :param player_id: if player_id is not None return only the ships of this player, otherwise return all ships
        :return: the list of ships
        """
        if player_id is not None:
            return Monitor.__ship_by_player[player_id]
        else:
            total_list = []
            for enemy_id, list_ship in Monitor.__ship_by_player.keys():
                # Don't get our ships
                if enemy_id != Monitor.player_id:
                    total_list.extend(list_ship)
            return total_list

    @staticmethod
    def map_has_available_spots():
        """
        This function check if at least 1 planet has a free spot, no need to create conqueror otherwise
        :return: true if there is at least one planet with a free spot
        """
        list_planets = Monitor.get_free_planets()
        for planet in list_planets:
            if planet.nb_available_docking_spots() > 0:
                return True

        return False

    @staticmethod
    def get_map_center():
        center = Circle(Monitor.game_map.width / 2.0, Monitor.game_map.height / 2.0)
        return center

    @staticmethod
    def get_free_planets():
        """
        Return the list of free (empty or owned not full) planet
        :return: list of planet that are free
        """
        list_free_planet = []
        for planet_id, planet in Monitor.__all_planets_dict.items():
            # Skip if full
            if planet.is_full():
                continue
            # Skip if not owned by us or empty
            if planet.is_owned() and planet.owner.id != Monitor.player_id:
                continue
            # Otherwise add the the list of free planet
            list_free_planet.append(planet)
        return list_free_planet

    @staticmethod
    def get_planet(planet_id):
        """
        return a single planet
        :param planet_id:
        :return:
        """
        return Monitor.__all_planets_dict[planet_id]

    @staticmethod
    def get_empty_planets():
        return Monitor.__empty_planets

    @staticmethod
    def get_planets_by_player():
        return Monitor.__planets_by_player

    @staticmethod
    def get_empty_planet(planet_id):
        """
        return a single planet
        raison a KeyError exception if the planet can't be found in the list of empty planets
        :param planet_id:  the id of the planet
        :return:
        """
        return Monitor.__empty_planets[planet_id]

    @staticmethod
    def nb_owned_planets():
        """
        Return the number of planet owned by ourself
        :return:
        """
        return len(Monitor.__planets_by_player[Monitor.player_id])

    @staticmethod
    def nb_empty_planets():
        """
        Return the number of empty planets
        :return:
        """
        return len(Monitor.__empty_planets)

    @staticmethod
    def nb_ships_player(player_id):
        try:
            return len(Monitor.__ship_by_player[player_id])
        except KeyError:
            return 0

    @staticmethod
    def get_ship_by_player():
        return Monitor.__ship_by_player

    @staticmethod
    def get_team_ships():
        """
        Return the list of ships of our team
        :return:
        """
        return Monitor.__ship_by_player[Monitor.player_id]

    @staticmethod
    def get_ship(ship_id):
        """
        return a single ship
        Raise KeyError exception if the ship_id is not found
        :param ship_id:
        :return:
        """
        return Monitor.__all_ships_dict[ship_id]

    @staticmethod
    def player_with_max_planet():
        """
        Helper function to find the player_id that has the max number of planets
        :return: return both the player_id and the number of planets
        """

        max_nb = 0
        max_player_id = None
        # Loop through all player to find which has the most planet
        for player_id, list_planets in Monitor.__planets_by_player.items():
            nb = len(list_planets)
            if nb > max_nb:
                max_nb = nb
                max_player_id = player_id

        return max_player_id, max_nb

    @staticmethod
    def player_with_max_ship():
        """
        Helper function to find the player_id that has the max number of ships
        :return: return both the player_id and the number of ships
        """

        max_nb = 0
        max_player_id = None
        # Loop through all player to find which has the most planet
        for player_id, list_ships in Monitor.__ship_by_player.items():
            nb = len(list_ships)
            if nb > max_nb:
                max_nb = nb
                max_player_id = player_id

        return max_player_id, max_nb

    @staticmethod
    def gravitational_center(player_id):
        """
        Return the pre-calculated center of gravity for a player_id
            - Sum all X coordinates of every ships
            - Sum all Y coordinates of every ships
            - Divide by the number of ships
        :param player_id:
        :return: x  & y of the gratitional center
        """
        return Monitor.__gravitational_center[player_id]

    @staticmethod
    def defense_point():
        """
        Find a suitable place for defender to wait for attackers
        near our center of gravity, toward enemies center of gravity
        :return:
        """
        if Monitor.__defense_points is None:
            our_center = Monitor.gravitational_center(Monitor.player_id)
            enemy_center = Circle.zero()
            # Loop through all enemy player id
            nb_ships_enemies = 0
            for player_id in Monitor.__ship_by_player.keys():
                # If it's not our team
                if player_id != Monitor.player_id:
                    enemy_center += Monitor.gravitational_center(player_id)
                    nb_ships_enemies += Monitor.nb_ships_player(player_id)
            enemy_center /= len(Monitor.__ship_by_player) - 1

            direction = enemy_center - our_center
            ratio = nb_ships_enemies / float(nb_ships_enemies + Monitor.nb_ships_player(Monitor.player_id))
            #ratio = 0.5
            direction = direction / (calculate_length(direction) * ratio)
            defense = our_center + direction
            # Make it a position
            Monitor.__defense_points = Position(defense.x, defense.y, DEFENSE_POINT_RADIUS)
        return Monitor.__defense_points

    @staticmethod
    def nb_ship_in_influence_last_x(nb_turn):
        """
        Return the number of enemy ships inside our influence zone
        :return: int
        """
        Monitor.nb_ship_in_influence()
        try:
            nb = int(max(Monitor.__history_nb_in_influence[-nb_turn:]))
            logging.debug("nb_ship_in_influence_last_X: %s" % nb)
            return nb
        except KeyError:
            return 0


    @staticmethod
    def nb_ship_in_influence():
        """
        Return the number of enemy ships inside our influence zone
        :return: int
        """
        # Cache mechanism to avoid counting each time
        if Monitor.__nb_in_influence is None:
            Monitor.__nb_in_influence = 0
            # loop through all enemy ship
            for enemy_id, list_ship in Monitor.__ship_by_player.items():
                # Don't check our own ships
                if enemy_id != Monitor.player_id:
                    # Loop through all ships
                    for ship_id in list_ship:
                        # Get the ship
                        ship = Monitor.__all_ships_dict[ship_id]
                        # Only count undocked ship
                        if ship.docking_status == Ship.DockingStatus.UNDOCKED:
                            # Check if the ship is in the influence zone
                            if Influence.is_in_influence_zone(ship.pos):
                                Monitor.__nb_in_influence += 1
            Monitor.__history_nb_in_influence.append(Monitor.__nb_in_influence)
        # Return the number of ship in our influence zone
        logging.debug("nb_ship_in_influence: %s" % Monitor.__nb_in_influence)
        return Monitor.__nb_in_influence

    @staticmethod
    def check_planets_miners():
        """
        Remove dead drone
        :return:
        """
        from .manager import Manager
        for planet_id, list_drone in Monitor.__planets_miners.items():
            new_list = []
            for ship_id in list_drone:
                if Manager.get_drone(ship_id) is not None:
                    new_list.append(ship_id)
            Monitor.__planets_miners[planet_id] = new_list

    """
    # Miner version of the "nb spot functions"
    """
    @staticmethod
    def map_has_available_spots_for_miners():
        return Monitor.get_total_nb_spots_for_miners() > 0

    @staticmethod
    def get_planets_miners(planet_id):
        try:
            return Monitor.__planets_miners[planet_id]
        except KeyError:
            return []

    @staticmethod
    def add_planets_miner(planet_id, drone):
        try:
            Monitor.__planets_miners[planet_id].append(drone)
        except KeyError:
            Monitor.__planets_miners[planet_id] = []
            Monitor.__planets_miners[planet_id].append(drone)

    @staticmethod
    def get_total_nb_spots_for_miners():
        nb = 0
        for planet in Monitor.get_free_planets():
            nb += Monitor.get_nb_spots_for_miners(planet.id)
        return nb

    @staticmethod
    def get_nb_spots_for_miners(planet_id):
        try:
            planet = Monitor.get_planet(planet_id)
        except KeyError:
            return 0
        nb = max(0, planet.num_docking_spots - len(Monitor.get_planets_miners(planet.id)))
        return nb
