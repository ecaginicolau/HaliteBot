"""
# Monitor parameters
# Hyperparameters for nemesis calculation
"""
# score increase with the number of ship, so SHIP_WEIGHT > 0
SHIP_WEIGHT = 1.0
# score increase with the number of planets, so PLANET_WEIGHT > 0
PLANET_WEIGHT = 3.0
# score decrease as the distance increase, so PROXIMITY_WEIGHT < 0
PROXIMITY_WEIGHT = -0.05
# Minimum angle for a target to be considered as possible
MIN_ANGLE_TARGET = 10
# constant for no threat, ship should start with a threat of NO_THREAT / 2
NO_THREAT = 1000
# Ratio at wich the threat move by turn
THREAT_BY_TURN_RATIO = 0.1
# Position toward the enemy from our gravititional center
DEFENSE_FORWARD = 30
# Radius of the defense position
DEFENSE_POINT_RADIUS = 5
# Check that no team starts too close, take x turns to arrive
INITIAL_SAFE_DISTANCE = 120

"""
# Manager parameters
"""
# Some global
# Radius inside which an enemy must be for a drone to become a defender
DEFENDER_RADIUS = 10
# Special radius for miner to react faster
MINER_DEFENDER_RADIUS = 10
# If the turn takes more than this, just exit
MAX_TURN_DURATION = 1.8
# Arbitrary threshold after which we need to sort ship by distance
NB_SHIP_THRESHOLD = 100
# Should a miner stop miner to become a defender
MINER_CAN_DEFEND = False
# If no enemy in this radius of an attack, convert it to a conqueror
SAFE_ZONE_RADIUS = 50  # 10 turns?
# If we can't find a path to the target look for a path in an intermediate position
INTERMEDIATE_RATIO = 0.5
# Minimum score to trigger a defensive move
MIN_SCORE_DEFENSE = 150
# If the distance between the ship and it's target is bigger than that, then try to predict its destination: 28 ~4 turn max speed
FOLLOW_DISTANCE = 28
# Radius into which we count the number of enemiy ships
ENEMY_SQUAD_RADIUS = 7


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

"""
# Drone parameters
"""
# Nb of turn the ship is set to defender mode
MAX_TURN_DEFENDER = 5
# Threat score calculation: distance * DISTANCE_WEIGHT + threat * THREAT_WEIGHT
DISTANCE_WEIGHT = 2
THREAT_WEIGHT = 1

# Planet score
SCORE_NB_DOCKING_SPOTS = 1
SCORE_NB_SHIP_ONGOING = 1
SCORE_DISTANCE_CENTER = 0.05

# Distance after which we don't need to look for ship during navigation
NAVIGATION_SHIP_DISTANCE = 90

GHOST_RATIO_RADIUS = 1.6
""""
# Navigation parameters
"""
# The radius the assassin tries to avoid enemy ship, 7+? 14+?
ASSASSIN_AVOID_RADIUS = 7

"""
# Influence parameters
"""
# The radius influence of a ship
SHIP_INFLUENCE = 10
# The radius influence of a planet
PLANET_INFLUENCE = 10
# The influence of an empty planet
INFLUENCE_EMPTY_PLANET = 32
INFLUENCE_ZONE = 32
INFLUENCE_STEP = 4
# Threshold after which the point is considered inside the influence zone
INFLUENCE_THRESHOLD = 0
# Nb turn in history we look for the max nb of ship in our influence
NB_TURN_INFLUENCE = 5
# Nb enemy ratio
NB_IN_INFLUENCE_RATIO = 0.8

"""
# SQUAD
"""
SQUAD_DISTANCE_CREATION = 20
# Radius of the squad by number of ship
SQUAD_SCATTERED_THRESHOLD = 3
SQUAD_SIZE = 6
