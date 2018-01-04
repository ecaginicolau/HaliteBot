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
# Always try to have at least 1 ship attacking (if not alone?)
MIN_SHIP_ATTACKERS = 0
# Even if there are still some available planet, send a portion of the ship to attack
MAX_RATIO_SHIP_ATTACKERS = 0.20
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
SAFE_ZONE_RADIUS = 70  # 10 turns?
# If we can't find a path to the target look for a path in an intermediate position
INTERMEDIATE_RATIO = 0.5
# Minimum score to trigger a defensive move
MIN_SCORE_DEFENSE = 150
# If the distance between the ship and it's target is bigger than that, then try to predict its destination: 28 ~4 turn max speed
FOLLOW_DISTANCE = 28
"""
# Drone parameters
"""
# Nb of turn the ship is set to defender mode
MAX_TURN_DEFENDER = 5
# Threat score calculation: distance * DISTANCE_WEIGHT + threat * THREAT_WEIGHT
DISTANCE_WEIGHT = 2
THREAT_WEIGHT = 1

""""
# Navigation parameters
"""
# The radius the assassin tries to avoid enemy ship, 7+? 14+?
ASSASSIN_AVOID_RADIUS = 16
