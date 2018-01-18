"""
# Hyperparameters
"""
import pickle
from random import randint, getrandbits
import logging

# Position toward the enemy from our gravitational center
DEFENSE_FORWARD = 30
# Radius of the defense position
DEFENSE_POINT_RADIUS = 5
# If the turn takes more than this, just exit
MAX_TURN_DURATION = 1.8
# Arbitrary threshold after which we need to sort ship by distance
NB_SHIP_THRESHOLD = 100
# Should a miner stop miner to become a defender
MINER_CAN_DEFEND = False
# If we can't find a path to the target look for a path in an intermediate position
INTERMEDIATE_RATIO = 0.5
# Minimum score to trigger a defensive move
MIN_SCORE_DEFENSE = 150
# If the distance between the ship and it's target is bigger than that, then try to predict its destination: 28 ~4 turn max speed
FOLLOW_DISTANCE = 28 # 28 was ok
# Always try to have at least 1 ship attacking (if not alone?)
MIN_SHIP_ATTACKERS = 0
# Even if there are still some available planet, send a portion of the ship to attack
MAX_RATIO_SHIP_ATTACKERS = 0.10
# ratio of offensive ship at the start of the game (before the game is full)
EARLY_RATIO_ATTACKER = 1.0
EARLY_RATIO_ASSASSIN = 0.0
EARLY_RATIO_DEFENDER = 0.0
# ratio of offensive ship at the end of the game (after the game is full)
LATE_RATIO_ATTACKER = 1.0
LATE_RATIO_ASSASSIN = 0.0
LATE_RATIO_DEFENDER = 0.0
# Threat score calculation: distance * DISTANCE_WEIGHT + threat * THREAT_WEIGHT
DISTANCE_WEIGHT = 2
THREAT_WEIGHT = 1
# Nb of turn the ship is set to defender mode
MAX_TURN_DEFENDER = 5
# The radius the assassin tries to avoid enemy ship, 7+? 14+?
ASSASSIN_AVOID_RADIUS = 7
# Threshold after which the point is considered inside the influence zone
INFLUENCE_THRESHOLD = 0


"""
# First hyperparameters to tests
"""
class Configuration(object):
    def __init__(self):
        # distance after which accept we slow down to regroup drones
        self.SLOW_TARGET_DISTANCE = 15
        self.SLOW_TO_TARGET = False
        self.INTERCEPT = False
        # Only apply the slow ratio to a part of the speed
        self.SLOW_SPEED_RATIO = 1.0
        # Check that no team starts too close, take x turns to arrive
        self.INITIAL_SAFE_DISTANCE = 115
        # Radius inside which an enemy must be for a drone to become a defender
        self.DEFENDER_RADIUS = 8
        # If no enemy in this radius of an attack, convert it to a conqueror
        self.SAFE_ZONE_RADIUS = 45  # 10 turns?
        # If the enemy is in this radius calculate the enemy squad size
        self.CONTACT_ZONE_RADIUS = 20
        # Planet score
        self.SCORE_NB_DOCKING_SPOTS = 1.4
        self.SCORE_DISTANCE_CENTER = 0.05
        # Distance after which we don't need to look for ship during navigation
        self.NAVIGATION_SHIP_DISTANCE = 92
        self.GHOST_RATIO_RADIUS = 1.3
        # The radius influence of a ship
        self.SHIP_INFLUENCE = 11
        # The radius influence of a planet
        self.PLANET_INFLUENCE = 7
        # The influence of an empty planet
        self.INFLUENCE_EMPTY_PLANET = 32
        self.INFLUENCE_ZONE = 32
        self.INFLUENCE_STEP = 5
        # Nb turn in history we look for the max nb of ship in our influence
        self.NB_TURN_INFLUENCE = 8
        # Nb enemy ratio
        self.NB_IN_INFLUENCE_RATIO = 1.8
        # Distance to trigger squad creation
        self.SQUAD_DISTANCE_CREATION = 20
        # Radius of the squad by number of ship
        self.SQUAD_SCATTERED_THRESHOLD = 2.4
        self.SQUAD_SIZE = 6
        self.SQUAD_REGROUP = False
        # Ratio of bravery of the squad
        self.SQUAD_BRAVERY = 1
        # Radius into which we count the number of enemiy ships
        self.ENEMY_SQUAD_RADIUS = 5
        # True if we create squad
        self.CREATE_SQUAD = True
        self.SQUAD_RUN_AWAY = False
        # Add the center as a ghost, doesn't work that well
        self.CENTER_GHOST = False

        # enemy ghost
        self.ENEMY_GHOST = False
        self.ENEMY_GHOST_VELOCITY_RATIO = 0.5

        # troll settings
        self.TROLL_ANGLE_STEP = 20
        self.TROLL_DISTANCE = 18
        self.TROLL_EXIST = True

    handled_data={
        #"INITIAL_SAFE_DISTANCE": 5,
        #"DEFENDER_RADIUS": 1,
        #"SCORE_NB_DOCKING_SPOTS": 0.1,
        #"SCORE_DISTANCE_CENTER": 0.01,
        #"NAVIGATION_SHIP_DISTANCE": 1,
        "GHOST_RATIO_RADIUS": 0.1,
        "SHIP_INFLUENCE": 1,
        "PLANET_INFLUENCE": 1,
        "INFLUENCE_STEP": 1,
        "NB_TURN_INFLUENCE": 1,
        "NB_IN_INFLUENCE_RATIO": 0.1,
        "SAFE_ZONE_RADIUS": 1,
        "CONTACT_ZONE_RADIUS": 1,
        "ENEMY_SQUAD_RADIUS": 1,
        "SQUAD_DISTANCE_CREATION": 1,
        "SQUAD_BRAVERY": 0.1,
        "SQUAD_SCATTERED_THRESHOLD": 0.1,
        # "SQUAD_REGROUP": False
    }

    def save_configuration(self, best=False, filename=None):
        data = {}
        for key in Configuration.handled_data.keys():
            data[key]=getattr(self, key)
        if filename is None:
            if best:
                filename = "best_configuration.pickle"
            else:
                filename = "configuration.pickle"

        pickle.dump(data, open(filename, "wb"))

    def load_configuration(self, best=False, filename=None):
        if filename is None:
            if best:
                filename = "best_configuration.pickle"
            else:
                filename = "configuration.pickle"
        data = pickle.load(open(filename, "rb"))

        for key in sorted(data.keys()):
            value = data[key]
            setattr(self, key, value)
            logging.debug("[Configuration]%s = %s" % (key, value))

    def random_step(self):
        # for each value, get a random number : -1, 0 or 1. Apply the step for each value
        for key in Configuration.handled_data.keys():
            # If it's not a boolean field
            if Configuration.handled_data[key] is not False:
                value = getattr(self, key) + self.handled_data[key] * randint(-1,1)
            else:
                value = bool(getrandbits(1))
            setattr(self, key, value)

    def __get__(self, instance, owner):
        return getattr(self, instance)


config = Configuration()


if __name__ == "__main__":
    config.save_configuration()
    config.save_configuration(True)
