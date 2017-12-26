from libc.math cimport sqrt, atan2, M_PI, sin, cos, round
from hlt.entity import Ship, Planet, Entity
from hlt.game_map import Map

cdef class Position:
    """
    A simple wrapper for a coordinate. Intended to be passed to some functions in place of a ship or planet.

    :ivar x: The x-coordinate.
    :ivar y: The y-coordinate.
    :ivar radius: The radius
    """
    cdef public int x
    cdef public int y
    cdef public int radius
    def __init__(self, int x, int y, int radius = 0):
        self.x = x
        self.y = y
        self.radius = radius



cpdef float calculate_distance_between(Position p1, Position p2):
    """
    Calculate the distance between 2 points, p1 and p2
    :param p1: Position #1 (the ship)
    :param p2: Position #2 (the target)
    :return: float, distance
    """
    return sqrt(((p1.x - p2.x) ** 2) + ((p1.y - p2.y) ** 2))


cpdef float calculate_angle_between(Position p1, Position p2):
    """
    Calculates the angle between this object and the target in degrees.

    :param p1: Position #1 (the ship)  
    :param p2: Position #2 (the target)  
    :return: Angle between entities in degrees
    :rtype: float
    """
    return (180 / M_PI * atan2(p2.y - p1.y, p2.x - p1.x)) % 360


cpdef Position closest_point_to(Position p1, Position p2, int min_distance=3):
    """
    Find the closest point to the given ship near the given target, outside its given radius,
    with an added fudge of min_distance.

    :param p1: Position #1 (the ship)
    :param p2: Position #1 (the target)
    :param radius: int the entity radius
    :param int min_distance: Minimum distance specified from the object's outer radius
    :return: The closest point's coordinates
    :rtype: Position
    """
    cdef float angle = calculate_angle_between(p2, p1)
    cdef float radius = p2.radius + min_distance
    cdef int x = int(round(p2.x + radius * cos(angle * M_PI / 180.0)))
    cdef int y = int(round(p2.y + radius * sin(angle * M_PI / 180.0)))

    return Position(x, y)



cpdef tuple navigate_old(Position p1, Position p2, int speed):
    """
    #Very basic path finding, don't avoid obstacle at all
    :param p1: Position #1 (the ship)
    :param p2: Position #2 (the target)
    :param speed: the speed
    :return:
    """

    cdef int distance = int(round(calculate_distance_between(p1, p2)))
    cdef angle = calculate_angle_between(p1, p2)
    speed = speed if (distance >= speed) else distance
    return speed, angle



cpdef bint intersect_segment_circle(Position start, Position end, Position circle, float fudge=0.5):
    """
    Test whether a line segment and circle intersect.

    :param Entity start: The start of the line segment. (Needs x, y attributes)
    :param Entity end: The end of the line segment. (Needs x, y attributes)
    :param Entity circle: The circle to test against. (Needs x, y, r attributes)
    :param float fudge: A fudge factor; additional distance to leave between the segment and circle. (Probably set this to the ship radius, 0.5.)
    :return: True if intersects, False otherwise
    :rtype: bool
    """
    # Derived with SymPy
    # Parameterize the segment as start + t * (end - start),
    # and substitute into the equation of a circle
    # Solve for t
    cdef float dx = end.x - start.x
    cdef float dy = end.y - start.y

    cdef float a = dx**2 + dy**2
    cdef float b = -2 * (start.x**2 - start.x*end.x - start.x*circle.x + end.x*circle.x +
              start.y**2 - start.y*end.y - start.y*circle.y + end.y*circle.y)
    #cdef float c = (start.x - circle.x)**2 + (start.y - circle.y)**2

    if a == 0.0:
        # Start and end are the same point
        return calculate_distance_between(start,circle) <= circle.radius + fudge

    # Time along segment when closest to the circle (vertex of the quadratic)
    cdef float t = min(-b / (2 * a), 1.0)
    if t < 0:
        return False

    cdef int closest_x = int(round(start.x + dx * t))
    cdef int closest_y = int(round(start.y + dy * t))
    cdef float closest_distance = calculate_distance_between(Position(closest_x, closest_y),circle)

    return closest_distance <= circle.radius + fudge



cpdef bint obstacles_between(Position ship, Position target, game_map, ignore_ships = False, ignore_planets= False):
    """
    Check whether there is a straight-line path to the given point, without planetary obstacles in between.

    :param entity.Ship ship: Source entity
    :param entity.Entity target: Target entity
    :param Map game_map: The game_map to get all ships & planets
    :param bool ignore_ships: should we ignore ships
    :param bool ignore_planets: should we ignore planets
    :return: True if there is an obstacle, False if there is not
    :rtype: bool
    """

    obstacles = []
    entities = []
    if not ignore_planets :
        entities.extend(game_map.all_planets())
    if not ignore_ships :
        entities.extend(game_map._all_ships())
    for foreign_entity in entities:
        if foreign_entity == ship or foreign_entity == target:
            continue
        if intersect_segment_circle(ship, target, foreign_entity, fudge=ship.radius + 0.1):
            return True
    return False

cpdef tuple navigate(ship, target, game_map, speed, max_corrections=90, angular_step=1,
                     ignore_ships=False, ignore_planets=False):
    """
    Move a ship to a specific target position (Entity). It is recommended to place the position
    itself here, else navigate will crash into the target. If avoid_obstacles is set to True (default)
    will avoid obstacles on the way, with up to max_corrections corrections. Note that each correction accounts
    for angular_step degrees difference, meaning that the algorithm will naively try max_correction degrees before giving
    up (and returning None). The navigation will only consist of up to one command; call this method again
    in the next turn to continue navigating to the position.

    :param Entity target: The entity to which you will navigate
    :param game_map.Map game_map: The map of the game, from which obstacles will be extracted
    :param int speed: The (max) speed to navigate. If the obstacle is nearer, will adjust accordingly.
    :param int max_corrections: The maximum number of degrees to deviate per turn while trying to pathfind. If exceeded returns None.
    :param int angular_step: The degree difference to deviate if the original destination has obstacles
    :param bool ignore_ships: Whether to ignore ships in calculations (this will make your movement faster, but more precarious)
    :param bool ignore_planets: Whether to ignore planets in calculations (useful if you want to crash onto planets)
    :return tuple: speed & angle of thrust
    :rtype: tuple
    """
    # Assumes a position, not planet (as it would go to the center of the planet otherwise)
    if max_corrections <= 0:
        return None
    cdef float distance = calculate_distance_between(ship, target)
    cdef float angle = calculate_angle_between(ship, target)

    cdef int new_target_dx
    cdef int new_target_dy
    cdef Position new_target
    #If we try to avoid an obstacle
    if not ignore_ships or not ignore_planets:
        if obstacles_between(ship, target, game_map, ignore_ships=ignore_ships, ignore_planets=ignore_planets):
            new_target_dx = int(round(cos((M_PI / 180.0) * (angle + angular_step)) * distance))
            new_target_dy = int(round(sin((M_PI / 180.0) * (angle + angular_step)) * distance))
            new_target = Position(ship.x + new_target_dx, ship.y + new_target_dy)
            return navigate(ship, new_target, game_map, speed, max_corrections - 1, angular_step,
                            ignore_ships=ignore_ships, ignore_planets=ignore_planets)
    speed = speed if (distance >= speed) else distance
    return int(round(speed)), int(round(angle))
