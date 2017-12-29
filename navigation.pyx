from libc.math cimport sqrt, M_PI , sin, cos, round ,atan2
import logging
logger = logging.getLogger("navigation")

cdef double radians(double angle):
    return (angle/180.0) * M_PI



cdef double degrees(double angle):
    return (angle/M_PI) * 180.0


cdef class Circle:
    """
    A simple wrapper for a coordinate. Intended to be passed to some functions in place of a ship or planet.

    :ivar x: The x-coordinate.
    :ivar y: The y-coordinate.
    :ivar radius: The radius
    """
    cdef public double x
    cdef public double y
    cdef public double radius
    def __init__(self, double x, double y, double radius = 0):
        self.x = x
        self.y = y
        self.radius = radius

    def __str__(self):
        return "Circle(%s, %s, %s)" % (self.x, self.y, self.radius)

    def __repr__(self):
        return self.__str__()




cpdef double calculate_distance_between(Circle p1, Circle p2):
    """
    Calculate the distance between 2 points, p1 and p2
    :param p1: Circle #1 (the ship)
    :param p2: Circle #2 (the target)
    :return: float, distance
    """

    return sqrt(((p1.x - p2.x) ** 2) + ((p1.y - p2.y) ** 2))



cpdef double calculate_angle_between(Circle p1, Circle p2):
    """
    Calculates the angle between this object and the target in degrees.

    :param p1: Circle #1 (the ship)  
    :param p2: Circle #2 (the target)  
    :return: Angle between entities in degrees
    :rtype: float
    """
    return (degrees(atan2(p2.y - p1.y, p2.x - p1.x))) % 360


cpdef Circle closest_point_to(Circle p1, Circle p2, int min_distance=3):
    """
    Find the closest point to the given ship near the given target, outside its given radius,
    with an added fudge of min_distance.

    :param p1: Circle #1 (the ship)
    :param p2: Circle #1 (the target)
    :param radius: int the entity radius
    :param int min_distance: Minimum distance specified from the object's outer radius
    :return: The closest point's coordinates
    :rtype: Circle
    """
    cdef double angle = calculate_angle_between(p2, p1)
    cdef double radius = p2.radius + min_distance
    cdef double x = p2.x + radius * cos(radians(angle))
    cdef double y = p2.y + radius * sin(radians(angle))

    return Circle(x, y)





cpdef bint intersect_segment_circle(Circle start,Circle end,Circle circle, fudge=0.5):
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
    cdef double dx = end.x - start.x
    cdef double dy = end.y - start.y

    cdef double a = dx**2 + dy**2

    #Never happens
    if a == 0.0:
        # Start and end are the same point
        return calculate_distance_between(start,circle) <= circle.radius + fudge

    cdef double b = -2 * (start.x**2 - start.x*end.x - start.x*circle.x + end.x*circle.x +
              start.y**2 - start.y*end.y - start.y*circle.y + end.y*circle.y)
    cdef double c = (start.x - circle.x)**2 + (start.y - circle.y)**2



    # Time along segment when closest to the circle (vertex of the quadratic)
    cdef double t = min(-b / (2 * a), 1.0)
    if t < 0:
        return False

    cdef double closest_x = start.x + dx * t
    cdef double closest_y = start.y + dy * t
    cdef Circle closest = Circle(closest_x,closest_y)
    cdef double closest_distance = calculate_distance_between(closest, circle)

    return closest_distance <= circle.radius + fudge

cpdef bint obstacles_between(Circle ship, Circle target, game_map,bint ignore_ships=False,bint ignore_planets = False):
    """
    Check whether there is a straight-line path to the given point, without planetary obstacles in between.

    :param entity.Ship ship: Source entity
    :param entity.Entity target: Target entity
    :param entity.Entity ignore: Which entity type to ignore
    :return: The list of obstacles between the ship and target
    :rtype: list[entity.Entity]
    """

    if not ignore_ships:
        for enemy_ship in game_map._all_ships():
            if enemy_ship.pos == ship or enemy_ship.pos == target:
                continue
            if intersect_segment_circle(ship, target, enemy_ship.pos, fudge=ship.radius + 0.1):
                return True
    if not ignore_planets:
        for planet in game_map.all_planets():
            if planet.pos == ship or planet.pos == target:
                continue
            if intersect_segment_circle(ship, target, planet.pos, fudge=ship.radius + 0.1):
                return True

    return False


cdef Circle dx_target(start, angle, distance):
    cdef int new_target_dx
    cdef int new_target_dy
    cdef Circle new_target
    if (angle < 0) :
        angle += 360
    angle = angle % 360
    new_target_dx = int(round(cos((M_PI / 180.0) * angle) * <double>distance))
    new_target_dy = int(round(sin((M_PI / 180.0) * angle) * <double>distance))
    new_target = Circle(start.x + new_target_dx, start.y + new_target_dy)
    logger.debug("dx_target: %s" % new_target)
    return new_target

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
    :param bool avoid_obstacles: Whether to avoid the obstacles in the way (simple pathfinding).
    :param int max_corrections: The maximum number of degrees to deviate per turn while trying to pathfind. If exceeded returns None.
    :param int angular_step: The degree difference to deviate if the original destination has obstacles
    :param bool ignore_ships: Whether to ignore ships in calculations (this will make your movement faster, but more precarious)
    :param bool ignore_planets: Whether to ignore planets in calculations (useful if you want to crash onto planets)
    :return string: The command trying to be passed to the Halite engine or None if movement is not possible within max_corrections degrees.
    :rtype: str
    """
    if max_corrections <= 0:
        return 0, 0
    cdef double distance = calculate_distance_between(ship, target)
    cdef double angle = calculate_angle_between(ship, target)

    cdef double new_target_dx
    cdef double new_target_dy
    cdef Circle new_target

    if not ignore_planets or not ignore_ships:
        if obstacles_between(ship, target, game_map,  ignore_ships = ignore_ships, ignore_planets=ignore_planets):
            new_target_dx = cos(radians(angle + angular_step)) * distance
            new_target_dy = sin(radians(angle + angular_step)) * distance
            new_target = Circle(ship.x + new_target_dx, ship.y + new_target_dy)
            return navigate(ship,new_target, game_map, speed,  max_corrections - 1, angular_step,
                                 ignore_ships = ignore_ships, ignore_planets = ignore_planets)
    speed = speed if (distance >= speed) else distance
    return speed, angle
