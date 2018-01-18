from libc.math cimport sqrt, M_PI, sin, cos, round, atan2, acos
from bot.settings import ASSASSIN_AVOID_RADIUS, config

cdef double radians(double angle):
    """
    Convert degrees to radians
    :param angle: 
    :return: 
    """
    return (angle / 180.0) * M_PI

cdef double degrees(double angle):
    """
    convert radians to degrees
    :param angle: 
    :return: 
    """
    return (angle / M_PI) * 180.0

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
        return "Circle({:.2f}, {:.2f}, {:.2f})".format(self.x, self.y, self.radius)

    def __repr__(self):
        return self.__str__()

    def __add__(self,Circle other):
        return Circle(self.x + other.x, self.y + other.y, other.radius)

    def __sub__(self,Circle other):
        return Circle(self.x - other.x, self.y - other.y, other.radius)

    def __truediv__(self, double other):
        return Circle(self.x / other, self.y / other, self.radius)

    def __mul__(self, other):
        cdef double d1
        cdef double d2
        cdef double scalar
        if isinstance(other, Circle):
            d1 = calculate_length(self)
            d2 = calculate_length(other)
            scalar =  (self.x * other.x + self.y * other.y) / (d1 * d2)
            return scalar
        else:
            return Circle(self.x * other, self.y * other, self.radius)

    @staticmethod
    def zero():
        return Circle(0,0,0)

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

cpdef double calculate_length(Circle v1):
    """
    Calculate the length of a vector
    :param v1: 
    :return: 
    """
    return sqrt((v1.x ** 2) + (v1.y ** 2))

cpdef double calculate_angle_vector(Circle v1, Circle v2):
    """
    Calculate the angle between 2 vectors
    :param v1: 
    :param v2: 
    :return: 
    """
    cdef double scalar = v1 * v2
    return degrees(acos(scalar))

cpdef Circle calculate_direction(Circle p1, Circle p2):
    """
    Return the direction between p1 & p2 :
    :param p1: 
    :param p2: 
    :return: p2 - p1
    """
    return p2 - p1

cpdef Circle closest_point_to(Circle p1, Circle p2, int min_distance=3):
    """
    Find the closest point to the given ship near the given target, outside its given radius,
    with an added fudge of min_distance.

    :param p1: Circle #1 (the ship)
    :param p2: Circle #1 (the target)
    :param int min_distance: Minimum distance specified from the object's outer radius
    :return: The closest point's coordinates
    :rtype: Circle
    """
    cdef double angle = calculate_angle_between(p2, p1)
    cdef double radius = p2.radius + min_distance
    cdef double x = p2.x + radius * cos(radians(angle))
    cdef double y = p2.y + radius * sin(radians(angle))

    return Circle(x, y)

cpdef bint intersect_segment_circle(Circle start, Circle end, Circle circle, fudge=0.5):
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

    cdef double a = dx ** 2 + dy ** 2

    #Never happens
    if a == 0.0:
        # Start and end are the same point
        return calculate_distance_between(start, circle) <= circle.radius + fudge

    cdef double b = -2 * (start.x ** 2 - start.x * end.x - start.x * circle.x + end.x * circle.x +
                          start.y ** 2 - start.y * end.y - start.y * circle.y + end.y * circle.y)
    cdef double c = (start.x - circle.x) ** 2 + (start.y - circle.y) ** 2

    # Time along segment when closest to the circle (vertex of the quadratic)
    cdef double t = min(-b / (2 * a), 1.0)
    if t < 0:
        return False

    cdef double closest_x = start.x + dx * t
    cdef double closest_y = start.y + dy * t
    cdef Circle closest = Circle(closest_x, closest_y)
    cdef double closest_distance = calculate_distance_between(closest, circle)

    return closest_distance <= circle.radius + fudge

cpdef bint obstacles_between(Circle ship, Circle target, game_map, bint ignore_ships=False,
                             bint ignore_planets = False, bint ignore_ghosts = False, assassin = False):
    """
    Check whether there is a straight-line path to the given point, without planetary obstacles in between.

    :param Circle ship: Source entity
    :param Circle target: Target entity
    :param Map game_map: the game_map
    :param bint ignore_ships: Should we ignore ships
    :param bint ignore_planets: Should we ignore planets
    :param bint ignore_ghosts: Should we ignore ghosts
    :param bint assassin: Is the ship an assassin? => Increase fudge for enemy ship
    :return: is there an obstacle on the path?
    :rtype: bint
    """

    if target.x < 1:
        return True
    if target.y < 1:
        return True
    if target.x + 1 > game_map.width:
        return True
    if target.y + 1 > game_map.height:
        return True

    cdef double fudge = ship.radius + 0.1
    # Avoid my own ships
    if not ignore_ships:
        for my_ship in game_map.get_me().all_ships():
            if my_ship.pos == ship:
                continue
            # If the ship is too far ahead, no need to look right now
            if my_ship.docking_status==0 and calculate_distance_between(my_ship.pos, ship) > config.NAVIGATION_SHIP_DISTANCE:
                continue
            if intersect_segment_circle(ship, target, my_ship.pos, fudge=fudge):
                return True

    # Avoid ghost (future position of my ships)
    if not ignore_ghosts:
        for start,ghost in game_map.all_ghost():
            if segment_intersect(start,ghost, ship, target):
                return True
            if intersect_segment_circle(ship, target, ghost, fudge=fudge+1):
                return True
            if calculate_distance_between(target, ghost) < ghost.radius + fudge:
                return True

    # Avoid planets
    if not ignore_planets:
        for planet in game_map.all_planets():
            if planet.pos == ship or planet.pos == target:
                continue
            if intersect_segment_circle(ship, target, planet.pos, fudge=fudge):
                return True

    # Assassin needs to have a different fudge for docked & undocked ship
    cdef double undocked_fudge = fudge
    if assassin:
        # Increase the the fudge but only for undocked ship, docked ship are safe
        undocked_fudge += ASSASSIN_AVOID_RADIUS

    # Avoid enemy ships
    if not ignore_ships:
        for enemy_ship in game_map.all_ships():
            # Don't look at my own ship in this loop
            if enemy_ship.owner.id == game_map.get_me().id:
                continue
            # Don't look at the ship that could be the target
            if enemy_ship.pos == target:
                continue
            # If the ship is too far ahead, no need to look right now
            if enemy_ship.docking_status==0 and calculate_distance_between(enemy_ship.pos, ship) > config.NAVIGATION_SHIP_DISTANCE:
                continue
            # Handle docked & undocked ship with different fudge (if assassin)
            if enemy_ship.docking_status == 0: # UNDOCKED (hack to avoid import)
                if intersect_segment_circle(ship, target, enemy_ship.pos, fudge=undocked_fudge):
                    return True
            else:
                if intersect_segment_circle(ship, target, enemy_ship.pos, fudge=fudge):
                    return True



    return False

cdef Circle dx_target(start, angle, distance):
    cdef int new_target_dx
    cdef int new_target_dy
    cdef Circle new_target
    if angle < 0:
        angle += 360
    angle = angle % 360
    new_target_dx = int(round(cos((M_PI / 180.0) * angle) * <double> distance))
    new_target_dy = int(round(sin((M_PI / 180.0) * angle) * <double> distance))
    new_target = Circle(start.x + new_target_dx, start.y + new_target_dy)
    return new_target

cpdef tuple navigate(Circle ship, Circle target, game_map, double speed, int max_corrections=90, int angular_step=1,
                     bint ignore_ships=False, bint ignore_planets=False, ignore_ghosts=False, assassin=False):
    """
    Move a ship to a specific target position (Entity). It is recommended to place the position
    itself here, else navigate will crash into the target. If avoid_obstacles is set to True (default)
    will avoid obstacles on the way, with up to max_corrections corrections. Note that each correction accounts
    for angular_step degrees difference, meaning that the algorithm will naively try max_correction degrees before giving
    up (and returning None). The navigation will only consist of up to one command; call this method again
    in the next turn to continue navigating to the position.

    :param Circle ship: The ship that navigates
    :param Circle target: The entity to which you will navigate
    :param game_map.Map game_map: The map of the game, from which obstacles will be extracted
    :param int speed: The (max) speed to navigate. If the obstacle is nearer, will adjust accordingly.
    :param int max_corrections: The maximum number of degrees to deviate per turn while trying to pathfind. If exceeded returns None.
    :param int angular_step: The degree difference to deviate if the original destination has obstacles
    :param bool ignore_ships: Whether to ignore ships in calculations (this will make your movement faster, but more precarious)
    :param bool ignore_planets: Whether to ignore planets in calculations (useful if you want to crash onto planets)
    :param bool ignore_ghosts: Whether to ignore ghosts
    :param bool assassin: Whether the ship is an assassin
    :return tuple: the speed and angle of the thrust
    :rtype: tuple
    """

    # If we've run out of tries, we can't navigate
    if max_corrections <= 0:
        return 0, 0, None
    # Calculate the distance between the ship and its target
    cdef double distance = calculate_distance_between(ship, target)
    # Calculate the angle between the ship and its target
    cdef int angle = int(round(calculate_angle_between(ship, target)))

    # New ship target after correction
    cdef double new_target_dx
    cdef double new_target_dy
    cdef Circle new_target = target

    cdef int da = 0
    cdef int direction = 1
    cdef int new_angle = angle

    if not ignore_planets or not ignore_ships:
        while obstacles_between(ship, new_target, game_map, ignore_ships=ignore_ships, ignore_planets=ignore_planets, ignore_ghosts=ignore_ghosts, assassin=assassin):
            # Increase the delta angle
            da += angular_step
            # If we ran out of tries
            if da > max_corrections:
                # Return no thrust
                return 0, 0, None

            #Switch direction
            direction = -1 * direction
            # Add the new delta
            new_angle = angle + da * direction

            # Make sure the new_angle is between [0, 360]
            if new_angle < 0:
                new_angle = 360 + new_angle
            new_angle = new_angle % 360

            # Calculate the position of the new target
            new_target_dx = cos(radians(new_angle)) * distance
            new_target_dy = sin(radians(new_angle)) * distance
            new_target = Circle(ship.x + new_target_dx, ship.y + new_target_dy, target.radius)

    speed = speed if (distance >= speed) else distance

    #Also calculate the future position of the ship
    new_target_dx = cos(radians(new_angle)) * speed
    new_target_dy = sin(radians(new_angle)) * speed
    new_target = Circle(ship.x + new_target_dx, ship.y + new_target_dy, ship.radius * config.GHOST_RATIO_RADIUS)

    return speed, new_angle, new_target


# From https://www.cdn.geeksforgeeks.org/check-if-two-given-line-segments-intersect/
# Given three colinear points p, q, r, the function checks if
# point q lies on line segment 'pr'
cdef bint on_segment(Circle p, Circle q, Circle r):
    if min(p.x, r.x) <= q.x <= max(p.x, r.x) and  min(p.y, r.y) <= q.y <= max(p.y, r.y):
       return True
    return False

# To find orientation of ordered triplet (p, q, r).
# The function returns following values
# 0 --> p, q and r are collinear
# 1 --> Clockwise
# 2 --> Counterclockwise
cdef int orientation(Circle p, Circle q, Circle r):
    # See https://www.geeksforgeeks.org/orientation-3-ordered-points/
    # for details of below formula.
    cdef double val = (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y)

    if val == 0:
        return 0 # collinear

    if val > 0:
        return 1
    return 2

# The main function that returns true if line segment 'p1q1'
# and 'p2q2' intersect.
cpdef bint segment_intersect(Circle p1, Circle q1, Circle p2, Circle q2):
    # Find the four orientations needed for general and
    # special cases
    cdef int o1 = orientation(p1, q1, p2)
    cdef int o2 = orientation(p1, q1, q2)
    cdef int o3 = orientation(p2, q2, p1)
    cdef int o4 = orientation(p2, q2, q1)

    # General case
    if o1 != o2 and o3 != o4:
        return True

    # Special Cases
    # p1, q1 and p2 are collinear and p2 lies on segment p1q1
    if o1 == 0 and on_segment(p1, p2, q1):
        return True

    # p1, q1 and p2 are collinear and q2 lies on segment p1q1
    if o2 == 0 and on_segment(p1, q2, q1):
        return True

    # p2, q2 and p1 are collinear and p1 lies on segment p2q2
    if o3 == 0 and on_segment(p2, p1, q2):
        return True

    # p2, q2 and q1 are collinear and q1 lies on segment p2q2
    if o4 == 0 and on_segment(p2, q1, q2):
        return True

    return False # Doesn't fall in any of the above cases
