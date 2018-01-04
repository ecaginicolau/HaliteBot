import logging
from copy import copy

from bot.settings import SHIP_WEIGHT, PLANET_WEIGHT, PROXIMITY_WEIGHT, MIN_ANGLE_TARGET, NO_THREAT, THREAT_BY_TURN_RATIO, DEFENSE_FORWARD, DEFENSE_POINT_RADIUS, \
    INITIAL_SAFE_DISTANCE, MIN_SHIP_ATTACKERS
from bot.navigation import Circle, calculate_distance_between, calculate_direction, calculate_angle_vector, calculate_length
from hlt.entity import Ship, Position

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
        if min_distance < INITIAL_SAFE_DISTANCE:
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
                if enemy_id == Monitor.player_id:
                    total_list.extend(list_ship)
            return total_list

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
        player_id
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
        logging.debug(Monitor.__gravitational_center)
        return Monitor.__gravitational_center[player_id]

    @staticmethod
    def defense_point():
        """
        Find a suitable place for defender to wait for attackers
        near our center of gravity, toward enemies center of gravity
        :return:
        """
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
        ratio = (nb_ships_enemies * 2) / float(nb_ships_enemies * 2 + Monitor.nb_ships_player(player_id))
        direction = direction / (calculate_length(direction) * ratio)
        defense = our_center + direction
        logging.debug("Defense points: %s, Our center: %s, Enemy center: %s" % (defense,our_center, enemy_center))
        # Make it a position
        defense = Position(defense.x, defense.y, DEFENSE_POINT_RADIUS)
        return defense



    @staticmethod
    def find_nemesis():
        """
        Calculate which player should be targeted next, based on number of ship, number of planets ...
        # Return the current nemesis if already calculated for this turn
        - if Monitor.nemesis != None
        # Otherwise calculate it again
        - Depends on hyper parameters, SHIP_WEIGHT, PLANET_WEIGHT, PROXIMITY_WEIGHT
        - Could count which player has been too close of our frontier
        - The distance between the average of our planets
        - Many other criteria

        The nemesis can change over time, maybe in the same turn (avoid launching all ships to the same enemy?)

        :return: the player_id of our nemesis
        """

        # If we have already calculated the nemesis this turn
        if Monitor.__nemesis is not None:
            return Monitor.__nemesis

        # If there is only one enemy, no need to calculate anything
        if len(Monitor.__ship_by_player) == 2:
            for enemy_id in Monitor.__ship_by_player.keys():
                if enemy_id != Monitor.player_id:
                    return enemy_id
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
        team_g_center = Monitor.gravitational_center(Monitor.player_id)

        # Store the score for each enemy
        enemy_score = {}

        # Loop through all enemies
        for enemy_id in Monitor.__ship_by_player.keys():
            logging.debug("calculating score of: %s" % enemy_id)
            # This is not an enemy, it's ourself
            if enemy_id == Monitor.player_id:
                # Skip to next player
                continue
            # Calculate the gravitational_center
            enemy_g_center = Monitor.gravitational_center(enemy_id)
            # Calculate the distance
            distance = calculate_distance_between(team_g_center, enemy_g_center)
            # Get the number of ships
            try:
                nb_ship = len(Monitor.__ship_by_player[enemy_id])
            except KeyError:
                nb_ship = 0
            # Get the number of planets
            try:
                nb_planet = len(Monitor.__planets_by_player[enemy_id])
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

        Monitor.__nemesis = nemesis
        logging.debug("Found a nemesis: %s" % nemesis)
        return Monitor.__nemesis

    @staticmethod
    def get_threat_level(ship_id):
        try:
            return Monitor.__threat_level[ship_id]
        except KeyError:
            return NO_THREAT / 2

    @staticmethod
    def update_threat(ship_id, angle):
        old_threat = Monitor.get_threat_level(ship_id)
        logger.debug("old threat: %s" % old_threat)
        Monitor.__threat_level[ship_id] = old_threat - (90 + angle) * THREAT_BY_TURN_RATIO
        logger.debug("new threat: %s" % Monitor.__threat_level[ship_id])

    @staticmethod
    def calculate_threat_level():
        """
        Give a threat level for every enemy ship
        :return:
        """
        from bot.manager import Manager

        # Clean threat level of ship that died
        for ship_id in list(Monitor.__threat_level.keys()):
            try:
                # Check if the ship can be still found in the list of enemy ship
                Monitor.__all_ships_dict[ship_id]
            except KeyError:
                # Remove the ship if it can't be found
                del Monitor.__threat_level[ship_id]

        # Store the old threat level for delta calculation
        # old_threat_level = Monitor.__threat_level

        # loop through all enemy ship
        for enemy_id, list_ship in Monitor.__ship_by_player.items():
            # Don't check our own ships
            if enemy_id != Monitor.player_id:
                for ship_id in list_ship:
                    ship = Monitor.__all_ships_dict[ship_id]
                    # Easy : docked = no threat
                    if ship.docking_status != Ship.DockingStatus.UNDOCKED:
                        Monitor.__threat_level[ship.id] = NO_THREAT
                        # Skip to next ship
                        continue

                    # Try to guess the target
                    # Skip if the velocity is null
                    if ship.velocity.x == 0 and ship.velocity.y == 0:
                        #Monitor.__threat_level[ship.id] = NO_THREAT
                        continue
                    smallest_angle = 360
                    possible_target = None
                    for other_ship_id, other_ship in Monitor.__all_ships_dict.items():
                        # If they belong to the same owner, don't look
                        if ship.owner == other_ship.owner:
                            continue

                        # Calculate the direction between the 2 ships
                        delta = calculate_direction(ship.pos, other_ship.pos)
                        # Calculate the angle between the direction and the velocity
                        angle = calculate_angle_vector(ship.velocity, delta)
                        # Get an absolute angle: 10° == 350°
                        angle = min(angle, 360 - angle)
                        # logger.info("Dir: %.2f:%.2f, vel: %.2f:%.2f Angle between ship: %s & ship: %s is %s"  %
                        #  (delta.x, delta.y, ship.velocity.x, ship.velocity.y,ship_id, other_ship_id, angle))
                        if angle < smallest_angle:
                            smallest_angle = angle
                            possible_target = other_ship

                    # Update the threat of that ship, the smallest the angle the more the threat increase (threat value decrease)
                    logging.debug("Update threat of ship_id: %s with angle: %s" % (ship_id, smallest_angle))
                    Monitor.update_threat(ship_id, smallest_angle)

                    if (possible_target is not None) and (smallest_angle < MIN_ANGLE_TARGET) and (possible_target.owner.id == Monitor.player_id):
                        # The threat is an estimation of the number it would take to the ship to arrives
                        distance = calculate_distance_between(ship.pos, possible_target.pos)
                        Monitor.__threat_level[ship.id] = distance
                        logger.info("Found a possible target for ship: %s it's: ship %s" % (ship.id, possible_target.id))
                        Manager.add_possible_threat(possible_target.id, distance, ship.id)
