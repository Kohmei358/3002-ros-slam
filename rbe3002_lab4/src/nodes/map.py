import rospy
from nav_msgs.msg import GridCells
from nav_msgs.srv import GetMap


class Map:
    def __init__(self):
        self.refresh_map()

    def refresh_map(self):
        occupancy_grid = self.request_map()
        if occupancy_grid is None:
            raise TypeError("Tried to create Map object but got None for occupancy_grid")
        self.header = occupancy_grid.header
        self.info = occupancy_grid.info
        self.data = occupancy_grid.data
        self.calc_cspace()

    def request_map(self):
        """
        Requests the map from the map server.
        :return [OccupancyGrid] The grid if the service call was successful,
                                None in case of error.
        """
        ### REQUIRED CREDIT
        rospy.loginfo("Requesting the map")
        rospy.wait_for_service('static_map', timeout=None)
        try:
            map_server = rospy.ServiceProxy('static_map', GetMap)
            return map_server().map
        except rospy.ServiceException, e:
            return None

    def force_inbound(self, curr_x, curr_y):
        new_x = max(0, min(curr_x, self.info.width - 1))
        new_y = max(0, min(curr_y, self.info.height - 1))

        return new_x, new_y

    def neighbors_of_4(self, x, y):
        """
        Returns the walkable 4-neighbors cells of (x,y) in the occupancy grid.
        :param self [OccupancyGrid] The map information.
        :param x       [int]           The X coordinate in the grid.
        :param y       [int]           The Y coordinate in the grid.
        :return        [[(int,int)]]   A list of walkable 4-neighbors.
        """
        return_list = []

        if x != 0 and self.is_cell_walkable(x - 1, y):
            return_list.append((x - 1, y))
        if x != self.info.width - 1 and self.is_cell_walkable(x + 1, y):
            return_list.append((x + 1, y))
        if y != 0 and self.is_cell_walkable(x, y - 1):
            return_list.append((x, y - 1))
        if y != self.info.height - 1 and self.is_cell_walkable(x, y + 1):
            return_list.append((x, y + 1))

        return return_list

    def neighbors_of_8(self, x, y):
        """
        Returns the walkable 8-neighbors cells of (x,y) in the occupancy grid.
        :param mapdata [OccupancyGrid] The map information.
        :param x       [int]           The X coordinate in the grid.
        :param y       [int]           The Y coordinate in the grid.
        :return        [[(int,int)]]   A list of walkable 8-neighbors.
        """
        # This already checks for in-boundness
        returnList = self.neighbors_of_4(x, y)

        if x != 0 and y != 0 and self.is_cell_walkable(x - 1, y - 1):
            returnList.append((x - 1, y - 1))
        if x != self.info.width - 1 and y != 0 and self.is_cell_walkable(x + 1, y - 1):
            returnList.append((x + 1, y - 1))
        if y != self.info.height - 1 and x != 0 and self.is_cell_walkable(x - 1, y + 1):
            returnList.append((x - 1, y + 1))
        if x != self.info.width - 1 and y != self.info.height - 1 and self.is_cell_walkable(x + 1, y + 1):
            returnList.append((x + 1, y + 1))

        return returnList

    def is_cell_in_bounds(self, x, y):
        return 0 <= x < self.info.width - 1 and self.info.height - 1 > y >= 0

    def grid_to_index(self, x, y):
        """
        Returns the index corresponding to the given (x,y) coordinates in the occupancy grid.
        :param x [int] The cell X coordinate.
        :param y [int] The cell Y coordinate.
        :return  [int] The index.
        """
        return y * self.info.width + x

    def get_cell_value(self, x, y):
        if not self.is_cell_in_bounds(x, y):
            raise IndexError("The cell index (%d, %d) is outside of this map (size %dx%d)" % (
                x, y, self.info.width, self.info.height))
        return self.data[self.grid_to_index(x, y)]

    def is_cell_walkable(self, x, y):
        """
        A cell is walkable if all of these conditions are true:
        1. It is within the boundaries of the grid;
        2. It is free (not unknown, not occupied by an obstacle)
        :param mapdata [OccupancyGrid] The map information.
        :param x       [int]           The X coordinate in the grid.
        :param y       [int]           The Y coordinate in the grid.
        :return        [boolean]       True if the cell is walkable, False otherwise
        """

        ### REQUIRED CREDIT
        "if the x and y coordinates are out of bounds"
        return self.is_cell_in_bounds(x, y) and self.get_cell_value(x, y) < 0.196

    def is_cell_wall(self, x, y):
        return self.get_cell_value(x, y) > 0.55

    def is_cell_unknown(self, x, y):
        return self.is_cell_in_bounds(x, y) and self.get_cell_value(x, y) == 0.5

    def calc_cspace(self):
        """
        Calculates the C-Space, i.e., makes the obstacles in the map thicker.
        Publishes the list of cells that were added to the original map.
        :param mapdata [OccupancyGrid] The map data.
        :param padding [int]           The number of cells around the obstacles.
        :return        [OccupancyGrid] The C-Space.self.pubCspace.publish(msg)
        """
        OBSTACLE_THRESH = 90
        rospy.loginfo("Calculating C-Space")

        paddedArray = list(self.data)

        ## Go through each cell in the occupancy grid
        for x in range(self.info.height):
            for y in range(self.info.width):
                ## Inflate the obstacles where necessary
                if self.data[self.grid_to_index(x, y)] > OBSTACLE_THRESH:
                    paddedArray[self.grid_to_index(x, y)] = 100
                    for neighbor in self.neighbors_of_8(x, y):
                        x3, y3 = self.force_inbound(neighbor[0], neighbor[1])
                        paddedArray[self.grid_to_index(x3, y3)] = 100

        paddedArray = tuple(paddedArray)
        gridCellsList = []

        for x in range(self.info.height):
            for y in range(self.info.width):
                ## Inflate the obstacles where necessary
                if paddedArray[self.grid_to_index(x, y)] > OBSTACLE_THRESH:
                    world_point = self.grid_to_world(x, y)
                    gridCellsList.append(world_point)

        ## Create a GridCells message and publish it
        msg = GridCells()
        msg.cell_width = self.info.resolution
        msg.cell_height = self.info.resolution
        msg.cells = gridCellsList
        msg.header = self.header
        self.pubCspace.publish(msg)
        self.cspace_data = paddedArray